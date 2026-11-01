# SPDX-License-Identifier: GPL-2.0-or-later
"""Click through the settings window; any exception raised inside a Qt slot fails the test."""
import os
import sys

import pytest

pytest.importorskip('PySide6')
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')

from PySide6.QtCore import QPoint, Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from basilisk_profiler.core import config as cfg  # noqa: E402
from basilisk_profiler.core.model import BUTTON_IDS  # noqa: E402
from basilisk_profiler.gui import main_window as mw  # noqa: E402
from basilisk_profiler.gui.mouse_view import HOTSPOTS  # noqa: E402


@pytest.fixture
def window(tmp_path, monkeypatch):
    app = QApplication.instance() or QApplication([])  # noqa: F841
    errors = []
    monkeypatch.setattr(sys, 'excepthook', lambda *exc: errors.append(exc))
    monkeypatch.setattr(QMessageBox, 'question', lambda *a, **k: QMessageBox.Yes)
    for name in ('warning', 'information'):
        monkeypatch.setattr(QMessageBox, name,
                            lambda *a, name=name, **k: errors.append((name, a[1:])))
    path = tmp_path / 'config.toml'
    path.write_text(cfg.EXAMPLE.replace('button5 = "ctrl+t"',
                                        'button5 = "ctrl+t"\n0x34 = "raw:0e:680014"'))
    win = mw.MainWindow(path)
    win.resize(1280, 760)
    win.show()
    QApplication.processEvents()
    yield win, errors
    win.draft.dirty = False
    win.close()
    assert not errors, errors


def click_hotspots(win, expect_selection=True):
    view = win.mouse
    for h in HOTSPOTS:
        center = view._map(h.rect).center().toPoint()
        QTest.mouseMove(view, center)
        QTest.mouseClick(view, Qt.LeftButton, Qt.NoModifier, center)
        if h.editable and expect_selection:
            assert win.current_button == BUTTON_IDS[h.key]
    QTest.mouseMove(view, QPoint(1, 1))


def test_click_through_everything(window, monkeypatch):
    win, errors = window
    for row in range(win.profiles.count()):
        win.profiles.setCurrentRow(row)
        click_hotspots(win)
        editor = win.button_editor
        for mode in editor.MODES:
            editor.radios[mode].click()
        editor.mouse_button.setCurrentIndex(3)
        editor.media.setCurrentIndex(2)
        editor.radios['disabled'].click()
        editor.dpi_function.setCurrentIndex((editor.dpi_function.currentIndex() + 1) % 3)
        editor.dpi_function.setCurrentIndex(2)
        editor.clutch_dpi.setValue(800)
        assert editor.action() == 'dpi:clutch:800'
        win.onboard.setCurrentIndex(2)
        editor.key.setFocus()
        QTest.keyClick(editor.key, Qt.Key_W, Qt.ControlModifier)
        QTest.keyClick(editor.key, Qt.Key_Exclam, Qt.ShiftModifier)
        QTest.keyClick(editor.key, Qt.Key_Shift)
        dpi = win.dpi_editor
        dpi.enabled.setChecked(True)
        for count in (5, 1, 3):
            dpi.count.setValue(count)
        dpi.stages[0][0].setValue(1234)
        dpi.active_group.button(2).click()
        dpi.enabled.setChecked(False)

    monkeypatch.setattr(win, '_ask_name', lambda *a: 'teszt')
    win._new_profile()
    win._duplicate()
    monkeypatch.setattr(win, '_ask_name', lambda *a: 'átnevezett')
    win._rename()
    win._make_default()
    rules = win.rules_tab
    rules._add('match_title', 'x')
    rules.table.item(0, 1).setText('firefox-nightly')
    rules.table.selectRow(1)
    rules._move(1)
    rules._move(-1)
    rules.table.cellWidget(0, 0).setCurrentIndex(2)
    rules.table.cellWidget(0, 2).setCurrentIndex(0)
    rules.table.selectRow(0)
    rules._remove()
    win._delete()
    assert win.save()
    cfg.load(win.config_path)
    win.reload_from_file()
    click_hotspots(win)


def test_raw_action_is_shown_not_editable(window):
    win, _ = window
    win.profiles.setCurrentRow(1)
    win.button_editor.load('x', 'raw:0e:680014')
    assert 'raw:0e' in win.button_editor.other.text()
    assert win.button_editor.group.checkedId() == -1


def test_delete_last_profile(window, monkeypatch):
    win, _ = window
    while win.draft.names():
        win._delete()
    click_hotspots(win, expect_selection=False)  # tab is disabled: no crash, no edit
    win.rules_tab._add('match_process', 'x')
    assert win.draft.rules == []
