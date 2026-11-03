# SPDX-License-Identifier: GPL-2.0-or-later
"""Input reports the dock sends on its interface 1 (report id 5), e.g. on a DPI change.

Seen on the Mouse Dock Pro (2026-11-03, see docs/basilisk-v3-pro-protocol.md):
  05 02 XX XX YY YY   DPI changed (big-endian X / Y), sent on every DPI button press
  05 31 LL ...        battery level, 0-255
  05 09 SS 01         connection / wake state
"""
from __future__ import annotations

from dataclasses import dataclass

EVENT_INTERFACE = 1
EVENT_REPORT_ID = 0x05


@dataclass(frozen=True)
class DpiChanged:
    x: int
    y: int


@dataclass(frozen=True)
class BatteryLevel:
    percent: int


DeviceEvent = DpiChanged | BatteryLevel


def parse_event(data: bytes) -> DeviceEvent | None:
    if len(data) < 3 or data[0] != EVENT_REPORT_ID:
        return None
    kind = data[1]
    if kind == 0x02 and len(data) >= 6:
        x = int.from_bytes(data[2:4], 'big')
        y = int.from_bytes(data[4:6], 'big')
        return DpiChanged(x, y) if x else None
    if kind == 0x31:
        return BatteryLevel(round(data[2] * 100 / 255))
    return None
