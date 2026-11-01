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
