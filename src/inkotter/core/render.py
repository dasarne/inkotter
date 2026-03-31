"""Protocol-neutral render contract and first monochrome renderer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from pathlib import Path
import subprocess
import tempfile

from PIL import Image

from inkotter.core.document import DocumentFormat, DocumentSpec
from inkotter.core.layout import LayoutMode, LayoutPlan
from inkotter.core.raster import RasterPlan

try:
    import cairosvg
except Exception:  # pragma: no cover - optional dependency at runtime
    cairosvg = None


class RenderResample(str, Enum):
    NEAREST = "nearest"
    LANCZOS = "lanczos"


class MonochromeStrategy(str, Enum):
    THRESHOLD = "threshold"


@dataclass(frozen=True)
class PixelExtent:
    width_px: int
    height_px: int


@dataclass(frozen=True)
class PixelPlacement:
    x_px: int
    y_px: int
    width_px: int
    height_px: int


@dataclass(frozen=True)
class RenderPlan:
    canvas: PixelExtent
    source_raster: PixelExtent
    placement: PixelPlacement
    svg_pixels_per_mm: float
    resample: RenderResample
    monochrome_strategy: MonochromeStrategy
    monochrome_threshold: int
    reason: str


@dataclass(frozen=True)
class RenderedCanvasSpec:
    canvas: PixelExtent
    placement: PixelPlacement
    monochrome_threshold: int
    reason: str


@dataclass
class RenderedMonochromeCanvas:
    grayscale_image: Image.Image
    monochrome_image: Image.Image
    plan: RenderPlan


DEFAULT_MONOCHROME_THRESHOLD = 230


def _source_raster_extent(document: DocumentSpec, plan: LayoutPlan) -> PixelExtent:
    if document.format == DocumentFormat.SVG and document.physical_size_mm is not None:
        return PixelExtent(
            width_px=max(1, round(document.physical_size_mm.width_mm * plan.svg_pixels_per_mm)),
            height_px=max(1, round(document.physical_size_mm.height_mm * plan.svg_pixels_per_mm)),
        )
    if document.pixel_size is not None:
        return PixelExtent(width_px=document.pixel_size.width_px, height_px=document.pixel_size.height_px)
    raise ValueError("document is missing both physical SVG size and raster pixel size")


def _fit_scaled_extent(source: PixelExtent, target_width_px: int, target_height_px: int) -> PixelExtent:
    if source.width_px <= 0 or source.height_px <= 0:
        raise ValueError("source extent must be positive")
    scale = min(target_width_px / source.width_px, target_height_px / source.height_px)
    return PixelExtent(
        width_px=max(1, round(source.width_px * scale)),
        height_px=max(1, round(source.height_px * scale)),
    )


def build_render_plan(document: DocumentSpec, layout: LayoutPlan, raster: RasterPlan) -> RenderPlan:
    source = _source_raster_extent(document, layout)
    canvas = PixelExtent(width_px=raster.target_canvas_width_px, height_px=raster.head_height_px)

    if layout.mode == LayoutMode.FIT_TO_LABEL:
        target_height_px = raster.fit_to_content_height_px or raster.head_height_px
        placed = _fit_scaled_extent(source, canvas.width_px, target_height_px)
        placement = PixelPlacement(
            x_px=max(0, (canvas.width_px - placed.width_px) // 2),
            y_px=max(0, (canvas.height_px - placed.height_px) // 2),
            width_px=placed.width_px,
            height_px=placed.height_px,
        )
        return RenderPlan(
            canvas=canvas,
            source_raster=source,
            placement=placement,
            svg_pixels_per_mm=layout.svg_pixels_per_mm,
            resample=RenderResample.NEAREST,
            monochrome_strategy=MonochromeStrategy.THRESHOLD,
            monochrome_threshold=DEFAULT_MONOCHROME_THRESHOLD,
            reason=layout.reason,
        )

    placement = PixelPlacement(
        x_px=0 if raster.place_top_left else max(0, (canvas.width_px - source.width_px) // 2),
        y_px=0 if raster.place_top_left else max(0, (canvas.height_px - source.height_px) // 2),
        width_px=min(source.width_px, canvas.width_px),
        height_px=min(source.height_px, canvas.height_px),
    )
    return RenderPlan(
        canvas=canvas,
        source_raster=source,
        placement=placement,
        svg_pixels_per_mm=layout.svg_pixels_per_mm,
        resample=RenderResample.NEAREST,
        monochrome_strategy=MonochromeStrategy.THRESHOLD,
        monochrome_threshold=DEFAULT_MONOCHROME_THRESHOLD,
        reason=layout.reason,
    )


def rendered_canvas_spec_from_plan(plan: RenderPlan) -> RenderedCanvasSpec:
    return RenderedCanvasSpec(
        canvas=plan.canvas,
        placement=plan.placement,
        monochrome_threshold=plan.monochrome_threshold,
        reason=plan.reason,
    )


def _pil_resample(mode: RenderResample) -> int:
    if mode == RenderResample.NEAREST:
        return Image.Resampling.NEAREST
    if mode == RenderResample.LANCZOS:
        return Image.Resampling.LANCZOS
    raise ValueError(f"unsupported resample mode: {mode}")


def _render_svg_with_cairosvg(document: DocumentSpec, plan: RenderPlan) -> Image.Image:
    png_bytes = cairosvg.svg2png(
        url=str(document.path),
        output_width=plan.source_raster.width_px,
        output_height=plan.source_raster.height_px,
        background_color="white",
    )
    with Image.open(BytesIO(png_bytes)) as im:
        return im.convert("L")


def _render_svg_with_inkscape(document: DocumentSpec, plan: RenderPlan) -> Image.Image:
    with tempfile.TemporaryDirectory(prefix="inkotter-svg-") as tmpdir:
        output = Path(tmpdir) / "render.png"
        cmd = [
            "inkscape",
            str(document.path),
            f"--export-filename={output}",
            f"--export-width={plan.source_raster.width_px}",
            f"--export-height={plan.source_raster.height_px}",
            "--export-background=white",
            "--export-background-opacity=255",
        ]
        completed = subprocess.run(cmd, capture_output=True, text=True)
        if completed.returncode != 0:
            stderr = completed.stderr.strip() or completed.stdout.strip() or "unknown inkscape error"
            raise RuntimeError(f"Inkscape SVG render failed: {stderr}")
        with Image.open(output) as im:
            return im.convert("L")


def _render_svg_to_grayscale(document: DocumentSpec, plan: RenderPlan) -> Image.Image:
    if cairosvg is not None:
        return _render_svg_with_cairosvg(document, plan)
    return _render_svg_with_inkscape(document, plan)


def _render_raster_to_grayscale(document: DocumentSpec, plan: RenderPlan) -> Image.Image:
    with Image.open(document.path) as im:
        grayscale = im.convert("L")
        if grayscale.width == plan.source_raster.width_px and grayscale.height == plan.source_raster.height_px:
            return grayscale.copy()
        return grayscale.resize(
            (plan.source_raster.width_px, plan.source_raster.height_px),
            resample=_pil_resample(plan.resample),
        )


def _render_source_to_grayscale(document: DocumentSpec, plan: RenderPlan) -> Image.Image:
    if document.format == DocumentFormat.SVG:
        return _render_svg_to_grayscale(document, plan)
    return _render_raster_to_grayscale(document, plan)


def _crop_for_placement(source: Image.Image, placement: PixelPlacement) -> Image.Image:
    if source.width == placement.width_px and source.height == placement.height_px:
        return source
    return source.crop((0, 0, placement.width_px, placement.height_px))


def _threshold_to_monochrome(image: Image.Image, threshold: int) -> Image.Image:
    grayscale = image.convert("L")
    return grayscale.point(lambda value: 0 if value < threshold else 255, mode="1")


def render_document_to_monochrome_canvas(document: DocumentSpec, plan: RenderPlan) -> RenderedMonochromeCanvas:
    source = _render_source_to_grayscale(document, plan)
    placed_source = _crop_for_placement(source, plan.placement)

    grayscale_canvas = Image.new("L", (plan.canvas.width_px, plan.canvas.height_px), color=255)
    grayscale_canvas.paste(placed_source, (plan.placement.x_px, plan.placement.y_px))

    if plan.monochrome_strategy != MonochromeStrategy.THRESHOLD:
        raise ValueError(f"unsupported monochrome strategy: {plan.monochrome_strategy}")
    monochrome_canvas = _threshold_to_monochrome(grayscale_canvas, plan.monochrome_threshold)
    return RenderedMonochromeCanvas(
        grayscale_image=grayscale_canvas,
        monochrome_image=monochrome_canvas,
        plan=plan,
    )
