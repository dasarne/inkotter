"""Base device profile abstractions.

The goal of the device layer is to turn printer-specific protocol knowledge
into explicit data structures instead of scattering facts across the codebase.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BluetoothDiscoveryHints:
    """Hints for auto-discovery and later UI presentation."""

    name_patterns: tuple[str, ...] = ()
    rfcomm_channels: tuple[int, ...] = (1,)
    needs_root_hint: bool = True


@dataclass(frozen=True)
class RasterProfile:
    """Raster semantics required to materialize device-ready pages."""

    pixels_per_mm: float
    head_height_px: int
    bytes_per_column: int
    btbuf_data_offset: int
    page_width_px: int
    trim_probe_columns: int
    first_page_left_margin: int = 1
    later_page_left_margin: int = 1
    right_margin: int = 1
    multi_page_supported: bool = False
    fitted_content_height_px: int | None = None
    actual_size_single_page_max_width_mm: float | None = None
    single_page_extra_right_margin_px: int = 0
    final_page_extra_right_margin_px: int = 0
    physical_left_cut_margin_px: int = 0
    physical_top_inset_px: int = 0
    actual_size_svg_right_bleed_px: int = 0
    fit_to_label_print_x_offset_px: int = 0
    fit_to_label_svg_print_x_offset_px: int = 0


@dataclass(frozen=True)
class ProtocolProfile:
    """Protocol-layer facts for a printer family."""

    transport_family: str
    image_payload_cmd: str
    page_start_cmd: str
    print_trigger_cmd: str
    print_trigger_payload: bytes
    start_transfer_payload_length: int
    single_page_flags: int
    continue_page_flags: int
    final_page_flags: int
    compression: str = "lzma-alone"
    prelude_packets: tuple[tuple[str, bytes], ...] = ()


@dataclass(frozen=True)
class DeviceProfile:
    """Top-level printer profile consumed by the rest of the kernel."""

    key: str
    display_name: str
    marketing_name: str
    discovery: BluetoothDiscoveryHints
    raster: RasterProfile
    protocol: ProtocolProfile
    notes: tuple[str, ...] = field(default_factory=tuple)


def first_matching_name(profile: DeviceProfile, device_name: str) -> bool:
    """Return whether a visible Bluetooth device name matches the profile."""

    device_name_l = device_name.lower()
    return any(pattern.lower() in device_name_l for pattern in profile.discovery.name_patterns)
