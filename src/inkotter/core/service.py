"""End-to-end print job service built on the core kernel."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from inkotter.core.document import DocumentSpec, document_spec_from_path
from inkotter.core.layout import LayoutPlan, choose_layout_plan
from inkotter.core.raster import RasterPlan, build_raster_plan
from inkotter.core.render import RenderPlan, RenderedMonochromeCanvas, build_render_plan, render_document_to_monochrome_canvas
from inkotter.devices.base import DeviceProfile
from inkotter.protocol import BtbufJob, EncodedJob, FramedPacket, build_grouped_image_frames, build_t15_btbuf_job, compress_btbuf_job


@dataclass(frozen=True)
class PreparedPrintJob:
    device: DeviceProfile
    document: DocumentSpec
    layout: LayoutPlan
    raster: RasterPlan
    render: RenderPlan
    canvas: RenderedMonochromeCanvas
    btbuf_job: BtbufJob
    encoded_job: EncodedJob
    frames: tuple[FramedPacket, ...]


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



def prepare_print_job(
    image_path: str | Path,
    device: DeviceProfile,
    *,
    no_scale: bool = False,
) -> PreparedPrintJob:
    document = document_spec_from_path(image_path)
    layout = choose_layout_plan(document, device, no_scale=no_scale)
    raster = build_raster_plan(document, layout, device)
    render = build_render_plan(document, layout, raster)
    canvas = render_document_to_monochrome_canvas(document, render)
    btbuf_job = build_t15_btbuf_job(canvas, raster, device)
    encoded_job = compress_btbuf_job(btbuf_job)
    frames = build_grouped_image_frames(encoded_job, device)
    return PreparedPrintJob(
        device=device,
        document=document,
        layout=layout,
        raster=raster,
        render=render,
        canvas=canvas,
        btbuf_job=btbuf_job,
        encoded_job=encoded_job,
        frames=frames,
    )



def summarize_print_job(job: PreparedPrintJob) -> PrintJobSummary:
    return PrintJobSummary(
        device_name=job.device.display_name,
        document_path=job.document.path,
        layout_mode=job.layout.mode.value,
        canvas_width_px=job.render.canvas.width_px,
        canvas_height_px=job.render.canvas.height_px,
        page_count=job.btbuf_job.page_count,
        frame_count=len(job.frames),
        chunks_per_page=tuple(len(page.aabb_payloads) for page in job.encoded_job.pages),
    )
