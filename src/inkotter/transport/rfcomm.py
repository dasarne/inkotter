"""RFCOMM transport implementation."""

from __future__ import annotations

from dataclasses import dataclass
import socket
import time

from inkotter.protocol.frames import FramedPacket


@dataclass(frozen=True)
class SendEvent:
    index: int
    cmd_hex: str
    tx_len: int
    rx_hex: str


def send_packets(
    *,
    mac: str,
    channel: int,
    packets: tuple[FramedPacket, ...],
    connect_timeout_s: float = 5.0,
    recv_timeout_s: float = 0.2,
    delay_ms: int = 30,
) -> tuple[SendEvent, ...]:
    sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
    sock.settimeout(connect_timeout_s)
    sock.connect((mac, channel))
    sock.settimeout(recv_timeout_s)
    events: list[SendEvent] = []
    try:
        for index, packet in enumerate(packets):
            sock.sendall(packet.frame)
            rx_hex = ""
            try:
                response = sock.recv(2048)
                if response == b"":
                    raise OSError("remote closed RFCOMM socket")
                rx_hex = response.hex()
            except socket.timeout:
                rx_hex = ""
            events.append(
                SendEvent(
                    index=index,
                    cmd_hex=packet.cmd_hex,
                    tx_len=len(packet.frame),
                    rx_hex=rx_hex,
                )
            )
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)
    finally:
        sock.close()
    return tuple(events)
