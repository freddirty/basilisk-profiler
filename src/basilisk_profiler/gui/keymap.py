# SPDX-License-Identifier: GPL-2.0-or-later
"""Qt key events -> action strings in config syntax (``ctrl+shift+t``)."""
from __future__ import annotations

import string

from PySide6.QtCore import Qt

from ..core import keys

_SPECIAL = {
    Qt.Key_Return: 'enter', Qt.Key_Enter: 'enter', Qt.Key_Escape: 'esc',
    Qt.Key_Backspace: 'backspace', Qt.Key_Tab: 'tab', Qt.Key_Space: 'space',
    Qt.Key_Minus: 'minus', Qt.Key_Equal: 'equal', Qt.Key_BracketLeft: 'leftbrace',
    Qt.Key_BracketRight: 'rightbrace', Qt.Key_Backslash: 'backslash',
    Qt.Key_Semicolon: 'semicolon', Qt.Key_Apostrophe: 'apostrophe',
    Qt.Key_QuoteLeft: 'grave', Qt.Key_Comma: 'comma', Qt.Key_Period: 'dot',
    Qt.Key_Slash: 'slash', Qt.Key_CapsLock: 'capslock', Qt.Key_Print: 'printscreen',
    Qt.Key_ScrollLock: 'scrolllock', Qt.Key_Pause: 'pause', Qt.Key_Insert: 'insert',
    Qt.Key_Home: 'home', Qt.Key_PageUp: 'pageup', Qt.Key_Delete: 'delete',
    Qt.Key_End: 'end', Qt.Key_PageDown: 'pagedown', Qt.Key_Right: 'right',
    Qt.Key_Left: 'left', Qt.Key_Down: 'down', Qt.Key_Up: 'up',
}
_MODIFIER_KEYS = {Qt.Key_Control, Qt.Key_Shift, Qt.Key_Alt, Qt.Key_Meta, Qt.Key_AltGr}


def key_name(key: int) -> str | None:
    if Qt.Key_A <= key <= Qt.Key_Z:
        return string.ascii_lowercase[key - Qt.Key_A]
    if Qt.Key_0 <= key <= Qt.Key_9:
        return str(key - Qt.Key_0)
    if Qt.Key_F1 <= key <= Qt.Key_F12:
        return f'f{key - Qt.Key_F1 + 1}'
    return _SPECIAL.get(Qt.Key(key))


def action_from_key(key: int, modifiers: Qt.KeyboardModifier) -> str | None:
    """None while only modifiers are held or for keys the device cannot send."""
    if key in _MODIFIER_KEYS:
        return None
    name = key_name(key)
    if name is None or f'KEY_{name.upper()}' not in keys.USAGES:
        return None
    parts = []
    if modifiers & Qt.ControlModifier:
        parts.append('ctrl')
    if modifiers & Qt.ShiftModifier:
        parts.append('shift')
    if modifiers & Qt.AltModifier:
        parts.append('alt')
    if modifiers & Qt.MetaModifier:
        parts.append('win')
    return '+'.join([*parts, name])
