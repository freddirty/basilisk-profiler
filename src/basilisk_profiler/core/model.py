# SPDX-License-Identifier: GPL-2.0-or-later
"""Profile model: what the user configures, independent of how it is stored or applied."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import keys
from . import protocol as p

# Friendly button names used in config files. Ids not listed here can be given as "0x34".
BUTTON_IDS: dict[str, int] = {
    'button4': p.ButtonId.BUTTON4,  # rear side button
    'button5': p.ButtonId.BUTTON5,  # front side button
    'side_bottom': p.ButtonId.CLUTCH,  # sensitivity clutch (Synapse: DKM_SB_02)
    'wheel_click': p.ButtonId.WHEEL_CLICK,
    'tilt_left': p.ButtonId.TILT_LEFT,
    'tilt_right': p.ButtonId.TILT_RIGHT,
    'scroll_mode': p.ButtonId.SCROLL_MODE,
    'dpi_cycle': p.ButtonId.DPI_CYCLE,
    'profile': p.ButtonId.PROFILE,
}
BUTTON_NAMES = {v: k for k, v in BUTTON_IDS.items()}

# What a button does when a profile does not set it (as read from the device / Synapse).
# Written explicitly so a mapping from the previous profile does not linger.
DEFAULT_ACTIONS: dict[int, p.Action] = {
    p.ButtonId.SCROLL_MODE: p.ScrollModeAction(),
    p.ButtonId.WHEEL_CLICK: p.MouseButtonAction(3),
    p.ButtonId.BUTTON4: p.MouseButtonAction(4),
    p.ButtonId.BUTTON5: p.MouseButtonAction(5),
    p.ButtonId.CLUTCH: p.DpiAction(p.DpiFunction.CLUTCH, 400),
    p.ButtonId.TILT_LEFT: p.RawAction(p.ActionType.REPEAT_SCROLL, bytes.fromhex('680014')),
    p.ButtonId.TILT_RIGHT: p.RawAction(p.ActionType.REPEAT_SCROLL, bytes.fromhex('690014')),
    p.ButtonId.DPI_CYCLE: p.DpiAction(p.DpiFunction.CYCLE_UP),
    p.ButtonId.PROFILE: p.ProfileAction(p.ProfileFunction.CYCLE_UP),
}

# HID consumer-page usages offered for media keys
MEDIA_KEYS: dict[str, int] = {
    'play_pause': 0xCD, 'next': 0xB5, 'previous': 0xB6, 'stop': 0xB7,
    'volume_up': 0xE9, 'volume_down': 0xEA, 'mute': 0xE2,
}
MEDIA_NAMES = {v: k for k, v in MEDIA_KEYS.items()}
DPI_FUNCTIONS = {'stage_up': p.DpiFunction.STAGE_UP, 'cycle': p.DpiFunction.CYCLE_UP}

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
    """``mouse:5``, ``key:8``, ``ctrl+w``, ``KEY_E``, ``ctrl+shift+t``, ``media:play_pause``,
    ``dpi:stage_up``, ``dpi:cycle``, ``dpi:clutch:400``, ``profile:cycle``, ``disabled``."""
    text = text.strip().lower()
    if text == 'disabled':
        return p.DisabledAction()
    if text.startswith('mouse:'):
        return p.MouseButtonAction(int(text[6:]))
    if text.startswith('media:'):
        name = text[6:]
        usage = MEDIA_KEYS.get(name)
        if usage is None:
            if not re.fullmatch(r'0x[0-9a-f]{1,4}', name):
                raise ValueError(f'unknown media key: {name}')
            usage = int(name, 16)
        return p.ConsumerAction(usage)
    if text.startswith('dpi:'):
        parts = text.split(':')
        if parts[1] == 'clutch':
            dpi = int(parts[2]) if len(parts) > 2 else 400
            if not p.DPI_MIN <= dpi <= p.DPI_MAX:
                raise ValueError(f'clutch DPI {dpi} out of range')
            return p.DpiAction(p.DpiFunction.CLUTCH, dpi)
        if parts[1] not in DPI_FUNCTIONS:
            raise ValueError(f'unknown DPI function: {parts[1]}')
        return p.DpiAction(DPI_FUNCTIONS[parts[1]])
    if text == 'profile:cycle':
        return p.ProfileAction(p.ProfileFunction.CYCLE_UP)
    if text == 'scroll_mode:toggle':
        return p.ScrollModeAction()
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
    if isinstance(action, p.DisabledAction):
        return 'disabled'
    if isinstance(action, p.ConsumerAction):
        return f"media:{MEDIA_NAMES.get(action.usage, f'0x{action.usage:04x}')}"
    if isinstance(action, p.DpiAction):
        if action.function == p.DpiFunction.CLUTCH:
            return f'dpi:clutch:{action.dpi}'
        names = {v: k for k, v in DPI_FUNCTIONS.items()}
        if action.function in names:
            return f'dpi:{names[action.function]}'
    if isinstance(action, p.ProfileAction) and action.function == p.ProfileFunction.CYCLE_UP:
        return 'profile:cycle'
    if isinstance(action, p.ScrollModeAction):
        return 'scroll_mode:toggle'
    return f'raw:{action.action_type:02x}:{action.payload().hex()}'


def parse_any_action(text: str) -> p.Action:
    """Like parse_action, but also accepts the ``raw:TT:HEX`` form format_action produces."""
    if text.strip().lower().startswith('raw:'):
        _, type_hex, data_hex = text.strip().split(':', 2)
        return p.RawAction(int(type_hex, 16), bytes.fromhex(data_hex))
    return parse_action(text)


@dataclass(frozen=True)
class Profile:
    name: str
    dpi_stages: tuple[int, ...] | None = None  # None = keep what the mouse has
    dpi_active: int | None = None  # 1-based
    buttons: dict[int, p.Action] = field(default_factory=dict)
    onboard_slot: int | None = None  # 1..4 as in Synapse's On-Board Memory list

    def dpi(self, store: int = p.STORE_LIVE) -> p.DpiStages | None:
        if not self.dpi_stages:
            return None
        active = self.dpi_active or 1
        return p.DpiStages(tuple(p.DpiStage(v, v) for v in self.dpi_stages), active=active,
                           store=store)

    def reports(self, store: int = p.STORE_LIVE) -> list[p.Report]:
        """Everything needed to write this profile to ``store`` (default: the live slot).

        Onboard slots also get the current DPI (04/05), as Synapse writes it there.
        """
        reports = []
        if (stages := self.dpi(store)) is not None:
            reports.append(p.set_dpi_stages(stages))
            if store != p.STORE_LIVE:
                reports.append(p.set_dpi_xy(stages.stages[stages.active - 1].x, store=store))
        buttons = {**DEFAULT_ACTIONS, **self.buttons}
        for button, action in sorted(buttons.items()):
            reports.append(p.set_button_mapping(p.ButtonMapping(button, action, store=store)))
        return reports


ONBOARD_SLOTS = 4  # Synapse colours: 1 red, 2 green, 3 blue, 4 cyan


def onboard_store(slot: int) -> int:
    """Onboard slot 1..4 (as shown in Synapse) -> device store id 0x02..0x05."""
    if not 1 <= slot <= ONBOARD_SLOTS:
        raise ValueError(f'onboard slot must be 1..{ONBOARD_SLOTS}, got {slot}')
    return p.ONBOARD_STORES[slot - 1]


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
        slots = [prof.onboard_slot for prof in self.profiles.values() if prof.onboard_slot]
        for slot in slots:
            onboard_store(slot)
        if len(slots) != len(set(slots)):
            raise ValueError('two profiles use the same onboard slot')
        for rule in self.rules:
            if rule.profile not in names:
                raise ValueError(f'rule refers to unknown profile {rule.profile!r}')
        if self.default_profile and self.default_profile not in names:
            raise ValueError(f'unknown default profile {self.default_profile!r}')

    def onboard(self) -> dict[int, Profile]:
        """Onboard slot -> profile, for the profiles kept in the mouse."""
        return {prof.onboard_slot: prof for prof in self.profiles.values() if prof.onboard_slot}

    def profile_for(self, window: WindowInfo) -> Profile | None:
        """First matching rule wins; otherwise the default profile (or None)."""
        for rule in self.rules:
            if rule.matches(window):
                return self.profiles[rule.profile]
        return self.profiles.get(self.default_profile) if self.default_profile else None
