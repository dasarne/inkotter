"""Transport-layer primitives."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from inkotter.transport.bluetooth import BluetoothDevice
    from inkotter.transport.rfcomm import SendEvent

__all__ = [
    "BluetoothDevice",
    "SendEvent",
    "auto_select_device",
    "list_visible_devices",
    "send_packets",
]


def __getattr__(name: str):
    if name in {"BluetoothDevice", "auto_select_device", "list_visible_devices"}:
        from inkotter.transport import bluetooth as _bluetooth

        return getattr(_bluetooth, name)
    if name in {"SendEvent", "send_packets"}:
        from inkotter.transport import rfcomm as _rfcomm

        return getattr(_rfcomm, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
