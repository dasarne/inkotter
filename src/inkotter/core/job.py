"""High-level print job model."""

from __future__ import annotations

from dataclasses import dataclass

from inkotter.core.document import DocumentSpec
from inkotter.core.layout import LayoutPlan
from inkotter.devices.base import DeviceProfile


@dataclass(frozen=True)
class PrintJobRequest:
    document: DocumentSpec
    device: DeviceProfile
    layout: LayoutPlan
