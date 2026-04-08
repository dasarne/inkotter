"""End-to-end print job service built on the core kernel."""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import replace
from io import BytesIO
from pathlib import Path

from PIL import Image

from inkotter.core.document import DocumentSpec, document_spec_from_path
from inkotter.core.layout import LayoutMode, LayoutPlan, choose_layout_plan
from inkotter.core.raster import RasterPlan, build_raster_plan
from inkotter.core.render import (
    DEFAULT_MONOCHROME_THRESHOLD,
    MonochromeStrategy,
    PixelPlacement,
    RenderPlan,
    RenderedMonochromeCanvas,
    build_render_plan,
    render_document_to_monochrome_canvas,
)
from inkotter.devices.base import DeviceProfile
from inkotter.protocol import BtbufJob, EncodedJob, FramedPacket, build_grouped_image_frames, build_t15_btbuf_job, compress_btbuf_job


@dataclass(frozen=True)
class PreparedPrintJob:
    device: DeviceProfile
    document: DocumentSpec
    layout: LayoutPlan
    raster: RasterPlan
    render: RenderPlan
    rendered_canvas: RenderedMonochromeCanvas
    preview_canvas: RenderedMonochromeCanvas
    printer_ready_canvas: RenderedMonochromeCanvas
    btbuf_job: BtbufJob
    encoded_job: EncodedJob
    frames: tuple[FramedPacket, ...]

    @property
    def source_canvas(self) -> RenderedMonochromeCanvas:
        return self.rendered_canvas

    @property
    def canvas(self) -> RenderedMonochromeCanvas:
        return self.preview_canvas

    @property
    def print_canvas(self) -> RenderedMonochromeCanvas:
        return self.printer_ready_canvas


@dataclass(frozen=True)
class PrintJobSummary:
    device_name: str
    document_path: Path
    layout_mode: str
    canvas_width_px: int
    canvas_height_px: int
    page_count: int
    frame_count: int
    chunks_per_page: tuple[int, ...]


@dataclass(frozen=True)
class PreviewImages:
    graphic_image: Image.Image
    physical_print_image: Image.Image
    strip_width_px: int
    strip_height_px: int
    right_margin_px: int


@dataclass(frozen=True)
class CanvasVariants:
    rendered_canvas: RenderedMonochromeCanvas
    preview_canvas: RenderedMonochromeCanvas
    printer_ready_canvas: RenderedMonochromeCanvas


@dataclass(frozen=True)
class VisiblePreviewSurface:
    image: Image.Image
    width_px: int
    height_px: int


def _shift_rendered_canvas_horizontally(
    canvas: RenderedMonochromeCanvas,
    target_x_px: int,
) -> RenderedMonochromeCanvas:
    render = canvas.plan
    placement = render.placement
    if placement.width_px <= 0 or placement.height_px <= 0:
        return canvas

    target_x_px = min(target_x_px, max(0, render.canvas.width_px - placement.width_px))
    target_x_px = max(0, target_x_px)
    if target_x_px == placement.x_px:
        return canvas

    source_box = (
        placement.x_px,
        placement.y_px,
        placement.x_px + placement.width_px,
        placement.y_px + placement.height_px,
    )
    placed_grayscale = canvas.grayscale_image.crop(source_box)
    placed_monochrome = canvas.monochrome_image.crop(source_box)

    shifted_render = replace(
        render,
        placement=PixelPlacement(
            x_px=target_x_px,
            y_px=placement.y_px,
            width_px=placement.width_px,
            height_px=placement.height_px,
        ),
    )

    grayscale = Image.new("L", (render.canvas.width_px, render.canvas.height_px), color=255)
    monochrome = Image.new("1", (render.canvas.width_px, render.canvas.height_px), color=1)
    grayscale.paste(placed_grayscale, (target_x_px, placement.y_px))
    monochrome.paste(placed_monochrome, (target_x_px, placement.y_px))
    shifted_canvas = RenderedMonochromeCanvas(
        grayscale_image=grayscale,
        monochrome_image=monochrome,
        plan=shifted_render,
    )
    return shifted_canvas


