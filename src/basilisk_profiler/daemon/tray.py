# SPDX-License-Identifier: GPL-2.0-or-later
"""System tray front end for the service (PySide6)."""
from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon

from ..platform import autostart
from .service import Service

TICK_MS = 100


def _icon(color: str) -> QIcon:
    pixmap = QPixmap(64, 64)
    pixmap.fill(QColor(0, 0, 0, 0))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.setBrush(QColor(color))
    painter.setPen(QColor('#101010'))
    painter.drawRoundedRect(14, 4, 36, 56, 18, 18)
    painter.end()
    return QIcon(pixmap)


def open_file(path) -> None:
    if sys.platform == 'win32':
        os.startfile(path)  # noqa: S606
    else:
        subprocess.Popen(['xdg-open', str(path)])


class Tray:
    def __init__(self, app: QApplication, service: Service):
        self.app = app
        self.service = service
        self.icons = {'ok': _icon('#44d62c'), 'paused': _icon('#9a9a9a'), 'error': _icon('#e04040')}
        self.tray = QSystemTrayIcon(self.icons['ok'])
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
        actions = [self.status, self.pause, settings, open_config]
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
        service._on_change = lambda _s: self.refresh()
        self.timer = QTimer()
        self.timer.timeout.connect(service.tick)
        self.timer.start(TICK_MS)
        self.refresh()
        self.tray.show()

    def open_settings(self) -> None:
        from ..gui.main_window import MainWindow

        if self.window is None or not self.window.isVisible():
            self.window = MainWindow(self.service.config_path)
        self.window.show()
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
        self.tray.setIcon(self.icons[state])
        self.tray.setToolTip(f'basilisk-profiler\n{text}' +
                             (f'\n{s.config_error}' if s.config_error else ''))
