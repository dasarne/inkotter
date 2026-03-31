"""Bluetooth discovery and device selection."""

from __future__ import annotations

from dataclasses import dataclass
import re
import shutil
import subprocess

from inkotter.devices.base import DeviceProfile, first_matching_name


MAC_RE = re.compile(r"^([0-9A-F]{2}:){5}[0-9A-F]{2}$", re.IGNORECASE)


@dataclass(frozen=True)
class BluetoothDevice:
    mac: str
    name: str


def _run_capture(cmd: list[str]) -> tuple[int, str, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    return proc.returncode, proc.stdout, proc.stderr


def parse_bluetoothctl_devices(output: str) -> tuple[BluetoothDevice, ...]:
    devices: list[BluetoothDevice] = []
    for line in output.splitlines():
        line = line.strip()
        if not line.startswith("Device "):
            continue
        parts = line.split(maxsplit=2)
        if len(parts) < 3:
            continue
        mac = parts[1].upper()
        name = parts[2].strip()
        if MAC_RE.match(mac):
            devices.append(BluetoothDevice(mac=mac, name=name))
    return tuple(devices)


def list_visible_devices(scan_seconds: int = 0) -> tuple[BluetoothDevice, ...]:
    if shutil.which("bluetoothctl") is None:
        raise RuntimeError("bluetoothctl is not available on this system")
    _run_capture(["bluetoothctl", "power", "on"])
    rc, out, err = _run_capture(["bluetoothctl", "devices"])
    if rc != 0:
        raise RuntimeError((err or out).strip() or "bluetoothctl devices failed")
    devices = list(parse_bluetoothctl_devices(out))
    if devices or scan_seconds <= 0:
        return tuple(devices)
    _run_capture(["bluetoothctl", "--timeout", str(scan_seconds), "scan", "on"])
    rc, out, err = _run_capture(["bluetoothctl", "devices"])
    if rc != 0:
        raise RuntimeError((err or out).strip() or "bluetoothctl devices failed after scan")
    return parse_bluetoothctl_devices(out)


def auto_select_device(
    profile: DeviceProfile,
    *,
    scan_seconds: int = 4,
) -> BluetoothDevice:
    devices = list_visible_devices(scan_seconds=scan_seconds)
    if not devices:
        raise RuntimeError("no Bluetooth devices found")
    for device in devices:
        if first_matching_name(profile, device.name):
            return device
    names = ", ".join(device.name for device in devices)
    raise RuntimeError(f"no visible device matches {profile.display_name}; found: {names}")