def _apply_physical_left_cut_margin(
    canvas: RenderedMonochromeCanvas,
    device: DeviceProfile,
) -> RenderedMonochromeCanvas:
    render = canvas.plan
    placement = render.placement
    if placement.width_px <= 0 or placement.height_px <= 0:
        return canvas

    left_margin_px = device.raster.visible_area_left_cut_margin_px()
    visible_width_px = max(1, render.canvas.width_px - left_margin_px)
    target_x_px = left_margin_px
    if placement.width_px < visible_width_px:
        target_x_px += max(0, (visible_width_px - placement.width_px) // 2)
    return _shift_rendered_canvas_horizontally(canvas, target_x_px)


def _apply_device_print_output_offset(
    canvas: RenderedMonochromeCanvas,
    document: DocumentSpec,
    layout: LayoutPlan,
    device: DeviceProfile,
) -> RenderedMonochromeCanvas:
    if layout.mode != LayoutMode.FIT_TO_LABEL:
        return canvas

    offset_px = device.raster.fit_to_label_output_x_offset_px(document.format)
    if offset_px == 0:
        return canvas

    placement = canvas.plan.placement
    target_x_px = max(0, min(canvas.plan.canvas.width_px - placement.width_px, placement.x_px + offset_px))
    return _shift_rendered_canvas_horizontally(canvas, target_x_px)


def _build_canvas_variants(
    document: DocumentSpec,
    layout: LayoutPlan,
    render: RenderPlan,
    device: DeviceProfile,
) -> CanvasVariants:
    rendered_canvas = render_document_to_monochrome_canvas(document, render)
    preview_canvas = _apply_physical_left_cut_margin(rendered_canvas, device)
    printer_ready_canvas = _apply_device_print_output_offset(preview_canvas, document, layout, device)
    return CanvasVariants(
        rendered_canvas=rendered_canvas,
        preview_canvas=preview_canvas,
        printer_ready_canvas=printer_ready_canvas,
    )



def prepare_print_job(
    image_path: str | Path,
    device: DeviceProfile,
    *,
    no_scale: bool = False,
    monochrome_strategy: MonochromeStrategy = MonochromeStrategy.THRESHOLD,
    monochrome_threshold: int = DEFAULT_MONOCHROME_THRESHOLD,
) -> PreparedPrintJob:
    document = document_spec_from_path(image_path)
    layout = choose_layout_plan(document, device, no_scale=no_scale)
    raster = build_raster_plan(document, layout, device)
    render = build_render_plan(
        document,
        layout,
        raster,
        monochrome_strategy=monochrome_strategy,
        monochrome_threshold=monochrome_threshold,
    )
    canvases = _build_canvas_variants(document, layout, render, device)
    btbuf_job = build_t15_btbuf_job(canvases.printer_ready_canvas, raster, device)
    encoded_job = compress_btbuf_job(btbuf_job)
    frames = build_grouped_image_frames(encoded_job, device)
    return PreparedPrintJob(
        device=device,
        document=document,
        layout=layout,
        raster=raster,
        render=render,
        rendered_canvas=canvases.rendered_canvas,
        preview_canvas=canvases.preview_canvas,
        printer_ready_canvas=canvases.printer_ready_canvas,
        btbuf_job=btbuf_job,
        encoded_job=encoded_job,
        frames=frames,
    )



def summarize_print_job(job: PreparedPrintJob) -> PrintJobSummary:
    return PrintJobSummary(
        device_name=job.device.display_name,
        document_path=job.document.path,
        layout_mode=job.layout.mode.value,
        canvas_width_px=job.preview_canvas.plan.canvas.width_px,
        canvas_height_px=job.preview_canvas.plan.canvas.height_px,
        page_count=job.btbuf_job.page_count,
        frame_count=len(job.frames),
        chunks_per_page=tuple(len(page.aabb_payloads) for page in job.encoded_job.pages),
    )


def _preview_right_margin_px(job: PreparedPrintJob) -> int:
    return job.device.raster.preview_margin_right_px()


def _preview_left_margin_px(job: PreparedPrintJob) -> int:
    return job.device.raster.preview_margin_left_px()


def _preview_top_margin_px(job: PreparedPrintJob) -> int:
    return job.device.raster.preview_margin_top_px()


def _preview_bottom_margin_px(job: PreparedPrintJob) -> int:
    return job.device.raster.preview_margin_bottom_px()


def _visible_preview_canvas(image: Image.Image, top_inset_px: int) -> Image.Image:
    if top_inset_px <= 0:
        return image.convert("L")
    grayscale = image.convert("L")
    visible = Image.new("L", grayscale.size, color=255)
    cropped = grayscale.crop((0, top_inset_px, grayscale.width, grayscale.height))
    visible.paste(cropped, (0, 0))
    return visible


def _crop_physical_visible_area(image: Image.Image, left_cut_margin_px: int) -> Image.Image:
    grayscale = image.convert("L")
    if left_cut_margin_px <= 0:
        return grayscale
    left = min(left_cut_margin_px, grayscale.width - 1)
    return grayscale.crop((left, 0, grayscale.width, grayscale.height))


def _build_visible_preview_surface(
    image: Image.Image,
    *,
    top_inset_px: int,
    left_cut_margin_px: int,
) -> VisiblePreviewSurface:
    visible_image = _visible_preview_canvas(image, top_inset_px)
    visible_image = _crop_physical_visible_area(visible_image, left_cut_margin_px)
    return VisiblePreviewSurface(
        image=visible_image,
        width_px=visible_image.width,
        height_px=visible_image.height,
    )


def _materialize_preview_strip(
    surface: VisiblePreviewSurface,
    *,
    left_margin_px: int,
    top_margin_px: int,
    total_width_px: int,
    total_height_px: int,
) -> Image.Image:
    strip = Image.new("L", (total_width_px, total_height_px), color=255)
    strip.paste(surface.image, (left_margin_px, top_margin_px))
    return strip


def build_preview_images(job: PreparedPrintJob) -> PreviewImages:
    raster = job.device.raster
    left_margin_px = _preview_left_margin_px(job)
    right_margin_px = _preview_right_margin_px(job)
    top_margin_px = _preview_top_margin_px(job)
    bottom_margin_px = _preview_bottom_margin_px(job)
    left_cut_margin_px = raster.visible_area_left_cut_margin_px()
    top_inset_px = raster.visible_area_top_inset_px()

    visible_graphic = _build_visible_preview_surface(
        job.preview_canvas.grayscale_image,
        top_inset_px=top_inset_px,
        left_cut_margin_px=left_cut_margin_px,
    )
    visible_physical_print = _build_visible_preview_surface(
        job.printer_ready_canvas.monochrome_image,
        top_inset_px=top_inset_px,
        left_cut_margin_px=left_cut_margin_px,
    )
    total_width_px = max(
        1,
        left_margin_px + visible_physical_print.width_px + right_margin_px,
    )
    total_height_px = max(
        1,
        top_margin_px + visible_physical_print.height_px + bottom_margin_px,
    )

    graphic = _materialize_preview_strip(
        visible_graphic,
        left_margin_px=left_margin_px,
        top_margin_px=top_margin_px,
        total_width_px=total_width_px,
        total_height_px=total_height_px,
    )
    physical = _materialize_preview_strip(
        visible_physical_print,
        left_margin_px=left_margin_px,
        top_margin_px=top_margin_px,
        total_width_px=total_width_px,
        total_height_px=total_height_px,
    )
    return PreviewImages(
        graphic_image=graphic,
        physical_print_image=physical,
        strip_width_px=total_width_px,
        strip_height_px=total_height_px,
        right_margin_px=right_margin_px,
    )


def build_physical_print_preview(job: PreparedPrintJob) -> Image.Image:
    return build_preview_images(job).physical_print_image


def encode_preview_png(image: Image.Image) -> bytes:
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()
