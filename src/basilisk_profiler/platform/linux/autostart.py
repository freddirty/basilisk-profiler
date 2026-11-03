# SPDX-License-Identifier: GPL-2.0-or-later
"""Start at login: an XDG autostart entry (~/.config/autostart/basilisk-profiler.desktop).

Cinnamon, GNOME, KDE and XFCE all honour it; deleting the file switches it off.
"""
from __future__ import annotations

import os
import shlex
import sys
from pathlib import Path

FILE_NAME = 'basilisk-profiler.desktop'


def desktop_file() -> Path:
    config = os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config'
    return Path(config) / 'autostart' / FILE_NAME


def command() -> str:
    """How to start the tray service with this installation."""
    if getattr(sys, 'frozen', False):
        return shlex.quote(sys.executable)
    return f'{shlex.quote(sys.executable)} -m basilisk_profiler.daemon'


def entry() -> str:
    return '\n'.join([
        '[Desktop Entry]',
        'Type=Application',
        'Name=Basilisk Profiler',
        'Comment=Razer Basilisk V3 Pro profile switcher',
        f'Exec={command()}',
        'Icon=basilisk-profiler',
        'Terminal=false',
        'X-GNOME-Autostart-enabled=true',
        '',
    ])


def is_enabled() -> bool:
    return desktop_file().is_file()


def set_enabled(enabled: bool) -> None:
    path = desktop_file()
    if enabled:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(entry())
    else:
        path.unlink(missing_ok=True)
