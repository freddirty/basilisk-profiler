# SPDX-License-Identifier: GPL-2.0-or-later
"""Start with Windows: a value under HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run.

The installer writes the same value when its "start with Windows" task is chosen.
"""
from __future__ import annotations

import sys
import winreg

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
VALUE_NAME = 'BasiliskProfiler'


def command() -> str:
    """How to start the tray service with this installation."""
    if getattr(sys, 'frozen', False):
        return f'"{sys.executable}"'
    pythonw = sys.executable.replace('python.exe', 'pythonw.exe')
    return f'"{pythonw}" -m basilisk_profiler.daemon'


def is_enabled() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY) as key:
            winreg.QueryValueEx(key, VALUE_NAME)
            return True
    except OSError:
        return False


def set_enabled(enabled: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if enabled:
            winreg.SetValueEx(key, VALUE_NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(key, VALUE_NAME)
            except FileNotFoundError:
                pass
