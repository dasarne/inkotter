"""Frame materialization."""

from __future__ import annotations

from dataclasses import dataclass

from inkotter.devices.base import DeviceProfile
from inkotter.protocol.lzma_codec import EncodedJob


@dataclass(frozen=True)
class FramedPacket:
    cmd_hex: str
    frame: bytes


def build_1001(cmd_hex: str, payload: bytes) -> bytes:
    command = int(cmd_hex, 16)
    length = 4 + len(payload)
    return (
        b"\x7e\x5a"
        + length.to_bytes(2, "little")
        + b"\x10\x01"
        + command.to_bytes(2, "big")
        + payload
    )


def build_1002_aabb(payload_504: bytes) -> bytes:
    if len(payload_504) != 504:
        raise ValueError("aabb payload must be 504 bytes")
    return b"\x7e\x5a" + (0x01FC).to_bytes(2, "little") + b"\x10\x02\xaa\xbb" + payload_504


def checksum_le(data: bytes) -> bytes:
    return (sum(data) & 0xFFFF).to_bytes(2, "little")


def payload_start_transfer(frame_size: int, frame_count: int) -> bytes:
    tail = b"\x00\x01" + frame_size.to_bytes(2, "little") + frame_count.to_bytes(2, "little")
    return checksum_le(tail) + tail


def build_grouped_image_frames(job: EncodedJob, device: DeviceProfile) -> tuple[FramedPacket, ...]:
    protocol = device.protocol
    framed: list[FramedPacket] = [
        FramedPacket(cmd_hex=cmd_hex, frame=build_1001(cmd_hex, payload))
        for cmd_hex, payload in protocol.prelude_packets
    ]
    for page in job.pages:
        start_payload = payload_start_transfer(
            protocol.start_transfer_payload_length,
            len(page.aabb_payloads),
        )
        framed.append(
            FramedPacket(
                cmd_hex=protocol.page_start_cmd,
                frame=build_1001(protocol.page_start_cmd, start_payload),
            )
        )
        for payload in page.aabb_payloads:
            framed.append(
                FramedPacket(
                    cmd_hex=protocol.image_payload_cmd,
                    frame=build_1002_aabb(payload),
                )
            )
        framed.append(
            FramedPacket(
                cmd_hex=protocol.print_trigger_cmd,
                frame=build_1001(protocol.print_trigger_cmd, protocol.print_trigger_payload),
            )
        )
    return tuple(framed)
