# SPDX-License-Identifier: GPL-2.0-or-later
"""Talk to the mouse over HID feature reports (hidapi; hidraw backend on Linux)."""
from __future__ import annotations

import sys
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol

from .. import (
    PID_BASILISK_V3_PRO_WIRED,
    PID_BASILISK_V3_PRO_WIRELESS,
    PID_MOUSE_DOCK_PRO,
    RAZER_VID,
)
from ..platform import hid_backend
from . import protocol as p

SUPPORTED_PIDS = (PID_MOUSE_DOCK_PRO, PID_BASILISK_V3_PRO_WIRED, PID_BASILISK_V3_PRO_WIRELESS)
CONTROL_INTERFACE = 0
REPORT_ID = 0x00

# Synapse reads the answer ~30-60 ms after writing; a busy device answers with status 0x01.
# After many flash writes (e.g. restoring all onboard slots) it can stay busy for seconds.
RESPONSE_DELAY = 0.03
BUSY_RETRIES = 150


class DeviceError(RuntimeError):
    pass


class HidHandle(Protocol):
    def send_feature_report(self, data: bytes | list[int]) -> int: ...
    def get_feature_report(self, report_id: int, length: int) -> list[int] | bytes: ...
    def close(self) -> None: ...


@dataclass(frozen=True)
class DeviceInfo:
    path: bytes
    product_id: int
    product: str
    interface: int
    usage_page: int
    usage: int


EnumerateFn = Callable[[int, int], Iterable[dict]]


def find_devices(enumerate_fn: EnumerateFn | None = None) -> list[DeviceInfo]:
    """Control interfaces of supported devices, the dock first."""
    if enumerate_fn is None:
        enumerate_fn = hid_backend().enumerate
    found = []
    for d in enumerate_fn(RAZER_VID, 0):
        if d['product_id'] in SUPPORTED_PIDS and d['interface_number'] == CONTROL_INTERFACE:
            found.append(DeviceInfo(
                path=d['path'], product_id=d['product_id'],
                product=d.get('product_string') or '', interface=d['interface_number'],
                usage_page=d.get('usage_page', 0), usage=d.get('usage', 0)))
    # On Windows every top-level collection is its own path; the mouse collection
    # (usage page 1, usage 2) is the one Synapse uses for feature reports.
    found.sort(key=lambda i: (SUPPORTED_PIDS.index(i.product_id),
                              (i.usage_page, i.usage) != (0x01, 0x02)))
    return found


class RazerDevice:
    def __init__(self, handle: HidHandle, info: DeviceInfo | None = None, *,
                 sleep: Callable[[float], None] = time.sleep):
        self.handle = handle
        self.info = info
        self._sleep = sleep

    @classmethod
    def open(cls, info: DeviceInfo | None = None) -> RazerDevice:
        hid = hid_backend()
        candidates = [info] if info else find_devices()
        if not candidates:
            raise DeviceError('no Razer Basilisk V3 Pro / Mouse Dock Pro found')
        errors = []
        for candidate in candidates:
            handle = hid.device()
            try:
                handle.open_path(candidate.path)
            except OSError as e:
                errors.append(f'{candidate.path!r}: {e}')
                continue
            device = cls(handle, candidate)
            try:
                device.transact(p.get_device_mode())
            except (OSError, DeviceError) as e:
                errors.append(f'{candidate.path!r}: {e}')
                handle.close()
                continue
            return device
        message = 'could not open a control interface:\n  ' + '\n  '.join(errors)
        if sys.platform.startswith('linux') and any('ermission' in e for e in errors):
            message += ('\nNo access to /dev/hidraw*: install the udev rule '
                        '(packaging/linux/70-basilisk-profiler.rules) and replug the dock.')
        raise DeviceError(message)

    def close(self) -> None:
        self.handle.close()

    def __enter__(self) -> RazerDevice:
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def transact(self, request: p.Report) -> p.Report:
        """Send one report and read the answer, retrying while the device is busy."""
        self.handle.send_feature_report(bytes([REPORT_ID]) + request.to_bytes())
        for _ in range(BUSY_RETRIES):
            self._sleep(RESPONSE_DELAY)
            raw = bytes(self.handle.get_feature_report(REPORT_ID, p.REPORT_LEN + 1))
            if len(raw) == p.REPORT_LEN + 1:
                raw = raw[1:]  # leading report id
            response = p.Report.from_bytes(raw)
            if response.status == p.Status.BUSY:
                continue
            if not response.matches(request):
                raise DeviceError(f'unexpected response {response.command} to {request.command}')
            if response.status != p.Status.SUCCESS:
                try:
                    status = p.Status(response.status).name
                except ValueError:
                    status = hex(response.status)
                raise DeviceError(f'command {request.command_class:02X}/{request.command_id:02X} '
                                  f'failed: {status}')
            return response
        raise DeviceError('device stayed busy')

    # --- convenience wrappers ---------------------------------------------------

    def device_mode(self) -> int:
        return p.parse_device_mode(self.transact(p.get_device_mode()))

    def set_device_mode(self, mode: p.DeviceMode) -> None:
        self.transact(p.set_device_mode(mode))

    def battery_percent(self) -> int:
        return p.parse_battery_percent(self.transact(p.get_battery_level()))

    def charging(self) -> bool:
        return p.parse_charging(self.transact(p.get_charging_status()))

    def dpi_stages(self, store: int = p.STORE_LIVE) -> p.DpiStages:
        return p.parse_dpi_stages(self.transact(p.get_dpi_stages(store)))

    def set_dpi_stages(self, stages: p.DpiStages) -> None:
        self.transact(p.set_dpi_stages(stages))

    def button(self, button: int, store: int = p.STORE_LIVE) -> p.ButtonMapping:
        return p.parse_button_mapping(self.transact(p.get_button_mapping(button, store)))

    def set_button(self, mapping: p.ButtonMapping) -> None:
        self.transact(p.set_button_mapping(mapping))

    def active_profile(self) -> int:
        return p.parse_active_profile(self.transact(p.get_active_profile()))

    def set_active_profile(self, store: int) -> None:
        self.transact(p.set_active_profile(store))

    def dock_effect(self, store: int = p.DOCK_STORE) -> p.DockEffect:
        return p.parse_dock_effect(self.transact(p.get_dock_effect(store)))

    def set_dock_effect(self, effect: p.DockEffect, store: int = p.DOCK_STORE) -> None:
        self.transact(p.set_dock_effect(effect, store))

    def firmware_version(self) -> str:
        return p.parse_firmware_version(self.transact(p.get_firmware_version()))
