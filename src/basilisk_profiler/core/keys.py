# SPDX-License-Identifier: GPL-2.0-or-later
"""HID keyboard usage ids and modifier bits, named like Synapse (``KEY_E``)."""
from __future__ import annotations

import enum
import string


class Modifier(enum.IntFlag):
    LEFT_CTRL = 0x01
    LEFT_SHIFT = 0x02
    LEFT_ALT = 0x04
    LEFT_GUI = 0x08
    RIGHT_CTRL = 0x10
    RIGHT_SHIFT = 0x20
    RIGHT_ALT = 0x40
    RIGHT_GUI = 0x80


USAGES: dict[str, int] = {}
USAGES.update({f'KEY_{c}': 0x04 + i for i, c in enumerate(string.ascii_uppercase)})
USAGES.update({f'KEY_{d}': 0x1E + i for i, d in enumerate('1234567890')})
USAGES.update({f'KEY_F{n}': 0x3A + n - 1 for n in range(1, 13)})
USAGES.update({
    'KEY_ENTER': 0x28, 'KEY_ESC': 0x29, 'KEY_BACKSPACE': 0x2A, 'KEY_TAB': 0x2B,
    'KEY_SPACE': 0x2C, 'KEY_MINUS': 0x2D, 'KEY_EQUAL': 0x2E, 'KEY_LEFTBRACE': 0x2F,
    'KEY_RIGHTBRACE': 0x30, 'KEY_BACKSLASH': 0x31, 'KEY_SEMICOLON': 0x33,
    'KEY_APOSTROPHE': 0x34, 'KEY_GRAVE': 0x35, 'KEY_COMMA': 0x36, 'KEY_DOT': 0x37,
    'KEY_SLASH': 0x38, 'KEY_CAPSLOCK': 0x39, 'KEY_PRINTSCREEN': 0x46,
    'KEY_SCROLLLOCK': 0x47, 'KEY_PAUSE': 0x48, 'KEY_INSERT': 0x49, 'KEY_HOME': 0x4A,
    'KEY_PAGEUP': 0x4B, 'KEY_DELETE': 0x4C, 'KEY_END': 0x4D, 'KEY_PAGEDOWN': 0x4E,
    'KEY_RIGHT': 0x4F, 'KEY_LEFT': 0x50, 'KEY_DOWN': 0x51, 'KEY_UP': 0x52,
})
NAMES: dict[int, str] = {v: k for k, v in USAGES.items()}


def usage(name: str) -> int:
    try:
        return USAGES[name.upper()]
    except KeyError:
        raise ValueError(f'unknown key name: {name}') from None


def name(usage_id: int) -> str:
    return NAMES.get(usage_id, f'0x{usage_id:02X}')
