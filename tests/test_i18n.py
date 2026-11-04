# SPDX-License-Identifier: GPL-2.0-or-later
import ast
import string
from pathlib import Path

import pytest

from basilisk_profiler import i18n
from basilisk_profiler.core.ui_settings import UiSettings, ui_settings_path
from basilisk_profiler.gui.draft import ConfigDraft, describe_action
from basilisk_profiler.i18n import hu, tr

SRC = Path(__file__).resolve().parents[1] / 'src' / 'basilisk_profiler'
HUNGARIAN_LETTERS = set('áéíóöőúüűÁÉÍÓÖŐÚÜŰ')


def marked_strings() -> dict[str, str]:
    """Every literal passed to tr() or N_() in the package -> where it is."""
    found = {}
    for path in sorted(SRC.rglob('*.py')):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
                    and node.func.id in ('tr', 'N_') and node.args
                    and isinstance(node.args[0], ast.Constant)
                    and isinstance(node.args[0].value, str)):
                found.setdefault(node.args[0].value, f'{path.name}:{node.lineno}')
    return found


def fields(text: str) -> set[str]:
    return {name for _, name, _, _ in string.Formatter().parse(text) if name is not None}


def test_every_marked_string_is_translated():
    missing = {s: where for s, where in marked_strings().items() if s not in hu.CATALOG}
    assert not missing


def test_no_stale_translations():
    assert not set(hu.CATALOG) - set(marked_strings())


@pytest.mark.parametrize('key', sorted(hu.CATALOG))
def test_translation_keeps_the_fields(key):
    assert fields(hu.CATALOG[key]) == fields(key)


def test_no_hungarian_left_in_the_code():
    """Interface texts go through the catalogue; the code itself stays English."""
    offenders = []
    for path in sorted(SRC.rglob('*.py')):
        if path.parent.name == 'i18n':
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and HUNGARIAN_LETTERS & set(node.value)):
                offenders.append(f'{path.name}:{node.lineno} {node.value[:40]!r}')
    assert not offenders


def test_tr_english_and_hungarian():
    i18n.set_language('en')
    assert tr('Pause') == 'Pause'
    assert tr('Stage {n}', n=2) == 'Stage 2'
    assert tr('not in any catalogue') == 'not in any catalogue'
    i18n.set_language('hu')
    assert tr('Pause') == 'Szüneteltetés'
    assert tr('Stage {n}', n=2) == '2. fokozat'
    assert tr('not in any catalogue') == 'not in any catalogue'


def test_english_labels():
    i18n.set_language('en')
    assert describe_action(None) == 'default'
    assert describe_action('mouse:4') == 'mouse button 4'
    assert describe_action('media:play_pause') == 'play/pause'
    assert describe_action('dpi:clutch:800') == 'clutch 800 DPI'
    d = ConfigDraft()
    d.add_profile('general')
    assert d.duplicate('general') == 'general copy'
    assert d.add_profile(' ') == 'profile'


@pytest.mark.parametrize(('env', 'expected'), [
    ({'LANG': 'hu_HU.UTF-8'}, 'hu'),
    ({'LANG': 'en_US.UTF-8'}, 'en'),
    ({'LANG': 'de_DE.UTF-8'}, 'en'),
    ({'LANG': 'C.UTF-8'}, 'en'),
    ({'LANGUAGE': 'de:hu', 'LANG': 'de_DE.UTF-8'}, 'hu'),
    ({'LC_ALL': 'hu_HU.UTF-8', 'LANG': 'en_US.UTF-8'}, 'hu'),
    ({'LC_MESSAGES': 'en_GB.UTF-8', 'LANG': 'hu_HU.UTF-8'}, 'en'),
])
def test_system_language_from_environment(monkeypatch, env, expected):
    monkeypatch.setattr(i18n.sys, 'platform', 'linux')
    for var in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG'):
        monkeypatch.delenv(var, raising=False)
    for var, value in env.items():
        monkeypatch.setenv(var, value)
    assert i18n.system_language() == expected


def test_resolve_and_set(monkeypatch):
    monkeypatch.setattr(i18n, 'system_language', lambda: 'hu')
    assert i18n.resolve('en') == 'en'
    assert i18n.resolve('auto') == 'hu'
    assert i18n.resolve(None) == 'hu'
    assert i18n.resolve('xx') == 'hu'  # an unknown stored value falls back to the system
    assert i18n.set_language('en') == 'en'
    assert i18n.language() == 'en'


def test_ui_settings_roundtrip(tmp_path):
    path = ui_settings_path(tmp_path / 'sub' / 'config.toml')
    assert path.name == 'tray.json'
    settings = UiSettings(path)
    assert settings.get('language', 'auto') == 'auto'
    settings.set('language', 'en')
    assert UiSettings(path).get('language', 'auto') == 'en'
    path.write_text('[1, 2]')  # not an object: ignored, not a crash
    assert UiSettings(path).get('language', 'auto') == 'auto'
