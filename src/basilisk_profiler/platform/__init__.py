# SPDX-License-Identifier: GPL-2.0-or-later
"""Platform-specific backends (HID access, foreground window, autostart)."""
import sys


def hid_backend():
    """hidapi if installed, else Windows' built-in hid.dll."""
    try:
        import hid
        return hid
    except ImportError:
        if sys.platform != 'win32':
            raise
    from .win import hid as win_hid
    return win_hid
