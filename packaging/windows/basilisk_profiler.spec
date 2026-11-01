# SPDX-License-Identifier: GPL-2.0-or-later
# PyInstaller spec: one-folder windowed build of the tray service + settings GUI.
#   pyinstaller packaging/windows/basilisk_profiler.spec --noconfirm
# Output: dist/BasiliskProfiler/BasiliskProfiler.exe
from pathlib import Path

ROOT = Path(SPECPATH).parents[1]  # noqa: F821 - SPECPATH is provided by PyInstaller
PKG = ROOT / 'src' / 'basilisk_profiler'

a = Analysis(  # noqa: F821
    [str(ROOT / 'packaging' / 'windows' / 'launcher.py')],
    pathex=[str(ROOT / 'src')],
    datas=[(str(PKG / 'gui' / 'assets'), 'basilisk_profiler/gui/assets')],
    hiddenimports=[
        'basilisk_profiler.gui.main_window',
        'basilisk_profiler.platform.win.hid',
        'basilisk_profiler.platform.win.foreground',
        'basilisk_profiler.platform.win.autostart',
    ],
    excludes=['tkinter', 'hid', 'Xlib', 'PySide6.QtWebEngineCore', 'PySide6.QtQml',
              'PySide6.QtQuick', 'PySide6.Qt3DCore', 'PySide6.QtMultimedia'],
)
pyz = PYZ(a.pure)  # noqa: F821
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='BasiliskProfiler',
    console=False,
    icon=str(ROOT / 'packaging' / 'windows' / 'app.ico'),
)
coll = COLLECT(exe, a.binaries, a.datas, name='BasiliskProfiler')  # noqa: F821
