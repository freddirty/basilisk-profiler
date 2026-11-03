# SPDX-License-Identifier: GPL-2.0-or-later
# PyInstaller spec: one-folder build of the tray service + settings GUI + CLI for Linux.
#   pyinstaller packaging/linux/basilisk_profiler.spec --noconfirm
# Output: dist/basilisk-profiler/basilisk-profiler
from pathlib import Path

ROOT = Path(SPECPATH).parents[1]  # noqa: F821 - SPECPATH is provided by PyInstaller
PKG = ROOT / 'src' / 'basilisk_profiler'

a = Analysis(  # noqa: F821
    [str(ROOT / 'packaging' / 'linux' / 'launcher.py')],
    pathex=[str(ROOT / 'src')],
    datas=[(str(PKG / 'gui' / 'assets'), 'basilisk_profiler/gui/assets')],
    hiddenimports=[
        'hidraw',
        'basilisk_profiler.cli',
        'basilisk_profiler.gui.main_window',
        'basilisk_profiler.platform.linux.x11',
        'basilisk_profiler.platform.linux.autostart',
        'basilisk_profiler.platform.linux.conflicts',
        'basilisk_profiler.platform.linux.events',
        'basilisk_profiler.platform.linux.cursor',
        # python-xlib loads its extensions by name at connect time
        'Xlib.ext.xfixes', 'Xlib.ext.xinput', 'Xlib.ext.shape',
    ],
    # 'hid' is hidapi's libusb build: it must never be used on Linux (see platform/__init__.py)
    excludes=['tkinter', 'hid', 'PySide6.QtWebEngineCore', 'PySide6.QtWebEngineWidgets',
              'PySide6.QtQml', 'PySide6.QtQuick', 'PySide6.Qt3DCore', 'PySide6.QtMultimedia',
              'PySide6.QtPdf'],
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='basilisk-profiler',
    console=True,  # no console window on Linux anyway; keeps CLI output on the terminal
)
coll = COLLECT(exe, a.binaries, a.datas, name='basilisk-profiler')  # noqa: F821
