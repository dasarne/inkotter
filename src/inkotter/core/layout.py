"""Layout decisions for fit-to-label and actual-size printing."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from inkotter.core.document import DocumentFormat, DocumentSpec
from inkotter.devices.base import DeviceProfile


class LayoutMode(str, Enum):
    FIT_TO_LABEL = "fit-to-label"
    ACTUAL_SIZE = "actual-size"
    WIDE_ACTUAL_SIZE = "wide-actual-size"


@dataclass(frozen=True)
class LayoutPlan:
    mode: LayoutMode
    should_prepare: bool
    should_auto_split_pages: bool
    should_top_left_anchor: bool
    should_trim_first_page_left: bool
    svg_pixels_per_mm: float
    reason: str


def is_long_label_candidate_mm(width_mm: float, height_mm: float) -> bool:
    if height_mm <= 0:
        return False
    if width_mm / height_mm < 2.0:
        return False
    if not (10.0 <= height_mm <= 14.5):
        return False
    return width_mm >= 24.0


def choose_layout_plan(document: DocumentSpec, device: DeviceProfile, no_scale: bool = False) -> LayoutPlan:
    raster = device.raster
    if document.format == DocumentFormat.SVG and document.physical_size_mm is not None:
        width_mm = document.physical_size_mm.width_mm
        height_mm = document.physical_size_mm.height_mm
        if no_scale:
            return LayoutPlan(
                mode=LayoutMode.ACTUAL_SIZE,
                should_prepare=False,
                should_auto_split_pages=width_mm > (raster.actual_size_single_page_max_width_mm or 0.0),
                should_top_left_anchor=True,
                should_trim_first_page_left=False,
                svg_pixels_per_mm=raster.pixels_per_mm,
                reason="explicit actual-size SVG document mode",
            )
        if is_long_label_candidate_mm(width_mm, height_mm):
            if (
                raster.actual_size_single_page_max_width_mm is not None
                and width_mm > raster.actual_size_single_page_max_width_mm
            ):
                return LayoutPlan(
                    mode=LayoutMode.WIDE_ACTUAL_SIZE,
                    should_prepare=False,
                    should_auto_split_pages=True,
                    should_top_left_anchor=True,
                    should_trim_first_page_left=False,
                    svg_pixels_per_mm=raster.pixels_per_mm,
                    reason="wide SVG with explicit physical size exceeds the single-page actual-size range",
                )
            return LayoutPlan(
                mode=LayoutMode.FIT_TO_LABEL,
                should_prepare=False,
                should_auto_split_pages=False,
                should_top_left_anchor=False,
                should_trim_first_page_left=True,
                svg_pixels_per_mm=12.0,
                reason="validated long-label SVG fits the everyday one-page renderer",
            )

    return LayoutPlan(
        mode=LayoutMode.FIT_TO_LABEL,
        should_prepare=True,
        should_auto_split_pages=False,
        should_top_left_anchor=False,
        should_trim_first_page_left=True,
        svg_pixels_per_mm=raster.pixels_per_mm,
        reason="default conservative layout path",
    )
