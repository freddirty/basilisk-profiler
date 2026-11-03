# SPDX-License-Identifier: GPL-2.0-or-later
"""Settings window: profiles, button mappings, DPI stages, window rules, Synapse import.

The window only edits config.toml; the running service picks the file up by itself.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QSpinBox,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core import config as cfg
from ..core import protocol as p
from ..core import synapse_import
from ..core.model import BUTTON_IDS, button_name
from ..platform import list_windows
from .draft import RULE_FIELDS, ConfigDraft, describe_action
from .keymap import action_from_key, key_name
from .mouse_view import MouseView

BUTTON_TITLES = {
    'button4': 'Hátsó oldalgomb (Mouse Button 4)',
    'button5': 'Elülső oldalgomb (Mouse Button 5)',
    'side_bottom': 'Érzékenység-clutch (hüvelykujj-gomb)',
    'wheel_click': 'Görgőkattintás',
    'tilt_left': 'Görgő döntése balra',
    'tilt_right': 'Görgő döntése jobbra',
    'scroll_mode': 'Görgő mód gomb (racsnis / sima)',
    'dpi_cycle': 'DPI-fokozat váltó gomb',
    'profile': 'Profilváltó gomb (alul)',
}
ONBOARD_CHOICES = ((None, 'Nincs (csak a program váltja)'), (1, '1. hely (piros)'),
                   (2, '2. hely (zöld)'), (3, '3. hely (kék)'), (4, '4. hely (cián)'))
RULE_TITLES = {'match_process': 'Program', 'match_class': 'Ablakosztály (regex)',
               'match_title': 'Ablakcím (regex)'}


class KeyCaptureEdit(QLineEdit):
    """Shows an action; while focused, the next key press (with modifiers) replaces it."""

    captured = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setReadOnly(True)
        self.setPlaceholderText('kattints ide, majd nyomd le a billentyűt')

    def keyPressEvent(self, event):
        key = event.key()
        if key_name(key) is None and 0x30 <= event.nativeVirtualKey() <= 0x5A:
            key = event.nativeVirtualKey()  # shifted digits arrive as symbols (Shift+1 = !)
        action = action_from_key(key, event.modifiers())
        if action:
            self.setText(action)
            self.captured.emit(action)


MOUSE_CHOICES = ((1, 'Bal gomb'), (2, 'Jobb gomb'), (3, 'Középső gomb'), (4, 'Vissza (4)'),
                 (5, 'Előre (5)'), (9, 'Görgetés fel'))
MEDIA_CHOICES = (('play_pause', 'Lejátszás / szünet'), ('next', 'Következő szám'),
                 ('previous', 'Előző szám'), ('stop', 'Leállítás'),
                 ('volume_up', 'Hangerő fel'), ('volume_down', 'Hangerő le'),
                 ('mute', 'Némítás'))
DPI_CHOICES = (('dpi:stage_up', 'DPI-fokozat fel'), ('dpi:cycle', 'DPI-fokozatok körbe'),
               ('dpi:clutch', 'Érzékenység-clutch (lenyomva tartva)'))


class ButtonEditor(QGroupBox):
    """Picks one action for a button; emits it in config syntax, or None for the default."""

    changed = Signal(object)

    MODES = ('default', 'mouse', 'key', 'media', 'dpi', 'profile', 'disabled')

    def __init__(self, parent=None):
        super().__init__('Gomb', parent)
        titles = ('Alapértelmezett (gyári funkció)', 'Egérgomb', 'Billentyű / kombináció',
                  'Multimédia', 'DPI-funkció', 'Következő profil', 'Letiltva')
        self.radios = {}
        self.group = QButtonGroup(self)
        for i, (mode, title) in enumerate(zip(self.MODES, titles, strict=True)):
            self.radios[mode] = QRadioButton(title)
            self.group.addButton(self.radios[mode], i)
        self.mode_default = self.radios['default']
        self.mode_mouse = self.radios['mouse']
        self.mode_key = self.radios['key']
        self.mouse_button = QComboBox()
        for n, label in MOUSE_CHOICES:
            self.mouse_button.addItem(label, n)
        self.key = KeyCaptureEdit()
        self.media = QComboBox()
        for name, label in MEDIA_CHOICES:
            self.media.addItem(label, name)
        self.dpi_function = QComboBox()
        for value, label in DPI_CHOICES:
            self.dpi_function.addItem(label, value)
        self.clutch_dpi = QSpinBox()
        self.clutch_dpi.setRange(p.DPI_MIN, p.DPI_MAX)
        self.clutch_dpi.setSingleStep(50)
        self.clutch_dpi.setSuffix(' DPI')
        self.clutch_dpi.setValue(400)
        self.other = QLabel()
        self.other.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.addWidget(self.mode_default)
        for radio, widget in ((self.mode_mouse, self.mouse_button),
                              (self.radios['media'], self.media)):
            row = QHBoxLayout()
            row.addWidget(radio)
            row.addWidget(widget, 1)
            layout.addLayout(row)
        layout.addWidget(self.mode_key)
        layout.addWidget(self.key)
        layout.addWidget(self.radios['dpi'])
        layout.addWidget(self.dpi_function)
        layout.addWidget(self.clutch_dpi)
        layout.addWidget(self.radios['profile'])
        layout.addWidget(self.radios['disabled'])
        layout.addWidget(self.other)
        layout.addStretch(1)

        self.group.idClicked.connect(lambda _: self._emit())
        self.mouse_button.currentIndexChanged.connect(lambda _: self._picked('mouse'))
        self.media.currentIndexChanged.connect(lambda _: self._picked('media'))
        self.dpi_function.currentIndexChanged.connect(lambda _: self._picked('dpi'))
        self.clutch_dpi.valueChanged.connect(lambda _: self._picked('dpi'))
        self.key.captured.connect(lambda _: self._picked('key'))
        self._loading = False

    def mode(self) -> str | None:
        checked = self.group.checkedId()
        return self.MODES[checked] if checked >= 0 else None

    def load(self, title: str, action: str | None) -> None:
        self._loading = True
        self.setTitle(title)
        self.other.setText('')
        self.key.clear()
        mode = 'default'
        if action is None:
            pass
        elif action.startswith('mouse:'):
            mode = 'mouse'
            index = self.mouse_button.findData(int(action[6:]))
            self.mouse_button.setCurrentIndex(max(index, 0))
        elif action.startswith('media:'):
            mode = 'media'
            self.media.setCurrentIndex(max(self.media.findData(action[6:]), 0))
        elif action.startswith('dpi:'):
            mode = 'dpi'
            base = 'dpi:clutch' if action.startswith('dpi:clutch') else action
            self.dpi_function.setCurrentIndex(max(self.dpi_function.findData(base), 0))
            if base == 'dpi:clutch':
                self.clutch_dpi.setValue(int(action.split(':')[2]))
        elif action == 'profile:cycle':
            mode = 'profile'
        elif action == 'disabled':
            mode = 'disabled'
        elif action.startswith('raw:'):
            mode = None
            self.other.setText(f'Ezt a funkciót még nem tudja szerkeszteni a program ({action}).')
        else:
            mode = 'key'
            self.key.setText(action)
        if mode is None:
            self.group.setExclusive(False)
            for b in self.group.buttons():
                b.setChecked(False)
            self.group.setExclusive(True)
        else:
            self.radios[mode].setChecked(True)
        self._update_enabled()
        self._loading = False

    def _update_enabled(self):
        self.clutch_dpi.setEnabled(self.dpi_function.currentData() == 'dpi:clutch')

    def _picked(self, mode: str):
        self._update_enabled()
        if not self._loading:
            self.radios[mode].setChecked(True)
            self._emit()

    def action(self) -> str | None:
        mode = self.mode()
        if mode == 'mouse':
            return f'mouse:{self.mouse_button.currentData()}'
        if mode == 'key':
            return self.key.text() or None
        if mode == 'media':
            return f'media:{self.media.currentData()}'
        if mode == 'dpi':
            value = self.dpi_function.currentData()
            return f'{value}:{self.clutch_dpi.value()}' if value == 'dpi:clutch' else value
        if mode == 'profile':
            return 'profile:cycle'
        if mode == 'disabled':
            return 'disabled'
        return None

    def _emit(self):
        if self._loading:
            return
        mode = self.mode()
        if mode == 'default':
            self.changed.emit(None)
        elif (action := self.action()) is not None:
            self.changed.emit(action)


class DpiEditor(QGroupBox):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__('DPI-fokozatok', parent)
        self.enabled = QCheckBox('A profil állítsa be a DPI-fokozatokat')
        self.count = QSpinBox()
        self.count.setRange(1, p.MAX_DPI_STAGES)
        self.stages = []
        self.active_group = QButtonGroup(self)
        form = QFormLayout()
        form.addRow(self.enabled)
        form.addRow('Fokozatok száma', self.count)
        for i in range(p.MAX_DPI_STAGES):
            spin = QSpinBox()
            spin.setRange(p.DPI_MIN, p.DPI_MAX)
            spin.setSingleStep(50)
            spin.setSuffix(' DPI')
            radio = QRadioButton('aktív')
            self.active_group.addButton(radio, i + 1)
            row = QHBoxLayout()
            row.addWidget(spin, 1)
            row.addWidget(radio)
            form.addRow(f'{i + 1}. fokozat', row)
            self.stages.append((spin, radio))
            spin.valueChanged.connect(self._changed)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addStretch(1)
        self.enabled.toggled.connect(self._changed)
        self.count.valueChanged.connect(self._changed)
        self.active_group.idClicked.connect(lambda _: self._changed())
        self._loading = False

    def load(self, stages: list[int] | None, active: int | None) -> None:
        self._loading = True
        self.enabled.setChecked(bool(stages))
        values = stages or [400, 800, 1600, 3200, 6400]
        self.count.setValue(len(values))
        for i, (spin, _radio) in enumerate(self.stages):
            spin.setValue(values[i] if i < len(values) else 3200)
        button = self.active_group.button(active or 1)
        if button:
            button.setChecked(True)
        self._loading = False
        self._update_enabled()

    def value(self) -> tuple[list[int] | None, int | None]:
        if not self.enabled.isChecked():
            return None, None
        n = self.count.value()
        return [spin.value() for spin, _ in self.stages[:n]], self.active_group.checkedId()

    def _update_enabled(self):
        on = self.enabled.isChecked()
        self.count.setEnabled(on)
        for i, (spin, radio) in enumerate(self.stages):
            visible = on and i < self.count.value()
            spin.setEnabled(visible)
            radio.setEnabled(visible)
        if on and self.active_group.checkedId() > self.count.value():
            self.active_group.button(self.count.value()).setChecked(True)

    def _changed(self, *_):
        self._update_enabled()
        if not self._loading:
            self.changed.emit()


class WindowPicker(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Futó ablak kiválasztása')
        self.resize(640, 400)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Program', 'Ablakosztály', 'Cím'])
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.windows = [w for w in list_windows() if w.process]
        for w in self.windows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for col, text in enumerate((w.process, w.wm_class, w.title)):
                self.table.setItem(row, col, QTableWidgetItem(text))
        self.table.doubleClicked.connect(self.accept)
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(self.table)
        layout.addWidget(buttons)

    def selected(self):
        row = self.table.currentRow()
        return self.windows[row] if 0 <= row < len(self.windows) else None


class RulesTab(QWidget):
    changed = Signal()

    def __init__(self, draft: ConfigDraft, parent=None):
        super().__init__(parent)
        self.draft = draft
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(['Feltétel', 'Érték', 'Profil'])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        add = QPushButton('Új szabály')
        pick = QPushButton('Futó ablakból…')
        remove = QPushButton('Törlés')
        up = QPushButton('Fel')
        down = QPushButton('Le')
        add.clicked.connect(lambda: self._add('match_process', ''))
        pick.clicked.connect(self._pick)
        remove.clicked.connect(self._remove)
        up.clicked.connect(lambda: self._move(-1))
        down.clicked.connect(lambda: self._move(1))
        buttons = QHBoxLayout()
        for b in (add, pick, remove, up, down):
            buttons.addWidget(b)
        buttons.addStretch(1)
        hint = QLabel('A szabályokat felülről lefelé nézi a program; az első egyező dönt. '
                      'Ha egyik sem illik, az alapértelmezett profil él.')
        hint.setWordWrap(True)
        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(self.table)
        layout.addLayout(buttons)
        self._loading = False
        self.table.itemChanged.connect(lambda item: self._store(item.row()))

    def reload(self) -> None:
        self._loading = True
        self.table.setRowCount(0)
        for i in range(len(self.draft.rules)):
            field, pattern, profile = self.draft.rule_parts(i)
            self.table.insertRow(i)
            kind = QComboBox()
            for f in RULE_FIELDS:
                kind.addItem(RULE_TITLES[f], f)
            kind.setCurrentIndex(RULE_FIELDS.index(field))
            prof = QComboBox()
            prof.addItems(self.draft.names())
            prof.setCurrentText(profile)
            self.table.setCellWidget(i, 0, kind)
            self.table.setItem(i, 1, QTableWidgetItem(pattern))
            self.table.setCellWidget(i, 2, prof)
            kind.currentIndexChanged.connect(lambda _=0, row=i: self._store(row))
            prof.currentIndexChanged.connect(lambda _=0, row=i: self._store(row))
        self._loading = False

    def _store(self, row: int) -> None:
        if self._loading or row >= len(self.draft.rules):
            return
        field = self.table.cellWidget(row, 0).currentData()
        pattern = self.table.item(row, 1).text() if self.table.item(row, 1) else ''
        profile = self.table.cellWidget(row, 2).currentText()
        self.draft.set_rule(row, field, pattern, profile)
        self.changed.emit()

    def _add(self, field: str, pattern: str) -> None:
        if not self.draft.names():
            return
        row = self.draft.add_rule(field, pattern, self.draft.default or self.draft.names()[0])
        self.reload()
        self.table.selectRow(row)
        self.table.editItem(self.table.item(row, 1))
        self.changed.emit()

    def _pick(self) -> None:
        dialog = WindowPicker(self)
        if dialog.exec() and (window := dialog.selected()):
            self._add('match_process', window.process)

    def _remove(self) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.draft.rules):
            self.draft.remove_rule(row)
            self.reload()
            self.changed.emit()

    def _move(self, delta: int) -> None:
        row = self.table.currentRow()
        if 0 <= row < len(self.draft.rules):
            row = self.draft.move_rule(row, delta)
            self.reload()
            self.table.selectRow(row)
            self.changed.emit()


class ImportDialog(QDialog):
    def __init__(self, imported, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Profilok importálása a Synapse-ból')
        self.resize(560, 380)
        self.list = QListWidget()
        for item in imported:
            prof = item.profile
            detail = ', '.join(f'{button_name(b)}={describe_action(a)}'
                               for b, a in ((b, _fmt(a)) for b, a in prof.buttons.items()))
            text = f'{prof.name}  —  {detail or "nincs gombkiosztás"}'
            if item.skipped:
                text += f'  (kihagyva: {len(item.skipped)})'
            entry = QListWidgetItem(text)
            entry.setFlags(entry.flags() | Qt.ItemIsUserCheckable)
            entry.setCheckState(Qt.Checked)
            entry.setToolTip('\n'.join(item.skipped))
            self.list.addItem(entry)
        self.imported = imported
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel('A Synapse helyi adatbázisában talált profilok. A Hypershift-'
                                'kiosztások és a nem támogatott gombok kimaradnak.'))
        layout.addWidget(self.list)
        layout.addWidget(buttons)

    def chosen(self):
        return [item for i, item in enumerate(self.imported)
                if self.list.item(i).checkState() == Qt.Checked]


def _fmt(action: p.Action) -> str:
    from ..core.model import format_action
    return format_action(action)


class MainWindow(QMainWindow):
    def __init__(self, config_path: Path, parent=None):
        super().__init__(parent)
        self.config_path = config_path
        self.setWindowTitle('Basilisk Profiler')
        self.resize(1100, 680)
        cfg.ensure_exists(config_path)
        self.draft = ConfigDraft.load(config_path)
        self.current: str | None = None
        self.current_button: int = BUTTON_IDS['button5']

        # profiles column
        self.profiles = QListWidget()
        self.profiles.currentTextChanged.connect(self._select_profile)
        prof_buttons = QHBoxLayout()
        for label, slot in (('Új', self._new_profile), ('Másolat', self._duplicate),
                            ('Átnevezés', self._rename), ('Törlés', self._delete)):
            b = QPushButton(label)
            b.clicked.connect(slot)
            prof_buttons.addWidget(b)
        self.default_button = QPushButton('Legyen az alapértelmezett')
        self.default_button.clicked.connect(self._make_default)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.addWidget(QLabel('Profilok'))
        left_layout.addWidget(self.profiles)
        left_layout.addLayout(prof_buttons)
        left_layout.addWidget(self.default_button)
        self.onboard = QComboBox()
        for slot, label in ONBOARD_CHOICES:
            self.onboard.addItem(label, slot)
        self.onboard.setToolTip('A beépített helyre írt profil az egérben marad: a program '
                                'nélkül, akár másik gépen is a profilgombbal választható.')
        self.onboard.currentIndexChanged.connect(self._onboard_changed)
        left_layout.addWidget(QLabel('Beépített hely az egérben'))
        left_layout.addWidget(self.onboard)

        # buttons tab
        self.mouse = MouseView()
        self.mouse.buttonClicked.connect(self._select_button)
        self.button_editor = ButtonEditor()
        self.button_editor.changed.connect(self._button_changed)
        buttons_tab = QWidget()
        bl = QHBoxLayout(buttons_tab)
        self.button_editor.setMaximumWidth(340)
        bl.addWidget(self.mouse, 1)
        bl.addWidget(self.button_editor)

        # dpi tab
        self.dpi_editor = DpiEditor()
        self.dpi_editor.changed.connect(self._dpi_changed)
        dpi_tab = QWidget()
        dl = QHBoxLayout(dpi_tab)
        dl.addWidget(self.dpi_editor)
        dl.addStretch(1)

        self.rules_tab = RulesTab(self.draft)
        self.rules_tab.changed.connect(self._mark_dirty)

        self.tabs = QTabWidget()
        self.tabs.addTab(buttons_tab, 'Gombok')
        self.tabs.addTab(dpi_tab, 'DPI')
        self.tabs.addTab(self.rules_tab, 'Szabályok (automatikus váltás)')

        splitter = QSplitter()
        splitter.addWidget(left)
        splitter.addWidget(self.tabs)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([260, 840])
        self.setCentralWidget(splitter)

        save = QAction('Mentés', self, shortcut=QKeySequence.Save, triggered=self.save)
        import_action = QAction('Importálás a Synapse-ból…', self, triggered=self.import_synapse)
        reload_action = QAction('Újratöltés a fájlból', self, triggered=self.reload_from_file)
        menu = self.menuBar().addMenu('Fájl')
        for a in (save, import_action, reload_action):
            menu.addAction(a)
        toolbar = self.addToolBar('main')
        toolbar.setMovable(False)
        toolbar.addAction(save)
        toolbar.addAction(import_action)
        self.statusBar().showMessage(str(config_path))
        # live DPI / battery from the tray service; stays hidden when run on its own
        self.live = QLabel()
        self.live.setStyleSheet('font-weight: bold; padding: 0 8px;')
        self.live.hide()
        self.statusBar().addPermanentWidget(self.live)
        self._refresh_profiles()

    # --- profiles ----------------------------------------------------------------

    def _refresh_profiles(self, select: str | None = None) -> None:
        select = select or self.current
        self.profiles.blockSignals(True)
        self.profiles.clear()
        for name in self.draft.names():
            text = f'{name}  ★' if name == self.draft.default else name
            if slot := self.draft.onboard_slot(name):
                text += f'   [{slot}. hely]'
            item = QListWidgetItem(text)
            item.setData(Qt.UserRole, name)
            self.profiles.addItem(item)
        self.profiles.blockSignals(False)
        names = self.draft.names()
        target = select if select in names else (names[0] if names else None)
        if target:
            self.profiles.setCurrentRow(names.index(target))
        self._select_profile()
        self.rules_tab.reload()

    def _select_profile(self, *_):
        item = self.profiles.currentItem()
        self.current = item.data(Qt.UserRole) if item else None
        enabled = self.current is not None
        self.tabs.widget(0).setEnabled(enabled)
        self.tabs.widget(1).setEnabled(enabled)
        self.onboard.setEnabled(enabled)
        if not enabled:
            return
        self._update_labels()
        self._select_button(self.current_button)
        self.dpi_editor.load(*self.draft.dpi(self.current))
        self.onboard.blockSignals(True)
        self.onboard.setCurrentIndex(max(self.onboard.findData(
            self.draft.onboard_slot(self.current)), 0))
        self.onboard.blockSignals(False)

    def _onboard_changed(self, _index):
        if self.current:
            self.draft.set_onboard_slot(self.current, self.onboard.currentData())
            self._refresh_profiles()
            self._mark_dirty()

    def _update_labels(self):
        self.mouse.set_labels({b: describe_action(self.draft.button(self.current, b))
                               for b in BUTTON_IDS.values()})

    def _ask_name(self, title: str, text: str = '') -> str | None:
        name, ok = QInputDialog.getText(self, title, 'Profil neve:', text=text)
        return name.strip() if ok and name.strip() else None

    def _new_profile(self):
        if name := self._ask_name('Új profil'):
            self._refresh_profiles(self.draft.add_profile(name))
            self._mark_dirty()

    def _duplicate(self):
        if self.current:
            self._refresh_profiles(self.draft.duplicate(self.current))
            self._mark_dirty()

    def _rename(self):
        if self.current and (name := self._ask_name('Átnevezés', self.current)):
            try:
                self._refresh_profiles(self.draft.rename(self.current, name))
            except ValueError as e:
                QMessageBox.warning(self, 'Átnevezés', str(e))
                return
            self._mark_dirty()

    def _delete(self):
        if not self.current:
            return
        answer = QMessageBox.question(
            self, 'Törlés', f'Törlöd a(z) „{self.current}” profilt és a hozzá tartozó szabályokat?')
        if answer == QMessageBox.Yes:
            self.draft.delete(self.current)
            self.current = None
            self._refresh_profiles()
            self._mark_dirty()

    def _make_default(self):
        if self.current:
            self.draft.set_default(self.current)
            self._refresh_profiles()
            self._mark_dirty()

    # --- buttons / dpi -------------------------------------------------------------

    def _select_button(self, button: int):
        self.current_button = button
        self.mouse.select(button)
        name = button_name(button)
        self.button_editor.load(BUTTON_TITLES.get(name, name),
                                self.draft.button(self.current, button))

    def _button_changed(self, action):
        if self.current:
            self.draft.set_button(self.current, self.current_button, action)
            self._update_labels()
            self._mark_dirty()

    def _dpi_changed(self):
        if self.current:
            self.draft.set_dpi(self.current, *self.dpi_editor.value())
            self._mark_dirty()

    # --- file ----------------------------------------------------------------------

    def _mark_dirty(self):
        self.setWindowTitle('Basilisk Profiler *' if self.draft.dirty else 'Basilisk Profiler')

    def save(self) -> bool:
        try:
            self.draft.save(self.config_path)
        except (cfg.ConfigError, OSError) as e:
            QMessageBox.warning(self, 'Mentés', f'Nem menthető:\n{e}')
            return False
        self._mark_dirty()
        self.statusBar().showMessage('Elmentve – a háttérszolgáltatás magától átveszi.', 5000)
        return True

    def reload_from_file(self):
        try:
            self.draft = ConfigDraft.load(self.config_path)
        except cfg.ConfigError as e:
            QMessageBox.warning(self, 'Újratöltés', str(e))
            return
        self.rules_tab.draft = self.draft
        self._refresh_profiles()
        self._mark_dirty()

    def import_synapse(self):
        folder = None
        default = synapse_import.default_db_dir()
        if default is None or not default.is_dir():
            # no local Synapse (Linux): a copy of its data folder from a Windows machine
            chosen = QFileDialog.getExistingDirectory(
                self, 'A Synapse adatmappája (Windowsról átmásolva: '
                      '%LOCALAPPDATA%\\Razer\\RazerAppEngine\\User Data)')
            if not chosen:
                return
            folder = Path(chosen)
        try:
            imported = synapse_import.read_profiles(folder)
        except (OSError, ValueError) as e:
            QMessageBox.warning(self, 'Importálás', f'A Synapse adatai nem olvashatók:\n{e}')
            return
        if not imported:
            QMessageBox.information(self, 'Importálás', 'Nem találtam Basilisk-profilt.')
            return
        dialog = ImportDialog(imported, self)
        if dialog.exec():
            last = None
            for item in dialog.chosen():
                last = self.draft.add_imported(item.profile)
            self._refresh_profiles(last)
            self._mark_dirty()

    def set_live_status(self, text: str) -> None:
        self.live.setText(text)
        self.live.setVisible(bool(text))

    def closeEvent(self, event):
        if self.draft.dirty:
            answer = QMessageBox.question(
                self, 'Kilépés', 'Mented a módosításokat?',
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel)
            if answer == QMessageBox.Cancel or (answer == QMessageBox.Save and not self.save()):
                event.ignore()
                return
        event.accept()
