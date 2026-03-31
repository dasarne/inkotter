"""Document loading and physical-size model."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re
import xml.etree.ElementTree as ET

from PIL import Image


_SVG_UNIT_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*(mm|cm|in|px)?\s*$", re.IGNORECASE)


class DocumentFormat(str, Enum):
    SVG = "svg"
    PNG = "png"
    JPEG = "jpeg"
    OTHER_RASTER = "other-raster"


@dataclass(frozen=True)
class PhysicalSizeMm:
    width_mm: float
    height_mm: float


@dataclass(frozen=True)
class PixelSize:
    width_px: int
    height_px: int


@dataclass(frozen=True)
class DocumentSpec:
    path: Path
    format: DocumentFormat
    pixel_size: PixelSize | None
    physical_size_mm: PhysicalSizeMm | None


def detect_document_format(path: Path) -> DocumentFormat:
    suffix = path.suffix.lower()
    if suffix == ".svg":
        return DocumentFormat.SVG
    if suffix == ".png":
        return DocumentFormat.PNG
    if suffix in (".jpg", ".jpeg"):
        return DocumentFormat.JPEG
    return DocumentFormat.OTHER_RASTER


def _svg_dimension_to_mm(raw: str | None) -> float | None:
    if not raw:
        return None
    match = _SVG_UNIT_RE.match(raw)
    if not match:
        return None
    value = float(match.group(1))
    unit = (match.group(2) or "px").lower()
    if unit == "mm":
        return value
    if unit == "cm":
        return value * 10.0
    if unit == "in":
        return value * 25.4
    if unit == "px":
        # SVG px are CSS px; 96 px per inch.
        return value * 25.4 / 96.0
    return None


def read_svg_physical_size_mm(path: Path) -> PhysicalSizeMm | None:
    try:
        root = ET.fromstring(path.read_text())
    except Exception:
        return None
    width_mm = _svg_dimension_to_mm(root.attrib.get("width"))
    height_mm = _svg_dimension_to_mm(root.attrib.get("height"))
    if width_mm is None or height_mm is None:
        return None
    return PhysicalSizeMm(width_mm=width_mm, height_mm=height_mm)


def read_raster_pixel_size(path: Path) -> PixelSize | None:
    try:
        with Image.open(path) as im:
            return PixelSize(width_px=im.width, height_px=im.height)
    except Exception:
        return None


def document_spec_from_path(path: str | Path) -> DocumentSpec:
    doc_path = Path(path)
    fmt = detect_document_format(doc_path)
    pixel_size = None
    physical_size_mm = None
    if fmt == DocumentFormat.SVG:
        physical_size_mm = read_svg_physical_size_mm(doc_path)
    else:
        pixel_size = read_raster_pixel_size(doc_path)
    return DocumentSpec(
        path=doc_path,
        format=fmt,
        pixel_size=pixel_size,
        physical_size_mm=physical_size_mm,
    )
