# SPDX-License-Identifier: GPL-2.0-or-later
"""TOML config file: load, save and locate.

    [default]
    profile = "general"

    [[profile]]
    name = "browser"
    dpi_stages = [400, 800, 1600, 3200, 6400]
    dpi_active = 3
    [profile.buttons]
    button4 = "ctrl+w"
    button5 = "key:8"

    [[rule]]
    match_process = "firefox"    # or match_class / match_title (regex)
    profile = "browser"
"""
from __future__ import annotations

import os
import re
import sys
import tomllib
from pathlib import Path

import tomli_w

from .model import (
    Config,
    Profile,
    Rule,
    button_id,
    button_name,
    format_action,
    parse_action,
)

APP_NAME = 'basilisk-profiler'


class ConfigError(ValueError):
    pass


def config_dir() -> Path:
    if sys.platform == 'win32':
        return Path(os.environ.get('APPDATA', Path.home() / 'AppData' / 'Roaming')) / APP_NAME
    base = os.environ.get('XDG_CONFIG_HOME') or Path.home() / '.config'
    return Path(base) / APP_NAME


def config_path() -> Path:
    return config_dir() / 'config.toml'


def parse(data: dict) -> Config:
    try:
        profiles = {}
        for entry in data.get('profile', []):
            name = entry['name']
            if name in profiles:
                raise ConfigError(f'duplicate profile {name!r}')
            buttons = {button_id(b): parse_action(a) for b, a in entry.get('buttons', {}).items()}
            profiles[name] = Profile(
                name=name,
                dpi_stages=tuple(entry['dpi_stages']) if 'dpi_stages' in entry else None,
                dpi_active=entry.get('dpi_active'),
                buttons=buttons,
                onboard_slot=entry.get('onboard_slot'),
            )
            profiles[name].dpi()  # validates DPI values and the active stage
        rules = tuple(Rule(profile=r['profile'], match_process=r.get('match_process'),
                           match_class=r.get('match_class'), match_title=r.get('match_title'))
                      for r in data.get('rule', []))
        return Config(profiles, rules, data.get('default', {}).get('profile'))
    except ConfigError:
        raise
    except (KeyError, TypeError, ValueError, re.error) as e:
        raise ConfigError(f'invalid config: {e}') from e


def load(path: Path) -> Config:
    try:
        with open(path, 'rb') as f:
            return parse(tomllib.load(f))
    except tomllib.TOMLDecodeError as e:
        raise ConfigError(f'{path}: {e}') from e


def dump(config: Config) -> dict:
    data: dict = {}
    if config.default_profile:
        data['default'] = {'profile': config.default_profile}
    data['profile'] = []
    for prof in config.profiles.values():
        entry: dict = {'name': prof.name}
        if prof.onboard_slot is not None:
            entry['onboard_slot'] = prof.onboard_slot
        if prof.dpi_stages:
            entry['dpi_stages'] = list(prof.dpi_stages)
        if prof.dpi_active:
            entry['dpi_active'] = prof.dpi_active
        if prof.buttons:
            entry['buttons'] = {button_name(b): format_action(a)
                                for b, a in sorted(prof.buttons.items())}
        data['profile'].append(entry)
    data['rule'] = []
    for rule in config.rules:
        entry = {k: v for k, v in (('match_process', rule.match_process),
                                    ('match_class', rule.match_class),
                                    ('match_title', rule.match_title)) if v}
        entry['profile'] = rule.profile
        data['rule'].append(entry)
    return data


def save(config: Config, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.tmp')
    tmp.write_bytes(tomli_w.dumps(dump(config)).encode())
    tmp.replace(path)


EXAMPLE = '''\
# basilisk-profiler config. The daemon reloads this file when it changes.

[default]
profile = "general"

[[profile]]
name = "general"
dpi_stages = [400, 800, 1600, 3200, 6400]
dpi_active = 3
[profile.buttons]
button4 = "mouse:4"
button5 = "mouse:5"

[[profile]]
name = "browser"
[profile.buttons]
button5 = "ctrl+t"
side_bottom = "ctrl+w"

[[rule]]
match_process = "firefox"
profile = "browser"

[[rule]]
match_process = "chrome"
profile = "browser"

[[rule]]
match_process = "brave"
profile = "browser"
'''


def ensure_exists(path: Path) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(EXAMPLE, encoding='utf-8')
