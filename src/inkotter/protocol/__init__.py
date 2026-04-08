"""Protocol-layer primitives."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from inkotter.protocol.btbuf import BtbufJob, BtbufPage
    from inkotter.protocol.frames import FramedPacket
    from inkotter.protocol.lzma_codec import EncodedJob, EncodedPage

__all__ = [
    "BtbufJob",
    "BtbufPage",
    "EncodedJob",
    "EncodedPage",
    "FramedPacket",
    "build_t15_btbuf_job",
    "compress_btbuf_job",
    "build_grouped_image_frames",
]


def __getattr__(name: str):
    if name in {"BtbufJob", "BtbufPage", "build_t15_btbuf_job"}:
        from inkotter.protocol import btbuf as _btbuf

        return getattr(_btbuf, name)
    if name in {"FramedPacket", "build_grouped_image_frames"}:
        from inkotter.protocol import frames as _frames

        return getattr(_frames, name)
    if name in {"EncodedJob", "EncodedPage", "compress_btbuf_job"}:
        from inkotter.protocol import lzma_codec as _lzma_codec

        return getattr(_lzma_codec, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
