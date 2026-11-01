# SPDX-License-Identifier: GPL-2.0-or-later
import tomllib

import pytest

from basilisk_profiler.core import config as cfg
from basilisk_profiler.core import keys
from basilisk_profiler.core import protocol as p
from basilisk_profiler.core.model import Rule, WindowInfo, button_id


def example():
    return cfg.parse(tomllib.loads(cfg.EXAMPLE))


def test_example_config_parses():
    config = example()
    assert set(config.profiles) == {'general', 'browser'}
    assert config.default_profile == 'general'
    browser = config.profiles['browser']
    assert browser.buttons[0x05] == p.KeyAction(keys.usage('KEY_T'), keys.Modifier.LEFT_CTRL)
    assert browser.buttons[0x0F] == p.KeyAction(keys.usage('KEY_W'), keys.Modifier.LEFT_CTRL)
    assert browser.dpi() is None
    assert config.profiles['general'].dpi().active == 3


def test_dump_and_parse_round_trip(tmp_path):
    config = example()
    path = tmp_path / 'config.toml'
    cfg.save(config, path)
    assert cfg.load(path) == config


@pytest.mark.parametrize('process,expected', [
    ('firefox', 'browser'),
    ('FIREFOX.EXE', 'browser'),
    ('chrome', 'browser'),
    ('code', 'general'),
    ('', 'general'),
])
def test_rules_by_process(process, expected):
    assert example().profile_for(WindowInfo(process=process)).name == expected


def test_rule_regex_class_and_title():
    rule = Rule('x', match_class='^Mozilla', match_title='youtube')
    assert rule.matches(WindowInfo(wm_class='MozillaWindowClass', title='Music - YouTube'))
    assert not rule.matches(WindowInfo(wm_class='MozillaWindowClass', title='Docs'))
    assert not rule.matches(WindowInfo(wm_class='Chrome_WidgetWin_1', title='YouTube'))


def test_rule_needs_condition():
    with pytest.raises(ValueError):
        Rule('x')


def test_first_rule_wins_and_no_default():
    data = {
        'profile': [{'name': 'a'}, {'name': 'b'}],
        'rule': [{'match_title': 'doc', 'profile': 'a'}, {'match_title': '.', 'profile': 'b'}],
    }
    config = cfg.parse(data)
    assert config.profile_for(WindowInfo(title='my doc')).name == 'a'
    assert config.profile_for(WindowInfo(title='x')).name == 'b'
    assert config.profile_for(WindowInfo(title='')) is None


@pytest.mark.parametrize('data', [
    {'profile': [{'name': 'a'}], 'rule': [{'match_process': 'x', 'profile': 'missing'}]},
    {'profile': [{'name': 'a'}], 'default': {'profile': 'missing'}},
    {'profile': [{'name': 'a'}, {'name': 'a'}]},
    {'profile': [{'name': 'a', 'buttons': {'button9': 'ctrl+w'}}]},
    {'profile': [{'name': 'a', 'buttons': {'button4': 'hyper+w'}}]},
    {'profile': [{'name': 'a', 'dpi_stages': [50]}]},
    {'profile': [{'name': 'a', 'dpi_stages': [800], 'dpi_active': 2}]},
    {'profile': [{'name': 'a'}], 'rule': [{'match_class': '(', 'profile': 'a'}]},
    {'profile': [{'dpi_stages': [800]}]},
])
def test_invalid_configs(data):
    with pytest.raises(cfg.ConfigError):
        cfg.parse(data)


def test_bad_toml_is_config_error(tmp_path):
    path = tmp_path / 'c.toml'
    path.write_text('[[profile]\n')
    with pytest.raises(cfg.ConfigError):
        cfg.load(path)


def test_button_ids():
    assert button_id('Button5') == 0x05
    assert button_id('0x34') == 0x34


def test_profile_reports():
    general = example().profiles['general']
    commands = [r.command for r in general.reports()]
    assert commands == [(0x04, 0x06), (0x02, 0x0C), (0x02, 0x0C)]
