from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from inkotter.transport.bluetooth import (
    BluetoothDevice,
    _run_capture,
    list_visible_devices,
    parse_bluetoothctl_devices,
)


class BluetoothTransportTests(unittest.TestCase):
    def test_parse_bluetoothctl_devices_extracts_entries(self) -> None:
        output = """Device AA:BB:CC:DD:EE:FF Printer One
Device 11:22:33:44:55:66 Another Device
invalid line
"""
        devices = parse_bluetoothctl_devices(output)
        self.assertEqual(
            devices,
            (
                BluetoothDevice(mac="AA:BB:CC:DD:EE:FF", name="Printer One"),
                BluetoothDevice(mac="11:22:33:44:55:66", name="Another Device"),
            ),
        )

    @patch("inkotter.transport.bluetooth.subprocess.run")
    def test_run_capture_timeout_raises_runtime_error(self, run_mock) -> None:
        run_mock.side_effect = subprocess.TimeoutExpired(cmd=["bluetoothctl"], timeout=1)
        with self.assertRaises(RuntimeError):
            _run_capture(["bluetoothctl", "devices"], timeout_s=1)

    @patch("inkotter.transport.bluetooth._run_capture")
    @patch("inkotter.transport.bluetooth.shutil.which")
    def test_list_visible_devices_raises_when_power_on_fails(self, which_mock, run_capture_mock) -> None:
        which_mock.return_value = "/usr/bin/bluetoothctl"
        run_capture_mock.return_value = (1, "", "power blocked")

        with self.assertRaisesRegex(RuntimeError, "power blocked"):
            list_visible_devices(scan_seconds=0)

    @patch("inkotter.transport.bluetooth._run_capture")
    @patch("inkotter.transport.bluetooth.shutil.which")
    def test_list_visible_devices_scans_when_initial_result_empty(self, which_mock, run_capture_mock) -> None:
        which_mock.return_value = "/usr/bin/bluetoothctl"
        run_capture_mock.side_effect = [
            (0, "", ""),
            (0, "", ""),
            (0, "", ""),
            (0, "Device AA:BB:CC:DD:EE:FF Katasymbol E10\n", ""),
        ]

        devices = list_visible_devices(scan_seconds=2)
        self.assertEqual(devices, (BluetoothDevice(mac="AA:BB:CC:DD:EE:FF", name="Katasymbol E10"),))


if __name__ == "__main__":
    unittest.main()
