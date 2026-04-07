"""btbuf construction from canonical monochrome canvases."""

from __future__ import annotations

from dataclasses import dataclass

from PIL import Image

from inkotter.core.raster import RasterPlan
from inkotter.core.render import RenderedMonochromeCanvas
from inkotter.devices.base import DeviceProfile


@dataclass(frozen=True)
class BtbufPage:
    index: int
    width_px: int
    no_zero_index: int
    page_flags: int
    data_offset: int
    payload: bytes
    btbuf: bytes


@dataclass(frozen=True)
class BtbufJob:
    canvas_width_px: int
    head_height_px: int
    page_count: int
    pages: tuple[BtbufPage, ...]


def _pack_canvas_columns_lsb(
    canvas: Image.Image,
    *,
    bytes_per_column: int,
    x_start: int,
    x_stop: int,
) -> bytes:
    width, height = canvas.size
    if x_start < 0 or x_stop < x_start or x_stop > width:
        raise ValueError("invalid x range for canvas packing")
    mono = canvas.convert("1")
    px = mono.load()
    data = bytearray((x_stop - x_start) * bytes_per_column)
    for x in range(x_start, x_stop):
        for by in range(bytes_per_column):
            value = 0
            for bit in range(8):
                y = (by * 8) + bit
                if y >= height:
                    continue
                if px[x, y] == 0:
                    value |= 1 << bit
            data[((x - x_start) * bytes_per_column) + by] = value
    return bytes(data)


def _compute_t15_checksum(btbuf: bytearray, used_length: int) -> int:
    checksum = sum(btbuf[2:14])
    for k in range(1, (used_length // 256) + 1):
        checksum += btbuf[(k * 256) - 1]
    return checksum & 0xFFFF


def _build_btbuf_page(
    *,
    page_data: bytes,
    width_px: int,
    bytes_per_column: int,
    no_zero_index: int,
    page_flags: int,
    data_offset: int,
    left_margin: int,
    right_margin: int,
) -> bytes:
    btbuf = bytearray(4000)
    btbuf[2:4] = page_flags.to_bytes(2, "little")
    btbuf[4:6] = width_px.to_bytes(2, "little")
    btbuf[6] = bytes_per_column
    btbuf[8:10] = left_margin.to_bytes(2, "little")
    btbuf[10:12] = right_margin.to_bytes(2, "little")
    btbuf[12] = no_zero_index & 0xFF
    btbuf[13] = 0
    btbuf[data_offset : data_offset + len(page_data)] = page_data
    used_length = (width_px * bytes_per_column) + data_offset
    btbuf[0:2] = _compute_t15_checksum(btbuf, used_length).to_bytes(2, "little")
    return bytes(btbuf)


def build_t15_btbuf_job(
    rendered: RenderedMonochromeCanvas,
    raster_plan: RasterPlan,
    device: DeviceProfile,
) -> BtbufJob:
    raster = device.raster
    protocol = device.protocol
    pages: list[BtbufPage] = []

    total_pages = len(raster_plan.page_spans)
    for span in raster_plan.page_spans:
        effective_start_x = span.start_x_px + span.trim_left_px
        effective_width_px = max(0, span.width_px - span.trim_left_px)
        if total_pages == 1:
            page_flags = protocol.single_page_flags
        else:
            page_flags = protocol.final_page_flags if span.is_final else protocol.continue_page_flags
        right_margin = raster.right_margin
        if total_pages > 1 and span.is_final:
            right_margin += raster.final_page_extra_right_margin_px
        page_data = _pack_canvas_columns_lsb(
            rendered.monochrome_image,
            bytes_per_column=raster.bytes_per_column,
            x_start=effective_start_x,
            x_stop=effective_start_x + effective_width_px,
        )
        btbuf = _build_btbuf_page(
            page_data=page_data,
            width_px=effective_width_px,
            bytes_per_column=raster.bytes_per_column,
            no_zero_index=span.trim_left_px,
            page_flags=page_flags,
            data_offset=raster.btbuf_data_offset,
            left_margin=raster.first_page_left_margin if span.index == 0 else raster.later_page_left_margin,
            right_margin=right_margin,
        )
        pages.append(
            BtbufPage(
                index=span.index,
                width_px=effective_width_px,
                no_zero_index=span.trim_left_px,
                page_flags=page_flags,
                data_offset=raster.btbuf_data_offset,
                payload=page_data,
                btbuf=btbuf,
            )
        )

    return BtbufJob(
        canvas_width_px=rendered.plan.canvas.width_px,
        head_height_px=rendered.plan.canvas.height_px,
        page_count=len(pages),
        pages=tuple(pages),
    )
