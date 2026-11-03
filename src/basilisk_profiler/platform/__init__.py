# SPDX-License-Identifier: GPL-2.0-or-later
"""Platform-specific backends (HID access, foreground window, autostart)."""
import os
import sys


def hid_backend():
    """The HID module with the hidapi ``enumerate`` / ``device`` API for this platform.

    Linux: cython-hidapi's ``hidraw`` module (kernel hidraw). Never its ``hid`` module there:
    that is the libusb build, which detaches the kernel driver and takes the mouse away from
    the desktop. Windows: hidapi if installed, else the built-in hid.dll wrapper.
    """
    if sys.platform.startswith('linux'):
        import hidraw
        return hidraw
    try:
        import hid
        return hid
    except ImportError:
        if sys.platform != 'win32':
            raise
    from .win import hid as win_hid
    return win_hid


def conflicts() -> list[str]:
    """Warnings about other software that would also write the mouse."""
    if sys.platform.startswith('linux'):
        from .linux.conflicts import warnings
        return warnings()
    return []


def list_windows():
    """Visible top-level windows (WindowInfo list); empty where not supported yet."""
    if sys.platform == 'win32':
        from .win.foreground import list_windows as win_list
        return win_list()
    if sys.platform.startswith('linux'):
        from .linux.x11 import list_windows as x11_list
        return x11_list()
    return []


def autostart():
    """Module with is_enabled() / set_enabled(bool), or None where not supported yet."""
    if sys.platform == 'win32':
        from .win import autostart as win_autostart
        return win_autostart
    if sys.platform.startswith('linux'):
        from .linux import autostart as linux_autostart
        return linux_autostart
    return None


def foreground_watcher(callback):
    """Calls ``callback(WindowInfo)`` whenever the active window changes."""
    if sys.platform == 'win32':
        from .win.foreground import ForegroundWatcher
    else:
        from .linux.x11 import ForegroundWatcher
    return ForegroundWatcher(callback)


def event_reader(callback):
    """Reader of the dock's input events (DPI changes), or None: the service polls instead."""
    if sys.platform.startswith('linux'):
        from .linux.events import EventReader
        return EventReader(callback)
    return None


def cursor_overlay():
    """Shows a custom pointer image (show(CursorImage) / hide()), or None where unsupported."""
    if sys.platform.startswith('linux') and os.environ.get('DISPLAY'):
        from .linux.cursor import CursorOverlay
        return CursorOverlay()
    return None
