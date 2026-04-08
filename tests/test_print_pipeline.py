from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw

from inkotter.core.document import DocumentFormat
from inkotter.core.service import build_physical_print_preview, build_preview_images, prepare_print_job
from inkotter.devices import KATASYMBOL_E10_PROFILE


def _visible_image(image: Image.Image, top_inset_px: int) -> Image.Image:
    grayscale = image.convert("L")
    if top_inset_px <= 0:
        return grayscale
    visible = Image.new("L", grayscale.size, color=255)
    cropped = grayscale.crop((0, top_inset_px, grayscale.width, grayscale.height))
    visible.paste(cropped, (0, 0))
    return visible


def _crop_left_margin(image: Image.Image, left_cut_margin_px: int) -> Image.Image:
    grayscale = image.convert("L")
    if left_cut_margin_px <= 0:
        return grayscale
    left = min(left_cut_margin_px, grayscale.width - 1)
    return grayscale.crop((left, 0, grayscale.width, grayscale.height))


def _materialize_strip(
    image: Image.Image,
    *,
    left_margin_px: int,
    right_margin_px: int,
    top_margin_px: int,
    bottom_margin_px: int,
) -> Image.Image:
    strip = Image.new(
        "L",
        (left_margin_px + image.width + right_margin_px, top_margin_px + image.height + bottom_margin_px),
        color=255,
    )
    strip.paste(image, (left_margin_px, top_margin_px))
    return strip


def _non_white_bbox(image: Image.Image):
    return ImageChops.invert(image.convert("L")).getbbox()


def _reconstruct_monochrome_from_btbuf(job) -> Image.Image:
    image = Image.new("1", (job.btbuf_job.canvas_width_px, job.btbuf_job.head_height_px), color=1)
    x_offset = 0
    bytes_per_column = job.device.raster.bytes_per_column

    for page in job.btbuf_job.pages:
        for x in range(page.width_px):
            base = x * bytes_per_column
            for by in range(bytes_per_column):
                value = page.payload[base + by]
                for bit in range(8):
                    y = (by * 8) + bit
                    if y >= job.btbuf_job.head_height_px:
                        continue
                    if value & (1 << bit):
                        image.putpixel((x_offset + x, y), 0)
        x_offset += page.width_px

    return image


