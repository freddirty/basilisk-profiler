# SPDX-License-Identifier: GPL-2.0-or-later
"""Editable copy of the config for the GUI (no Qt here, so it is unit-testable).

Holds the same plain-dict shape as the TOML file; ``config()`` validates it through the
normal loader, so the GUI can never save something the daemon would reject.
"""
from __future__ import annotations

import copy
from pathlib import Path

import tomli_w

from ..core import config as cfg
from ..core.model import Config, Profile, button_name, format_action

RULE_FIELDS = ('match_process', 'match_class', 'match_title')


class ConfigDraft:
    def __init__(self, data: dict | None = None):
        data = copy.deepcopy(data or {})
        self.profiles: list[dict] = data.get('profile', [])
        self.rules: list[dict] = data.get('rule', [])
        self.default: str | None = data.get('default', {}).get('profile')
        self.dirty = False

    @classmethod
    def from_config(cls, config: Config) -> ConfigDraft:
        return cls(cfg.dump(config))

    @classmethod
    def load(cls, path: Path) -> ConfigDraft:
        return cls.from_config(cfg.load(path))

    def data(self) -> dict:
        data: dict = {}
        if self.default:
            data['default'] = {'profile': self.default}
        data['profile'] = copy.deepcopy(self.profiles)
        data['rule'] = copy.deepcopy(self.rules)
        return data

    def config(self) -> Config:
        return cfg.parse(self.data())

    def save(self, path: Path) -> None:
        self.config()  # validate first
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix('.tmp')
        tmp.write_bytes(tomli_w.dumps(self.data()).encode())
        tmp.replace(path)
        self.dirty = False

    # --- profiles --------------------------------------------------------------

    def names(self) -> list[str]:
        return [prof['name'] for prof in self.profiles]

    def profile(self, name: str) -> dict:
        for prof in self.profiles:
            if prof['name'] == name:
                return prof
        raise KeyError(name)

    def unique_name(self, base: str) -> str:
        names = set(self.names())
        if base not in names:
            return base
        n = 2
        while f'{base} ({n})' in names:
            n += 1
        return f'{base} ({n})'

    def add_profile(self, name: str, template: dict | None = None) -> str:
        name = self.unique_name(name.strip() or 'profil')
        prof = copy.deepcopy(template) if template else {}
        prof['name'] = name
        self.profiles.append(prof)
        if self.default is None:
            self.default = name
        self.dirty = True
        return name

    def add_imported(self, profile: Profile) -> str:
        entry = cfg.dump(Config({profile.name: profile}))['profile'][0]
        return self.add_profile(profile.name, entry)

    def duplicate(self, name: str) -> str:
        return self.add_profile(f'{name} másolat', self.profile(name))

    def rename(self, old: str, new: str) -> str:
        new = new.strip()
        if not new or new == old:
            return old
        if new in self.names():
            raise ValueError(f'már van ilyen nevű profil: {new}')
        self.profile(old)['name'] = new
        for rule in self.rules:
            if rule['profile'] == old:
                rule['profile'] = new
        if self.default == old:
            self.default = new
        self.dirty = True
        return new

    def delete(self, name: str) -> None:
        self.profiles.remove(self.profile(name))
        self.rules = [r for r in self.rules if r['profile'] != name]
        if self.default == name:
            self.default = self.profiles[0]['name'] if self.profiles else None
        self.dirty = True

    def set_default(self, name: str) -> None:
        self.profile(name)
        self.default = name
        self.dirty = True

    # --- profile contents --------------------------------------------------------

    def button(self, profile: str, button: int) -> str | None:
        return self.profile(profile).get('buttons', {}).get(button_name(button))

    def set_button(self, profile: str, button: int, action: str | None) -> None:
        """``action`` in config syntax (``ctrl+w``, ``mouse:4``); None = factory default."""
        buttons = self.profile(profile).setdefault('buttons', {})
        if action is None:
            buttons.pop(button_name(button), None)
        else:
            buttons[button_name(button)] = action
        if not buttons:
            del self.profile(profile)['buttons']
        self.dirty = True

    def dpi(self, profile: str) -> tuple[list[int] | None, int | None]:
        prof = self.profile(profile)
        return prof.get('dpi_stages'), prof.get('dpi_active')

    def set_dpi(self, profile: str, stages: list[int] | None, active: int | None) -> None:
        prof = self.profile(profile)
        if stages:
            prof['dpi_stages'] = list(stages)
            prof['dpi_active'] = min(max(active or 1, 1), len(stages))
        else:
            prof.pop('dpi_stages', None)
            prof.pop('dpi_active', None)
        self.dirty = True

    def onboard_slot(self, profile: str) -> int | None:
        return self.profile(profile).get('onboard_slot')

    def set_onboard_slot(self, profile: str, slot: int | None) -> None:
        """Assign an onboard slot (1..4); a profile already in that slot gives it up."""
        if slot is not None:
            for prof in self.profiles:
                if prof.get('onboard_slot') == slot:
                    del prof['onboard_slot']
            self.profile(profile)['onboard_slot'] = slot
        else:
            self.profile(profile).pop('onboard_slot', None)
        self.dirty = True

    # --- rules -------------------------------------------------------------------

    def add_rule(self, field: str, pattern: str, profile: str) -> int:
        if field not in RULE_FIELDS:
            raise ValueError(field)
        self.rules.append({field: pattern, 'profile': profile})
        self.dirty = True
        return len(self.rules) - 1

    def set_rule(self, index: int, field: str, pattern: str, profile: str) -> None:
        if field not in RULE_FIELDS:
            raise ValueError(field)
        self.rules[index] = {field: pattern, 'profile': profile}
        self.dirty = True

    def rule_parts(self, index: int) -> tuple[str, str, str]:
        rule = self.rules[index]
        field = next((f for f in RULE_FIELDS if f in rule), RULE_FIELDS[0])
        return field, rule.get(field, ''), rule['profile']

    def remove_rule(self, index: int) -> None:
        del self.rules[index]
        self.dirty = True

    def move_rule(self, index: int, delta: int) -> int:
        target = index + delta
        if 0 <= target < len(self.rules):
            self.rules[index], self.rules[target] = self.rules[target], self.rules[index]
            self.dirty = True
            return target
        return index


MEDIA_LABELS = {'play_pause': 'lejátszás/szünet', 'next': 'következő szám',
                'previous': 'előző szám', 'stop': 'leállítás', 'volume_up': 'hangerő fel',
                'volume_down': 'hangerő le', 'mute': 'némítás'}


def describe_action(action: str | None) -> str:
    """Short Hungarian label for the mouse view."""
    if action is None:
        return 'alapértelmezett'
    if action == 'mouse:9':
        return 'görgetés fel'
    if action.startswith('mouse:'):
        return f'egérgomb {action[6:]}'
    if action.startswith('media:'):
        return MEDIA_LABELS.get(action[6:], 'multimédia')
    if action == 'dpi:stage_up':
        return 'DPI-fokozat fel'
    if action == 'dpi:cycle':
        return 'DPI-fokozatok körbe'
    if action.startswith('dpi:clutch'):
        return f'clutch {action.split(":")[2]} DPI'
    if action == 'profile:cycle':
        return 'következő profil'
    if action == 'disabled':
        return 'letiltva'
    if action.startswith('raw:'):
        return 'egyéb funkció'
    return action.upper().replace('+', ' + ')


__all__ = ['ConfigDraft', 'describe_action', 'format_action']
