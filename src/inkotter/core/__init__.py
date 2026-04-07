"""Core printing abstractions."""

from inkotter.core.document import DocumentSpec, document_spec_from_path
from inkotter.core.job import PrintJobRequest
from inkotter.core.layout import LayoutMode, LayoutPlan, choose_layout_plan
from inkotter.core.raster import RasterPlan, build_raster_plan
from inkotter.core.render import (
    DEFAULT_MONOCHROME_THRESHOLD,
    MonochromeStrategy,
    RenderPlan,
    RenderedMonochromeCanvas,
    build_render_plan,
    render_document_to_monochrome_canvas,
)
from inkotter.core.service import (
    PreparedPrintJob,
    PrintJobSummary,
    build_preview_images,
    build_physical_print_preview,
    encode_preview_png,
    prepare_print_job,
    summarize_print_job,
)

__all__ = [
    "DocumentSpec",
    "LayoutMode",
    "LayoutPlan",
    "MonochromeStrategy",
    "PreparedPrintJob",
    "PrintJobRequest",
    "PrintJobSummary",
    "RasterPlan",
    "RenderPlan",
    "RenderedMonochromeCanvas",
    "DEFAULT_MONOCHROME_THRESHOLD",
    "build_preview_images",
    "build_physical_print_preview",
    "build_raster_plan",
    "build_render_plan",
    "choose_layout_plan",
    "document_spec_from_path",
    "encode_preview_png",
    "prepare_print_job",
    "render_document_to_monochrome_canvas",
    "summarize_print_job",
]
