# SPDX-License-Identifier: GPL-2.0-or-later
"""System tray front end for the service (PySide6)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QCursor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QSystemTrayIcon

from ..platform import autostart
from .service import Service

TICK_MS = 100


COLORS = {'ok': '#44d62c', 'paused': '#9a9a9a', 'error': '#e04040'}


def profile_letter(name: str | None) -> str:
    """The first letter or digit of a profile name, upper case ('' if none)."""
    return next((c.upper() for c in name or '' if c.isalnum()), '')


def _icon(color: str, letter: str = '') -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(QColor('#101010'))
    if letter:
        # the active profile's letter on a wider mouse shape, readable at 16-24 px
        painter.drawRoundedRect(4, 2, 56, 60, 22, 22)
        font = QFont()
        font.setBold(True)
        font.setPixelSize(44)
        painter.setFont(font)
        painter.drawText(QRect(4, 2, 56, 60), Qt.AlignCenter, letter)
    else:
        painter.drawRoundedRect(14, 4, 36, 56, 18, 18)
    painter.end()
    return QIcon(pixmap)


def status_lines(service: Service) -> list[str]:
    st = service.status
    lines = []
    if st.dpi is not None:
        stage = f' ({st.stage}/{st.stage_count}. fokozat)' if st.stage and st.stage_count else ''
        lines.append(f'DPI: {st.dpi}{stage}')
    if st.battery is not None:
        lines.append(f'Akku: {st.battery}%')
    return lines


class Osd(QLabel):
    """A small on-screen display near the mouse pointer.

    Desktop notifications queue up (Cinnamon shows them one after another for seconds),
    so quick DPI button presses would trail behind; this label is updated in place.
    """

    def __init__(self):
        super().__init__()
        self.setWindowFlags(Qt.ToolTip | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                            | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setStyleSheet('QLabel { background: rgba(16, 16, 16, 225); color: #44d62c; '
                           'border: 1px solid #44d62c; border-radius: 8px; '
                           'padding: 8px 14px; font-size: 18px; font-weight: bold; }')
        self._hide = QTimer(self)
        self._hide.setSingleShot(True)
        self._hide.timeout.connect(self.hide)

    def flash(self, text: str, msecs: int = 1200) -> None:
        self.setText(text)
        self.adjustSize()
        pos = QCursor.pos()
        screen = QApplication.screenAt(pos) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        x = min(max(pos.x() + 24, area.left()), area.right() - self.width())
        y = min(max(pos.y() + 24, area.top()), area.bottom() - self.height())
        self.move(x, y)
        self.show()
        self.raise_()
        self._hide.start(msecs)


class UiSettings:
    """Small per-user tray preferences next to the config (not part of the profiles)."""

    def __init__(self, path: Path):
        self.path = path
        try:
            self.data = json.loads(path.read_text())
        except (OSError, ValueError):
            self.data = {}

    def get(self, key: str, default):
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        self.data[key] = value
        try:
            self.path.write_text(json.dumps(self.data, indent=2))
        except OSError:
            pass


def open_file(path) -> None:
    if sys.platform == 'win32':
        os.startfile(path)  # noqa: S606
    else:
        subprocess.Popen(['xdg-open', str(path)])


class Tray:
    def __init__(self, app: QApplication, service: Service):
        self.app = app
        self.service = service
        self.ui = UiSettings(service.config_path.with_name('tray.json'))
        self._icon_key = None
        self.tray = QSystemTrayIcon(_icon(COLORS['ok']))
        menu = QMenu()
        self.status = QAction('', menu, enabled=False)
        self.pause = QAction('Szüneteltetés', menu, checkable=True)
        self.pause.toggled.connect(service.set_paused)
        settings = QAction('Beállítások…', menu)
        settings.triggered.connect(self.open_settings)
        open_config = QAction('Konfig szövegként', menu)
        open_config.triggered.connect(lambda: open_file(service.config_path))
        quit_action = QAction('Kilépés', menu)
        quit_action.triggered.connect(app.quit)
        self.dpi_popup = QAction('DPI-váltás jelzése', menu, checkable=True)
        self.dpi_popup.setChecked(self.ui.get('dpi_popup', True))
        self.dpi_popup.toggled.connect(lambda on: self.ui.set('dpi_popup', on))
        self.dock_battery = QAction('Dokk: akkuszint-effekt', menu, checkable=True)
        self.dock_battery.setEnabled(False)  # until the dock has been read
        self.dock_battery.toggled.connect(self._dock_battery_toggled)
        if (saved := self.ui.get('dock_battery', None)) is not None:
            service.set_dock_battery(saved)  # re-applied if something else changed the dock
        actions = [self.status, self.pause, settings, open_config, self.dpi_popup,
                   self.dock_battery]
        if (auto := autostart()) is not None:
            start_with_os = QAction('Indítás a Windows-szal' if sys.platform == 'win32'
                                    else 'Indítás bejelentkezéskor', menu, checkable=True)
            start_with_os.setChecked(auto.is_enabled())
            start_with_os.toggled.connect(auto.set_enabled)
            actions.append(start_with_os)
        for action in (*actions, quit_action):
            menu.addAction(action)
        self.menu = menu  # keep a reference: the tray does not own it
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._activated)
        self.window = None
        self.osd = None
        service._on_change = lambda _s: self.refresh()
        service.on_dpi_changed = self._dpi_changed
        self.timer = QTimer()
        self.timer.timeout.connect(service.tick)
        self.timer.start(TICK_MS)
        self.refresh()
        self.tray.show()

    def _dpi_changed(self, status) -> None:
        self.refresh()
        if self.dpi_popup.isChecked() and status.dpi is not None:
            stage = f'  ({status.stage}/{status.stage_count})' if status.stage else ''
            if self.osd is None:
                self.osd = Osd()
            self.osd.flash(f'DPI {status.dpi}{stage}')

    def _dock_battery_toggled(self, on: bool) -> None:
        self.ui.set('dock_battery', on)
        self.service.set_dock_battery(on)

    def open_settings(self) -> None:
        from ..gui.main_window import MainWindow

        if self.window is None or not self.window.isVisible():
            self.window = MainWindow(self.service.config_path)
        self.window.show()
        self.refresh()
        self.window.raise_()
        self.window.activateWindow()

    def _activated(self, reason) -> None:
        if reason in (QSystemTrayIcon.DoubleClick, QSystemTrayIcon.Trigger):
            self.open_settings()

    def refresh(self) -> None:
        s = self.service
        profile = s.active.name if s.active else '-'
        text = f'Profil: {profile}'
        if s.config_error:
            text += ' (konfighiba)'
            state = 'error'
        else:
            state = 'paused' if s.paused else 'ok'
        self.status.setText(text)
        key = (state, profile_letter(s.active.name if s.active else None))
        if key != self._icon_key:
            self._icon_key = key
            self.tray.setIcon(_icon(COLORS[state], key[1]))
        lines = ['basilisk-profiler', text, *status_lines(s)]
        if s.config_error:
            lines.append(s.config_error)
        self.tray.setToolTip('\n'.join(lines))
        if s.dock_battery is not None:
            self.dock_battery.setEnabled(True)
            if self.dock_battery.isChecked() != s.dock_battery:
                self.dock_battery.blockSignals(True)
                self.dock_battery.setChecked(s.dock_battery)
                self.dock_battery.blockSignals(False)
        if self.window is not None and self.window.isVisible():
            self.window.set_live_status(' · '.join([text, *status_lines(s)]))