class PrintPipelineTests(unittest.TestCase):
    def test_preview_uses_same_printer_ready_geometry_for_raster_and_svg(self) -> None:
        for suffix in ("png", "svg"):
            with self.subTest(document_type=suffix):
                with tempfile.TemporaryDirectory() as tmpdir:
                    document_path = self._create_fixture(Path(tmpdir), suffix)
                    job = prepare_print_job(document_path, KATASYMBOL_E10_PROFILE)
                    previews = build_preview_images(job)

                    expected_graphic = _visible_image(
                        job.preview_canvas.grayscale_image,
                        job.device.raster.visible_area_top_inset_px(),
                    )
                    expected_graphic = _crop_left_margin(
                        expected_graphic,
                        job.device.raster.visible_area_left_cut_margin_px(),
                    )
                    expected_physical = _visible_image(
                        job.printer_ready_canvas.monochrome_image,
                        job.device.raster.visible_area_top_inset_px(),
                    )
                    expected_physical = _crop_left_margin(
                        expected_physical,
                        job.device.raster.visible_area_left_cut_margin_px(),
                    )
                    expected_left_margin = job.device.raster.protocol_left_margin_px(0)
                    expected_right_margin = job.device.raster.preview_margin_right_px()
                    expected_top_margin = job.device.raster.preview_margin_top_px()
                    expected_bottom_margin = job.device.raster.preview_margin_bottom_px()
                    expected_left_margin = job.device.raster.preview_margin_left_px()
                    expected_graphic = _materialize_strip(
                        expected_graphic,
                        left_margin_px=expected_left_margin,
                        right_margin_px=expected_right_margin,
                        top_margin_px=expected_top_margin,
                        bottom_margin_px=expected_bottom_margin,
                    )
                    expected_physical = _materialize_strip(
                        expected_physical,
                        left_margin_px=expected_left_margin,
                        right_margin_px=expected_right_margin,
                        top_margin_px=expected_top_margin,
                        bottom_margin_px=expected_bottom_margin,
                    )

                    self.assertEqual(previews.graphic_image.size, previews.physical_print_image.size)
                    self.assertEqual(previews.graphic_image.tobytes(), expected_graphic.tobytes())
                    self.assertEqual(previews.physical_print_image.tobytes(), expected_physical.tobytes())
                    self.assertEqual(
                        build_physical_print_preview(job).tobytes(),
                        previews.physical_print_image.tobytes(),
                    )

    def test_physical_preview_uses_same_internal_placement_as_preview_canvas(self) -> None:
        for suffix in ("png", "svg"):
            with self.subTest(document_type=suffix):
                with tempfile.TemporaryDirectory() as tmpdir:
                    document_path = self._create_fixture(Path(tmpdir), suffix)
                    job = prepare_print_job(document_path, KATASYMBOL_E10_PROFILE)
                    previews = build_preview_images(job)

                    self.assertEqual(job.preview_canvas.plan.placement.x_px, job.printer_ready_canvas.plan.placement.x_px)
                    self.assertEqual(
                        _non_white_bbox(previews.physical_print_image),
                        _non_white_bbox(
                            _materialize_strip(
                                _crop_left_margin(
                                    _visible_image(
                                        job.printer_ready_canvas.monochrome_image,
                                        job.device.raster.visible_area_top_inset_px(),
                                    ),
                                    job.device.raster.visible_area_left_cut_margin_px(),
                                ),
                                left_margin_px=job.device.raster.preview_margin_left_px(),
                                right_margin_px=job.device.raster.preview_margin_right_px(),
                                top_margin_px=job.device.raster.preview_margin_top_px(),
                                bottom_margin_px=job.device.raster.preview_margin_bottom_px(),
                            )
                        ),
                    )

    def test_btbuf_payload_reconstructs_exact_printer_ready_monochrome_canvas(self) -> None:
        for suffix in ("png", "svg"):
            with self.subTest(document_type=suffix):
                with tempfile.TemporaryDirectory() as tmpdir:
                    document_path = self._create_fixture(Path(tmpdir), suffix)
                    job = prepare_print_job(document_path, KATASYMBOL_E10_PROFILE)

                    self.assertEqual(job.btbuf_job.page_count, 1)
                    self.assertEqual(job.raster.page_spans[0].trim_left_px, 0)

                    reconstructed = _reconstruct_monochrome_from_btbuf(job)
                    self.assertEqual(reconstructed.tobytes(), job.printer_ready_canvas.monochrome_image.tobytes())
                    self.assertEqual(job.btbuf_job.pages[0].btbuf[8:10], b"\x00\x00")
                    self.assertEqual(
                        int.from_bytes(job.btbuf_job.pages[0].btbuf[10:12], "little"),
                        KATASYMBOL_E10_PROFILE.raster.protocol_right_margin_px(is_final=True, total_pages=1),
                    )

    def test_single_page_printer_ready_content_is_horizontally_balanced_in_visible_area(self) -> None:
        for suffix in ("png",):
            with self.subTest(document_type=suffix):
                with tempfile.TemporaryDirectory() as tmpdir:
                    document_path = self._create_fixture(Path(tmpdir), suffix)
                    job = prepare_print_job(document_path, KATASYMBOL_E10_PROFILE)

                    placement = job.preview_canvas.plan.placement
                    left_margin = placement.x_px - job.device.raster.visible_area_left_cut_margin_px()
                    right_margin = job.preview_canvas.plan.canvas.width_px - (placement.x_px + placement.width_px)
                    self.assertEqual(left_margin, right_margin)

    def test_svg_fit_to_label_does_not_shift_printer_ready_canvas(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            document_path = self._create_fixture(Path(tmpdir), "svg")
            job = prepare_print_job(document_path, KATASYMBOL_E10_PROFILE)
            self.assertEqual(
                job.printer_ready_canvas.plan.placement.x_px,
                job.preview_canvas.plan.placement.x_px
                + KATASYMBOL_E10_PROFILE.raster.fit_to_label_output_x_offset_px(DocumentFormat.SVG),
            )

    def test_raster_fit_to_label_does_not_shift_printer_ready_canvas(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            document_path = self._create_fixture(Path(tmpdir), "png")
            job = prepare_print_job(document_path, KATASYMBOL_E10_PROFILE)
            self.assertEqual(
                job.printer_ready_canvas.plan.placement.x_px,
                job.preview_canvas.plan.placement.x_px
                + KATASYMBOL_E10_PROFILE.raster.fit_to_label_output_x_offset_px(DocumentFormat.PNG),
            )

    def test_raster_profile_helpers_expose_effect_classes_explicitly(self) -> None:
        raster = KATASYMBOL_E10_PROFILE.raster
        self.assertEqual(raster.visible_area_left_cut_margin_px(), 0)
        self.assertEqual(raster.visible_area_top_inset_px(), 1)
        self.assertEqual(raster.actual_size_svg_bleed_px(), 12)
        self.assertEqual(raster.single_page_visible_width_px(DocumentFormat.SVG), raster.page_width_px)
        self.assertEqual(raster.single_page_visible_width_px(DocumentFormat.PNG), raster.page_width_px - 32)
        self.assertEqual(raster.fit_to_label_output_x_offset_px(DocumentFormat.PNG), 0)
        self.assertEqual(raster.fit_to_label_output_x_offset_px(DocumentFormat.SVG), 0)
        self.assertEqual(raster.preview_margin_left_px(), 37)
        self.assertEqual(raster.preview_margin_right_px(), 37)
        self.assertEqual(raster.preview_margin_top_px(), 14)
        self.assertEqual(raster.preview_margin_bottom_px(), 14)
        self.assertEqual(raster.protocol_left_margin_px(0), 0)
        self.assertEqual(raster.protocol_left_margin_px(1), 0)
        self.assertEqual(raster.protocol_right_margin_px(is_final=True, total_pages=1), 33)
        self.assertEqual(raster.protocol_right_margin_px(is_final=False, total_pages=2), 1)
        self.assertEqual(raster.protocol_right_margin_px(is_final=True, total_pages=2), 33)

    def _create_fixture(self, directory: Path, suffix: str) -> Path:
        if suffix == "png":
            path = directory / "fixture.png"
            image = Image.new("L", (260, 72), color=255)
            draw = ImageDraw.Draw(image)
            draw.ellipse((6, 8, 58, 60), fill=0)
            draw.rounded_rectangle((82, 14, 98, 54), radius=4, fill=0)
            draw.rounded_rectangle((110, 6, 126, 66), radius=4, fill=0)
            draw.rounded_rectangle((138, 18, 154, 50), radius=4, fill=0)
            draw.rounded_rectangle((168, 10, 184, 58), radius=4, fill=0)
            draw.rounded_rectangle((198, 14, 214, 54), radius=4, fill=0)
            draw.rounded_rectangle((226, 8, 242, 62), radius=4, fill=0)
            image.save(path)
            return path

        path = directory / "fixture.svg"
        path.write_text(
            """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="35mm" height="10mm" viewBox="0 0 35 10">
  <rect x="0.5" y="0.5" width="34" height="9" fill="white" stroke="black" stroke-width="0.4"/>
  <circle cx="17.5" cy="5" r="2.8" fill="white" stroke="black" stroke-width="0.35"/>
  <line x1="0.5" y1="0.5" x2="34.5" y2="9.5" stroke="black" stroke-width="0.3"/>
  <line x1="34.5" y1="0.5" x2="0.5" y2="9.5" stroke="black" stroke-width="0.3"/>
</svg>
""",
            encoding="utf-8",
        )
        return path


if __name__ == "__main__":
    unittest.main()
