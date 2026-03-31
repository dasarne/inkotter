"""Payload compression helpers."""

from __future__ import annotations

from dataclasses import dataclass
import lzma

from inkotter.protocol.btbuf import BtbufJob, BtbufPage


@dataclass(frozen=True)
class EncodedPage:
    index: int
    btbuf_page: BtbufPage
    lzma_stream: bytes
    aabb_payloads: tuple[bytes, ...]


@dataclass(frozen=True)
class EncodedJob:
    pages: tuple[EncodedPage, ...]


def chunk_lzma_for_aabb(lzma_stream: bytes) -> tuple[bytes, ...]:
    chunk_count = (len(lzma_stream) + 499) // 500
    payloads: list[bytes] = []
    for index in range(chunk_count):
        part = lzma_stream[index * 500 : (index + 1) * 500]
        payload = bytearray(504)
        payload[2] = index & 0xFF
        payload[3] = chunk_count & 0xFF
        payload[4 : 4 + len(part)] = part
        checksum = sum(payload[2:504]) & 0xFFFF
        payload[0:2] = checksum.to_bytes(2, "little")
        payloads.append(bytes(payload))
    return tuple(payloads)


def compress_btbuf_page(page: BtbufPage) -> EncodedPage:
    lzma_stream = lzma.compress(
        page.btbuf,
        format=lzma.FORMAT_ALONE,
        filters=[
            {
                "id": lzma.FILTER_LZMA1,
                "dict_size": 8192,
                "lc": 3,
                "lp": 0,
                "pb": 2,
                "mode": lzma.MODE_NORMAL,
                "nice_len": 128,
                "mf": lzma.MF_BT4,
            }
        ],
    )
    if len(lzma_stream) >= 13:
        lzma_stream = lzma_stream[:5] + len(page.btbuf).to_bytes(8, "little") + lzma_stream[13:]
    return EncodedPage(
        index=page.index,
        btbuf_page=page,
        lzma_stream=lzma_stream,
        aabb_payloads=chunk_lzma_for_aabb(lzma_stream),
    )


def compress_btbuf_job(job: BtbufJob) -> EncodedJob:
    return EncodedJob(pages=tuple(compress_btbuf_page(page) for page in job.pages))
