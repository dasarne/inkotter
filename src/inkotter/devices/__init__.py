"""Device driver registry."""

from inkotter.devices.base import DeviceProfile
from inkotter.devices.katasymbol_e10 import KATASYMBOL_E10_PROFILE

ALL_DEVICE_PROFILES: tuple[DeviceProfile, ...] = (
    KATASYMBOL_E10_PROFILE,
)

__all__ = ["ALL_DEVICE_PROFILES", "KATASYMBOL_E10_PROFILE", "DeviceProfile"]
