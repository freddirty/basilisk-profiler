# SPDX-License-Identifier: GPL-2.0-or-later
"""Profile model: what the user configures, independent of how it is stored or applied."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import keys
from . import protocol as p

# Friendly button names used in config files. Ids not listed here can be given as "0x34".
BUTTON_IDS: dict[str, int] = {
    'button4': 0x04,  # rear side button
    'button5': 0x05,  # front side button
    'side_bottom': 0x0F,  # lower side button (Synapse: DKM_SB_02)
}
BUTTON_NAMES = {v: k for k, v in BUTTON_IDS.items()}

MODIFIER_NAMES = {
    'ctrl': keys.Modifier.LEFT_CTRL, 'shift': keys.Modifier.LEFT_SHIFT,
    'alt': keys.Modifier.LEFT_ALT, 'win': keys.Modifier.LEFT_GUI,
    'rctrl': keys.Modifier.RIGHT_CTRL, 'rshift': keys.Modifier.RIGHT_SHIFT,
    'altgr': keys.Modifier.RIGHT_ALT, 'rwin': keys.Modifier.RIGHT_GUI,
}


def button_id(name: str) -> int:
    name = name.strip().lower()
    if name in BUTTON_IDS:
        return BUTTON_IDS[name]
    if re.fullmatch(r'0x[0-9a-f]{1,2}', name):
        return int(name, 16)
    raise ValueError(f'unknown button: {name}')


def button_name(button: int) -> str:
    return BUTTON_NAMES.get(button, f'0x{button:02x}')


def parse_action(text: str) -> p.Action:
    """``mouse:5``, ``key:8``, ``ctrl+w``, ``KEY_E``, ``ctrl+shift+t``."""
    text = text.strip().lower()
    if text.startswith('mouse:'):
        return p.MouseButtonAction(int(text[6:]))
    if text.startswith('key:'):
        text = text[4:]
    *mods, key = text.split('+')
    modifiers = 0
    for m in mods:
        if m not in MODIFIER_NAMES:
            raise ValueError(f'unknown modifier: {m}')
        modifiers |= MODIFIER_NAMES[m]
    name = key.upper() if key.upper().startswith('KEY_') else f'KEY_{key.upper()}'
    return p.KeyAction(keys.usage(name), modifiers)


def format_action(action: p.Action) -> str:
    if isinstance(action, p.MouseButtonAction):
        return f'mouse:{action.button}'
    if isinstance(action, p.KeyAction):
        mods = [n for n, bit in MODIFIER_NAMES.items() if action.modifiers & bit]
        return '+'.join([*mods, keys.name(action.usage).removeprefix('KEY_').lower()])
    return f'raw:{action.action_type:02x}:{action.payload().hex()}'


@dataclass(frozen=True)
class Profile:
    name: str
    dpi_stages: tuple[int, ...] | None = None  # None = keep what the mouse has
    dpi_active: int | None = None  # 1-based
    buttons: dict[int, p.Action] = field(default_factory=dict)
    onboard_slot: int | None = None  # 0x02..0x05 once onboard sync lands

    def dpi(self) -> p.DpiStages | None:
        if not self.dpi_stages:
            return None
        active = self.dpi_active or 1
        return p.DpiStages(tuple(p.DpiStage(v, v) for v in self.dpi_stages), active=active)

    def reports(self) -> list[p.Report]:
        """Everything needed to apply this profile to the live slot."""
        reports = []
        if (stages := self.dpi()) is not None:
            reports.append(p.set_dpi_stages(stages))
        for button, action in sorted(self.buttons.items()):
            reports.append(p.set_button_mapping(p.ButtonMapping(button, action)))
        return reports


@dataclass(frozen=True)
class WindowInfo:
    process: str = ''  # executable name without extension, lower case ("firefox")
    wm_class: str = ''  # Windows window class / X11 WM_CLASS
    title: str = ''


@dataclass(frozen=True)
class Rule:
    profile: str
    match_process: str | None = None  # exact, case-insensitive, ".exe" optional
    match_class: str | None = None  # regex, case-insensitive
    match_title: str | None = None  # regex, case-insensitive

    def __post_init__(self):
        if not (self.match_process or self.match_class or self.match_title):
            raise ValueError(f'rule for {self.profile!r} has no match_* condition')
        for pattern in (self.match_class, self.match_title):
            if pattern:
                re.compile(pattern)

    def matches(self, window: WindowInfo) -> bool:
        if self.match_process and \
                normalize_process(self.match_process) != normalize_process(window.process):
            return False
        if self.match_class and not re.search(self.match_class, window.wm_class, re.I):
            return False
        if self.match_title and not re.search(self.match_title, window.title, re.I):
            return False
        return True


def normalize_process(name: str) -> str:
    name = name.strip().lower().replace('\\', '/').rsplit('/', 1)[-1]
    return name.removesuffix('.exe')


@dataclass(frozen=True)
class Config:
    profiles: dict[str, Profile]
    rules: tuple[Rule, ...] = ()
    default_profile: str | None = None

    def __post_init__(self):
        names = set(self.profiles)
        for rule in self.rules:
            if rule.profile not in names:
                raise ValueError(f'rule refers to unknown profile {rule.profile!r}')
        if self.default_profile and self.default_profile not in names:
            raise ValueError(f'unknown default profile {self.default_profile!r}')

    def profile_for(self, window: WindowInfo) -> Profile | None:
        """First matching rule wins; otherwise the default profile (or None)."""
        for rule in self.rules:
            if rule.matches(window):
                return self.profiles[rule.profile]
        return self.profiles.get(self.default_profile) if self.default_profile else None
