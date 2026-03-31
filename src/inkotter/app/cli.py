"""Minimal CLI for the first InkOtter kernel."""

from __future__ import annotations

import argparse

from inkotter.core import prepare_print_job, summarize_print_job
from inkotter.devices import KATASYMBOL_E10_PROFILE
from inkotter.devices.base import first_matching_name
from inkotter.transport import auto_select_device, list_visible_devices, send_packets



def main() -> None:
    parser = argparse.ArgumentParser(description="InkOtter minimal Katasymbol E10 printer CLI")
    parser.add_argument("image", nargs="?", help="SVG/PNG/JPG to print")
    parser.add_argument("--no-scale", action="store_true", help="print SVGs in actual document size")
    parser.add_argument("--mac", default="", help="printer Bluetooth MAC; auto-discovered when omitted")
    parser.add_argument("--channel", type=int, default=1, help="RFCOMM channel")
    parser.add_argument("--scan-seconds", type=int, default=4, help="Bluetooth scan time when auto-discovering")
    parser.add_argument("--list-printers", action="store_true", help="list visible Bluetooth devices and exit")
    parser.add_argument("--dry-run", action="store_true", help="build the print job without sending it")
    args = parser.parse_args()

    if args.list_printers:
        try:
            devices = list_visible_devices(scan_seconds=args.scan_seconds)
        except RuntimeError as exc:
            raise SystemExit(f"Bluetooth discovery failed: {exc}") from exc
        for device in devices:
            if first_matching_name(KATASYMBOL_E10_PROFILE, device.name):
                print(f"* {device.mac}  {device.name}  [Katasymbol E10 candidate]")
            else:
                print(f"  {device.mac}  {device.name}")
        return

    if not args.image:
        parser.error("image is required unless --list-printers is used")

    job = prepare_print_job(
        args.image,
        KATASYMBOL_E10_PROFILE,
        no_scale=args.no_scale,
    )
    summary = summarize_print_job(job)

    print(f"Device: {summary.device_name}")
    print(f"Document: {summary.document_path}")
    print(f"Layout: {summary.layout_mode}")
    print(f"Canvas: {summary.canvas_width_px}x{summary.canvas_height_px}")
    print(f"Pages: {summary.page_count}")

    if args.dry_run:
        print(f"Frames: {summary.frame_count}")
        print(f"Chunks per page: {list(summary.chunks_per_page)}")
        return

    target_mac = args.mac.strip().upper()
    if not target_mac:
        try:
            selected = auto_select_device(KATASYMBOL_E10_PROFILE, scan_seconds=args.scan_seconds)
        except RuntimeError as exc:
            raise SystemExit(f"Printer auto-discovery failed: {exc}") from exc
        target_mac = selected.mac
        print(f"Printer: {selected.name} ({selected.mac})")
    else:
        print(f"Printer: {target_mac}")

    try:
        events = send_packets(
            mac=target_mac,
            channel=args.channel,
            packets=job.frames,
        )
    except PermissionError:
        raise SystemExit("RFCOMM open/connect was denied; retry as a user with Bluetooth access or with sudo")
    except OSError as exc:
        raise SystemExit(f"RFCOMM send failed: {exc}") from exc

    print(f"Sent {len(events)} frame(s)")


if __name__ == "__main__":
    main()
