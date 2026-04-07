"""Protocol-neutral render contract and first monochrome renderer."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET

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
    FLOYD_STEINBERG = "floyd-steinberg"


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


def build_render_plan(
    document: DocumentSpec,
    layout: LayoutPlan,
    raster: RasterPlan,
    *,
    monochrome_strategy: MonochromeStrategy = MonochromeStrategy.THRESHOLD,
    monochrome_threshold: int = DEFAULT_MONOCHROME_THRESHOLD,
) -> RenderPlan:
    source = _source_raster_extent(document, layout)
    canvas = PixelExtent(width_px=raster.target_canvas_width_px, height_px=raster.head_height_px)
    top_inset_px = max(0, raster.physical_top_inset_px)
    usable_height_px = max(1, canvas.height_px - top_inset_px)

    if layout.mode == LayoutMode.FIT_TO_LABEL:
        target_height_px = min(raster.fit_to_content_height_px or raster.head_height_px, usable_height_px)
        target_width_px = min(raster.fit_to_content_width_px or canvas.width_px, canvas.width_px)
        placed = _fit_scaled_extent(source, target_width_px, target_height_px)
        placement = PixelPlacement(
            x_px=0 if raster.place_top_left else max(0, (canvas.width_px - placed.width_px) // 2),
            y_px=top_inset_px + max(0, (usable_height_px - placed.height_px) // 2),
            width_px=placed.width_px,
            height_px=placed.height_px,
        )
        return RenderPlan(
            canvas=canvas,
            source_raster=source,
            placement=placement,
            svg_pixels_per_mm=layout.svg_pixels_per_mm,
            resample=RenderResample.NEAREST,
            monochrome_strategy=monochrome_strategy,
            monochrome_threshold=monochrome_threshold,
            reason=layout.reason,
        )

    placement = PixelPlacement(
        x_px=0 if raster.place_top_left else max(0, (canvas.width_px - source.width_px) // 2),
        y_px=top_inset_px if raster.place_top_left else top_inset_px + max(0, (usable_height_px - source.height_px) // 2),
        width_px=min(source.width_px, canvas.width_px),
        height_px=min(source.height_px, usable_height_px),
    )
    return RenderPlan(
        canvas=canvas,
        source_raster=source,
        placement=placement,
        svg_pixels_per_mm=layout.svg_pixels_per_mm,
        resample=RenderResample.NEAREST,
        monochrome_strategy=monochrome_strategy,
        monochrome_threshold=monochrome_threshold,
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
    svg_bytes = _svg_bytes_for_render(document, plan)
    render_kwargs = {
        "output_width": plan.source_raster.width_px,
        "output_height": plan.source_raster.height_px,
        "background_color": "white",
    }
    if svg_bytes is None:
        png_bytes = cairosvg.svg2png(url=str(document.path), **render_kwargs)
    else:
        png_bytes = cairosvg.svg2png(bytestring=svg_bytes, **render_kwargs)
    with Image.open(BytesIO(png_bytes)) as im:
        return im.convert("L")


def _render_svg_with_inkscape(document: DocumentSpec, plan: RenderPlan) -> Image.Image:
    with tempfile.TemporaryDirectory(prefix="inkotter-svg-") as tmpdir:
        output = Path(tmpdir) / "render.png"
        svg_input = document.path
        svg_bytes = _svg_bytes_for_render(document, plan)
        if svg_bytes is not None:
            svg_input = Path(tmpdir) / "render.svg"
            svg_input.write_bytes(svg_bytes)
        cmd = [
            "inkscape",
            str(svg_input),
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
    # Prefer Inkscape when available because text shaping and font resolution
    # match the interactive editor much more closely than CairoSVG for
    # real-world label artwork.
    if shutil.which("inkscape") is not None:
        return _render_svg_with_inkscape(document, plan)
    if cairosvg is not None:
        return _render_svg_with_cairosvg(document, plan)
    raise RuntimeError("SVG rendering requires either inkscape or CairoSVG")


def _svg_bytes_for_render(document: DocumentSpec, plan: RenderPlan) -> bytes | None:
    if document.physical_size_mm is None:
        return None
    base_width_px = max(1, round(document.physical_size_mm.width_mm * plan.svg_pixels_per_mm))
    bleed_px = plan.source_raster.width_px - base_width_px
    if bleed_px <= 0:
        return None

    try:
        root = ET.fromstring(document.path.read_text())
    except Exception:
        return None

    bleed_mm = bleed_px / plan.svg_pixels_per_mm
    root.attrib["width"] = f"{document.physical_size_mm.width_mm + bleed_mm:.6f}mm"
    root.attrib["overflow"] = "visible"
    root.attrib.setdefault("height", f"{document.physical_size_mm.height_mm:.6f}mm")

    view_box = root.attrib.get("viewBox")
    if view_box:
        parts = view_box.replace(",", " ").split()
        if len(parts) == 4:
            try:
                min_x, min_y, width, height = (float(part) for part in parts)
            except ValueError:
                pass
            else:
                bleed_user = width * (bleed_px / base_width_px)
                root.attrib["viewBox"] = f"{min_x:g} {min_y:g} {width + bleed_user:g} {height:g}"
    else:
        root.attrib["viewBox"] = (
            f"0 0 "
            f"{document.physical_size_mm.width_mm + bleed_mm:.6f} "
            f"{document.physical_size_mm.height_mm:.6f}"
        )

    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


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


def _prepare_source_for_placement(source: Image.Image, plan: RenderPlan) -> Image.Image:
    placement = plan.placement
    if source.width == placement.width_px and source.height == placement.height_px:
        return source

    if source.width >= placement.width_px and source.height >= placement.height_px:
        # Fit-to-label intentionally scales the rendered source into the page slot.
        if placement.width_px < plan.source_raster.width_px or placement.height_px < plan.source_raster.height_px:
            return source.resize(
                (placement.width_px, placement.height_px),
                resample=_pil_resample(plan.resample),
            )
        return source.crop((0, 0, placement.width_px, placement.height_px))

    return source.resize(
        (placement.width_px, placement.height_px),
        resample=_pil_resample(plan.resample),
    )


def _threshold_to_monochrome(image: Image.Image, threshold: int) -> Image.Image:
    grayscale = image.convert("L")
    return grayscale.point(lambda value: 0 if value < threshold else 255, mode="1")


def _floyd_steinberg_to_monochrome(image: Image.Image) -> Image.Image:
    grayscale = image.convert("L")
    return grayscale.convert("1", dither=Image.Dither.FLOYDSTEINBERG)


def render_document_to_monochrome_canvas(document: DocumentSpec, plan: RenderPlan) -> RenderedMonochromeCanvas:
    source = _render_source_to_grayscale(document, plan)
    placed_source = _prepare_source_for_placement(source, plan)

    grayscale_canvas = Image.new("L", (plan.canvas.width_px, plan.canvas.height_px), color=255)
    grayscale_canvas.paste(placed_source, (plan.placement.x_px, plan.placement.y_px))

    if plan.monochrome_strategy == MonochromeStrategy.THRESHOLD:
        monochrome_canvas = _threshold_to_monochrome(grayscale_canvas, plan.monochrome_threshold)
    elif plan.monochrome_strategy == MonochromeStrategy.FLOYD_STEINBERG:
        monochrome_canvas = _floyd_steinberg_to_monochrome(grayscale_canvas)
    else:
        raise ValueError(f"unsupported monochrome strategy: {plan.monochrome_strategy}")
    return RenderedMonochromeCanvas(
        grayscale_image=grayscale_canvas,
        monochrome_image=monochrome_canvas,
        plan=plan,
    )
