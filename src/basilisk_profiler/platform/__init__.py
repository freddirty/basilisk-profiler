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


def list_windows():
    """Visible top-level windows (WindowInfo list); empty where not supported yet."""
    if sys.platform == 'win32':
        from .win.foreground import list_windows as win_list
        return win_list()
    return []


def foreground_watcher(callback):
    """Calls ``callback(WindowInfo)`` whenever the active window changes."""
    if sys.platform == 'win32':
        from .win.foreground import ForegroundWatcher
    else:
        from .linux.x11 import ForegroundWatcher
    return ForegroundWatcher(callback)
