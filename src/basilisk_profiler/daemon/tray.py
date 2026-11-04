# SPDX-License-Identifier: GPL-2.0-or-later
"""System tray front end for the service (PySide6)."""
from __future__ import annotations

import os
import subprocess
import sys

from PySide6.QtCore import QRect, Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QColor, QCursor, QFont, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QLabel, QMenu, QSystemTrayIcon

from ..core.ui_settings import UiSettings, ui_settings_path
from ..gui.language import apply_language
from ..i18n import AUTO, LANGUAGES, N_, tr
from ..platform import autostart
from .service import Service

TICK_MS = 100


COLORS = {'ok': '#44d62c', 'manual': '#f0a020', 'paused': '#9a9a9a', 'error': '#e04040'}
SLOT_NAMES = {0x01: N_('white'), 0x02: N_('red'), 0x03: N_('green'), 0x04: N_('blue'),
              0x05: N_('cyan')}


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


def profile_display(service: Service) -> tuple[str, str]:
    """The status text and the icon letter for what the mouse is using now."""
    store = service.manual_store
    if store is None:
        name = service.active.name if service.active else None
        return tr('Profile: {name}', name=name or '-'), profile_letter(name)
    color = tr(SLOT_NAMES[store]) if store in SLOT_NAMES else f'0x{store:02x}'
    slot = tr('{color} slot', color=color)
    profile = service.manual_profile
    if profile is None:
        # the icon letter of a manual slot without a known profile: M(anual) / K(ézi)
        return tr('Profile: manual, {slot}', slot=slot), tr('M')
    return (tr('Profile: {name} (manual, {slot})', name=profile.name, slot=slot),
            profile_letter(profile.name))


def status_lines(service: Service) -> list[str]:
    st = service.status
    lines = []
    if st.dpi is not None:
        stage = (tr(' (stage {stage}/{count})', stage=st.stage, count=st.stage_count)
                 if st.stage and st.stage_count else '')
        lines.append(f'DPI: {st.dpi}{stage}')
    if st.battery is not None:
        lines.append(tr('Battery: {percent}%', percent=st.battery))
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


def open_file(path) -> None:
    if sys.platform == 'win32':
        os.startfile(path)  # noqa: S606
    else:
        subprocess.Popen(['xdg-open', str(path)])


class Tray:
    def __init__(self, app: QApplication, service: Service):
        self.app = app
        self.service = service
        self.ui = UiSettings(ui_settings_path(service.config_path))
        apply_language(app, self.ui.get('language', AUTO))
        self._icon_key = None
        self.tray = QSystemTrayIcon(_icon(COLORS['ok']))
        menu = QMenu()
        self.status = QAction('', menu, enabled=False)
        self.pause = QAction(menu, checkable=True)
        self.pause.toggled.connect(service.set_paused)
        self.settings = QAction(menu)
        self.settings.triggered.connect(self.open_settings)
        self.open_config = QAction(menu)
        self.open_config.triggered.connect(lambda: open_file(service.config_path))
        self.quit_action = QAction(menu)
        self.quit_action.triggered.connect(app.quit)
        self.dpi_popup = QAction(menu, checkable=True)
        self.dpi_popup.setChecked(self.ui.get('dpi_popup', True))
        self.dpi_popup.toggled.connect(lambda on: self.ui.set('dpi_popup', on))
        self.dock_battery = QAction(menu, checkable=True)
        self.dock_battery.setEnabled(False)  # until the dock has been read
        self.dock_battery.toggled.connect(self._dock_battery_toggled)
        if (saved := self.ui.get('dock_battery', None)) is not None:
            service.set_dock_battery(saved)  # re-applied if something else changed the dock
        self.language_menu = QMenu(menu)
        self.language_group = QActionGroup(self.language_menu)
        self.language_actions = {}
        current = self.ui.get('language', AUTO)
        for code in (AUTO, *LANGUAGES):
            action = QAction(self.language_menu, checkable=True)
            action.setChecked(code == current or (code == AUTO and current not in LANGUAGES))
            action.triggered.connect(lambda _=False, c=code: self.set_language(c))
            self.language_group.addAction(action)
            self.language_menu.addAction(action)
            self.language_actions[code] = action
        actions = [self.status, self.pause, self.settings, self.open_config, self.dpi_popup,
                   self.dock_battery]
        self.start_with_os = None
        if (auto := autostart()) is not None:
            self.start_with_os = QAction(menu, checkable=True)
            self.start_with_os.setChecked(auto.is_enabled())
            self.start_with_os.toggled.connect(auto.set_enabled)
            actions.append(self.start_with_os)
        for action in actions:
            menu.addAction(action)
        menu.addMenu(self.language_menu)
        menu.addAction(self.quit_action)
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
        self.retranslate()
        self.tray.show()

    def retranslate(self) -> None:
        """Menu texts in the current language (at start and after a language change)."""
        self.pause.setText(tr('Pause'))
        self.settings.setText(tr('Settings…'))
        self.open_config.setText(tr('Config as text'))
        self.quit_action.setText(tr('Quit'))
        self.dpi_popup.setText(tr('Show DPI changes'))
        self.dock_battery.setText(tr('Dock: battery level effect'))
        if self.start_with_os is not None:
            self.start_with_os.setText(tr('Start with Windows') if sys.platform == 'win32'
                                       else tr('Start at login'))
        # 'Nyelv / Language': findable even by someone who cannot read the current language
        self.language_menu.setTitle(tr('Language'))
        for code, action in self.language_actions.items():
            action.setText(tr('Automatic (system)') if code == AUTO else LANGUAGES[code])
        self.refresh()

    def set_language(self, code: str) -> None:
        """Takes effect in the tray at once; an open settings window on its next opening."""
        self.ui.set('language', code)
        apply_language(self.app, code)
        self.retranslate()

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
        text, letter = profile_display(s)
        if s.config_error:
            text += tr(' (config error)')
            state = 'error'
        else:
            state = 'paused' if s.paused else 'manual' if s.manual_store else 'ok'
        self.status.setText(text)
        key = (state, letter)
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
