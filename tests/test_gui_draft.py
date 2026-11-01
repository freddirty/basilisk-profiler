# SPDX-License-Identifier: GPL-2.0-or-later
import tomllib

import pytest

from basilisk_profiler.core import config as cfg
from basilisk_profiler.core.model import Profile
from basilisk_profiler.gui.draft import ConfigDraft, describe_action


def draft():
    return ConfigDraft(tomllib.loads(cfg.EXAMPLE))


def test_round_trip_matches_loader(tmp_path):
    d = draft()
    path = tmp_path / 'c.toml'
    d.save(path)
    assert cfg.load(path) == cfg.parse(tomllib.loads(cfg.EXAMPLE))
    assert not d.dirty


def test_add_duplicate_unique_names():
    d = draft()
    assert d.add_profile('browser') == 'browser (2)'
    assert d.duplicate('general') == 'general másolat'
    assert d.duplicate('general') == 'general másolat (2)'
    assert d.dirty


def test_rename_updates_rules_and_default():
    d = draft()
    d.rename('browser', 'web')
    d.rename('general', 'alap')
    assert {r['profile'] for r in d.rules} == {'web'}
    assert d.default == 'alap'
    with pytest.raises(ValueError):
        d.rename('web', 'alap')


def test_delete_removes_rules_and_moves_default():
    d = draft()
    d.delete('browser')
    assert d.rules == []
    d.delete('general')
    assert d.default is None and d.names() == []


def test_buttons_and_default_action():
    d = draft()
    d.set_button('general', 0x05, 'ctrl+shift+t')
    assert d.button('general', 0x05) == 'ctrl+shift+t'
    d.set_button('general', 0x05, None)
    d.set_button('general', 0x04, None)
    assert 'buttons' not in d.profile('general')
    assert d.config().profiles['general'].buttons == {}


def test_dpi_editing_clamps_active():
    d = draft()
    d.set_dpi('browser', [800, 1600], 5)
    assert d.dpi('browser') == ([800, 1600], 2)
    d.set_dpi('browser', None, None)
    assert d.dpi('browser') == (None, None)


def test_rules_edit_and_move():
    d = draft()
    i = d.add_rule('match_title', 'YouTube', 'general')
    assert d.rule_parts(i) == ('match_title', 'YouTube', 'general')
    assert d.move_rule(i, -1) == i - 1
    d.set_rule(0, 'match_class', '^Chrome', 'browser')
    assert d.rules[0] == {'match_class': '^Chrome', 'profile': 'browser'}
    d.remove_rule(0)
    assert len(d.rules) == 3


def test_invalid_draft_is_not_saved(tmp_path):
    d = draft()
    d.add_rule('match_class', '(', 'general')
    with pytest.raises(cfg.ConfigError):
        d.save(tmp_path / 'c.toml')
    assert not (tmp_path / 'c.toml').exists()


def test_add_imported_profile():
    d = draft()
    name = d.add_imported(Profile('browser', dpi_stages=(800,), dpi_active=1))
    assert name == 'browser (2)'
    assert d.dpi(name) == ([800], 1)


def test_describe_action():
    assert describe_action(None) == 'alapértelmezett'
    assert describe_action('mouse:4') == 'egérgomb 4'
    assert describe_action('ctrl+w') == 'CTRL + W'


def test_onboard_slot_moves_between_profiles():
    d = draft()
    d.set_onboard_slot('general', 2)
    d.set_onboard_slot('browser', 2)
    assert d.onboard_slot('general') is None and d.onboard_slot('browser') == 2
    assert d.config().onboard()[2].name == 'browser'
    d.set_onboard_slot('browser', None)
    assert d.config().onboard() == {}


def test_describe_new_actions():
    assert describe_action('media:play_pause') == 'lejátszás/szünet'
    assert describe_action('dpi:clutch:800') == 'clutch 800 DPI'
    assert describe_action('profile:cycle') == 'következő profil'
    assert describe_action('mouse:9') == 'görgetés fel'
