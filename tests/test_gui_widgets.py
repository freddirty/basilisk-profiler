# SPDX-License-Identifier: GPL-2.0-or-later
"""Qt-dependent tests; skipped where PySide6 is not installed."""
import os

import pytest

pytest.importorskip('PySide6')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from basilisk_profiler.core import config as cfg  # noqa: E402
from basilisk_profiler.gui.keymap import action_from_key  # noqa: E402


@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])


@pytest.mark.parametrize('key,mods,expected', [
    (Qt.Key_T, Qt.ControlModifier, 'ctrl+t'),
    (Qt.Key_T, Qt.ControlModifier | Qt.ShiftModifier, 'ctrl+shift+t'),
    (Qt.Key_8, Qt.NoModifier, '8'),
    (Qt.Key_F5, Qt.AltModifier, 'alt+f5'),
    (Qt.Key_PageDown, Qt.NoModifier, 'pagedown'),
    (Qt.Key_Control, Qt.ControlModifier, None),
    (Qt.Key_VolumeUp, Qt.NoModifier, None),
])
def test_action_from_key(key, mods, expected):
    assert action_from_key(key, mods) == expected


def test_main_window_edits_and_saves(app, tmp_path):
    from basilisk_profiler.gui.main_window import MainWindow

    path = tmp_path / 'config.toml'
    window = MainWindow(path)
    assert window.draft.names() == ['general', 'browser']
    window.profiles.setCurrentRow(1)
    window._select_button(0x05)
    assert window.button_editor.key.text() == 'ctrl+t'
    window.button_editor.load('x', 'mouse:4')
    window._button_changed('ctrl+shift+t')
    assert window.save()
    assert cfg.load(path).profiles['browser'].buttons[0x05].modifiers == 0x03
    window.draft.dirty = False
    window.close()


def test_tray_shows_manual_slot(tmp_path):
    pytest.importorskip('PySide6')
    from basilisk_profiler.core.model import Profile
    from basilisk_profiler.daemon.tray import profile_display

    class S:
        active = Profile('general')
        manual_store = None
        manual_profile = None

    assert profile_display(S()) == ('Profil: general', 'G')
    S.manual_store = 0x04
    assert profile_display(S()) == ('Profil: kézi, kék hely', 'K')
    S.manual_profile = Profile('arpg')
    assert profile_display(S()) == ('Profil: arpg (kézi, kék hely)', 'A')
    S.active = S.manual_store = S.manual_profile = None
    assert profile_display(S()) == ('Profil: -', '')


def test_tray_profile_letter_and_status_lines(tmp_path):
    from basilisk_profiler.daemon.service import LiveStatus
    from basilisk_profiler.daemon.tray import profile_letter, status_lines

    assert profile_letter('browser') == 'B'
    assert profile_letter('  2nd') == '2'
    assert profile_letter(None) == ''

    class S:
        status = LiveStatus(dpi=1600, stage=3, stage_count=5, battery=80)

    assert status_lines(S()) == ['DPI: 1600 (3/5. fokozat)', 'Akku: 80%']
    S.status = LiveStatus()
    assert status_lines(S()) == []


def test_tray_language_switch(app, tmp_path, monkeypatch):
    from basilisk_profiler import i18n
    from basilisk_profiler.core.ui_settings import UiSettings
    from basilisk_profiler.daemon import tray as tray_mod
    from basilisk_profiler.daemon.service import Service

    def no_device():
        raise OSError('no device in tests')

    monkeypatch.setattr(tray_mod, 'autostart', lambda: None)
    path = tmp_path / 'config.toml'
    cfg.ensure_exists(path)
    (tmp_path / 'tray.json').write_text('{"language": "hu"}')
    tray = tray_mod.Tray(app, Service(path, open_device=no_device))
    try:
        assert tray.pause.text() == 'Szüneteltetés'
        assert tray.language_actions['hu'].isChecked()
        tray.language_actions['en'].trigger()
        assert i18n.language() == 'en'
        assert tray.pause.text() == 'Pause'
        assert tray.language_menu.title() == 'Language'
        assert tray.status.text().startswith('Profile:')
        assert UiSettings(tmp_path / 'tray.json').get('language', None) == 'en'
        tray.language_actions['auto'].trigger()
        assert UiSettings(tmp_path / 'tray.json').get('language', None) == 'auto'
    finally:
        tray.timer.stop()
        tray.tray.hide()


def test_main_window_in_english(app, tmp_path):
    from basilisk_profiler import i18n
    from basilisk_profiler.gui.main_window import MainWindow

    i18n.set_language('en')
    window = MainWindow(tmp_path / 'config.toml')
    assert [window.tabs.tabText(i) for i in range(window.tabs.count())] == [
        'Buttons', 'DPI', 'Cursor', 'Rules (automatic switching)']
    assert window.button_editor.title() == 'Front side button (Mouse Button 5)'
    window.close()
