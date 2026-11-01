# SPDX-License-Identifier: GPL-2.0-or-later
import tomllib

import pytest

from basilisk_profiler.core import config as cfg
from basilisk_profiler.core import keys
from basilisk_profiler.core import protocol as p
from basilisk_profiler.core.model import DEFAULT_ACTIONS, Rule, WindowInfo, button_id


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
    # the DPI table, then one 02/0C per button: the profile's own and factory defaults
    assert commands[0] == (0x04, 0x06)
    assert commands[1:] == [(0x02, 0x0C)] * len(DEFAULT_ACTIONS)


def test_unset_buttons_get_factory_defaults():
    browser = example().profiles['browser']
    actions = {p.parse_button_mapping(r).button: p.parse_button_mapping(r).action
               for r in browser.reports() if r.command == (0x02, 0x0C)}
    assert actions[0x04] == p.MouseButtonAction(4)
    assert actions[0x0F] == p.KeyAction(keys.usage('KEY_W'), keys.Modifier.LEFT_CTRL)


def test_raw_action_round_trips_through_config(tmp_path):
    data = {'profile': [{'name': 'a', 'buttons': {'0x34': 'raw:0e:680014'}}]}
    config = cfg.parse(data)
    assert config.profiles['a'].buttons[0x34] == p.RawAction(0x0E, bytes.fromhex('680014'))
    path = tmp_path / 'c.toml'
    cfg.save(config, path)
    assert cfg.load(path) == config


@pytest.mark.parametrize('text', [
    'disabled', 'mouse:9', 'media:play_pause', 'media:0x0183', 'dpi:stage_up', 'dpi:cycle',
    'dpi:clutch:800', 'profile:cycle', 'ctrl+shift+t', 'raw:0e:680014',
])
def test_action_syntax_round_trips(text):
    from basilisk_profiler.core.model import format_action, parse_any_action
    assert format_action(parse_any_action(text)) == text


@pytest.mark.parametrize('text', ['media:nope', 'dpi:turbo', 'dpi:clutch:50'])
def test_bad_action_syntax(text):
    from basilisk_profiler.core.model import parse_action
    with pytest.raises(ValueError):
        parse_action(text)


def test_new_button_names():
    assert button_id('wheel_click') == 0x03
    assert button_id('scroll_mode') == 0x6A
    assert button_id('profile') == 0x0E
