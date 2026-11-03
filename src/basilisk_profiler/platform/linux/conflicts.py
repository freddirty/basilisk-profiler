# SPDX-License-Identifier: GPL-2.0-or-later
"""Other software on Linux that would fight us for the mouse (OpenRazer)."""
from __future__ import annotations

from pathlib import Path

from ... import (
    PID_BASILISK_V3_PRO_WIRED,
    PID_BASILISK_V3_PRO_WIRELESS,
    PID_MOUSE_DOCK_PRO,
    RAZER_VID,
)

_PIDS = (PID_MOUSE_DOCK_PRO, PID_BASILISK_V3_PRO_WIRED, PID_BASILISK_V3_PRO_WIRELESS)


def _bound_to_openrazer(sys_root: Path) -> bool:
    """True if OpenRazer's razermouse kernel driver has claimed one of our devices."""
    driver = sys_root / 'bus' / 'hid' / 'drivers' / 'razermouse'
    if not driver.is_dir():
        return False
    for entry in driver.iterdir():
        # HID device names look like 0003:1532:00A4.0007
        parts = entry.name.split(':')
        if len(parts) != 3:
            continue
        try:
            vid, pid = int(parts[1], 16), int(parts[2].split('.')[0], 16)
        except ValueError:
            continue
        if vid == RAZER_VID and pid in _PIDS:
            return True
    return False


def _openrazer_daemon_running(proc_root: Path) -> bool:
    for comm in proc_root.glob('[0-9]*/comm'):
        try:
            if comm.read_text().strip() == 'openrazer-daemo':  # comm is cut at 15 chars
                return True
        except OSError:
            continue
    return False


def warnings(sys_root: Path = Path('/sys'), proc_root: Path = Path('/proc')) -> list[str]:
    found = []
    if _bound_to_openrazer(sys_root):
        found.append('the OpenRazer kernel driver (razermouse) owns the mouse; settings written '
                     'here may be overwritten. Unload it: sudo modprobe -r razermouse')
    if _openrazer_daemon_running(proc_root):
        found.append('openrazer-daemon is running and may overwrite settings written here; '
                     'stop it: systemctl --user stop openrazer-daemon')
    return found
