"""Raster conversion planning primitives."""

from __future__ import annotations

from dataclasses import dataclass

from inkotter.core.document import DocumentFormat, DocumentSpec
from inkotter.core.layout import LayoutMode, LayoutPlan
from inkotter.devices.base import DeviceProfile


@dataclass(frozen=True)
class PageSpan:
    index: int
    start_x_px: int
    width_px: int
    trim_left_px: int
    is_final: bool


@dataclass(frozen=True)
class RasterPlan:
    head_height_px: int
    target_canvas_width_px: int
    raster_pixels_per_mm: float
    place_top_left: bool
    fit_to_content_height_px: int | None
    page_spans: tuple[PageSpan, ...]
    reason: str


def _document_width_px_for_plan(document: DocumentSpec, plan: LayoutPlan, device: DeviceProfile) -> int:
    if document.format == DocumentFormat.SVG and document.physical_size_mm is not None:
        return max(1, round(document.physical_size_mm.width_mm * plan.svg_pixels_per_mm))
    if document.pixel_size is not None:
        return document.pixel_size.width_px
    return device.raster.page_width_px


def build_raster_plan(document: DocumentSpec, plan: LayoutPlan, device: DeviceProfile) -> RasterPlan:
    raster = device.raster
    document_width_px = _document_width_px_for_plan(document, plan, device)

    if plan.mode == LayoutMode.FIT_TO_LABEL:
        target_canvas_width_px = raster.page_width_px
        trim_left_px = raster.trim_probe_columns // 2
        page_spans = (
            PageSpan(
                index=0,
                start_x_px=0,
                width_px=target_canvas_width_px,
                trim_left_px=trim_left_px if plan.should_trim_first_page_left else 0,
                is_final=True,
            ),
        )
        return RasterPlan(
            head_height_px=raster.head_height_px,
            target_canvas_width_px=target_canvas_width_px,
            raster_pixels_per_mm=plan.svg_pixels_per_mm,
            place_top_left=plan.should_top_left_anchor,
            fit_to_content_height_px=raster.fitted_content_height_px,
            page_spans=page_spans,
            reason=plan.reason,
        )

    target_canvas_width_px = document_width_px
    spans: list[PageSpan] = []
    remaining = target_canvas_width_px
    current_x = 0
    index = 0
    while remaining > 0:
        page_width = min(raster.page_width_px, remaining)
        spans.append(
            PageSpan(
                index=index,
                start_x_px=current_x,
                width_px=page_width,
                trim_left_px=0,
                is_final=remaining <= raster.page_width_px,
            )
        )
        current_x += page_width
        remaining -= page_width
        index += 1

    return RasterPlan(
        head_height_px=raster.head_height_px,
        target_canvas_width_px=target_canvas_width_px,
        raster_pixels_per_mm=plan.svg_pixels_per_mm,
        place_top_left=plan.should_top_left_anchor,
        fit_to_content_height_px=None,
        page_spans=tuple(spans),
        reason=plan.reason,
    )
