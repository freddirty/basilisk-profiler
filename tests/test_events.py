# SPDX-License-Identifier: GPL-2.0-or-later
from basilisk_profiler.core.events import BatteryLevel, DpiChanged, SlotChanged, parse_event


def test_dpi_event_from_capture():
    raw = bytes.fromhex('05 02 0c 80 0c 80 00 00 00 00 00 00 00 00 00 00')
    assert parse_event(raw) == DpiChanged(3200, 3200)


def test_battery_event_from_capture():
    raw = bytes.fromhex('05 31 cd 00 00 01 00 00')
    assert parse_event(raw) == BatteryLevel(80)


def test_slot_event_from_probe():
    raw = bytes.fromhex('05 39 00 00 00 00 00 00 00 00 00 00 00 00 00 00')
    assert parse_event(raw) == SlotChanged()


def test_other_reports_ignored():
    assert parse_event(bytes.fromhex('05 09 02 01 00 00')) is None
    assert parse_event(bytes.fromhex('02 00 00 00 00 00')) is None
    assert parse_event(b'') is None
