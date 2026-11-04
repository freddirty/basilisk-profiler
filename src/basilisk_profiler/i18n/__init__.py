# SPDX-License-Identifier: GPL-2.0-or-later
"""User interface language: English source strings, translated through small catalogues.

    from ..i18n import N_, tr
    tr('Profile: {name}', name=name)     # translated now
    TITLES = {'button4': N_('Back side button')}   # marked here, translated where shown

The English text is the key; a catalogue (``hu.py``) maps it to the translation, and a
missing entry falls back to English. Only the user interface is translated: log messages,
config errors and the command line stay in English. No Qt here, so it is unit-testable;
``gui/language.py`` adds Qt's own translations of its standard dialogs.
"""
from __future__ import annotations

import locale
import os
import sys

from . import hu

AUTO = 'auto'
DEFAULT = 'en'
# language code -> its name in that language (shown untranslated in the language menu)
LANGUAGES = {'en': 'English', 'hu': 'Magyar'}
CATALOGS: dict[str, dict[str, str]] = {'en': {}, 'hu': hu.CATALOG}

_language = DEFAULT


def N_(text: str) -> str:
    """Mark a string for translation without translating it yet (module-level tables)."""
    return text


def tr(text: str, **values) -> str:
    """``text`` in the current language, with ``{name}`` fields filled from ``values``."""
    translated = CATALOGS[_language].get(text, text)
    return translated.format(**values) if values else translated


def language() -> str:
    return _language


def _code(name: str | None) -> str | None:
    """'hu_HU.UTF-8' -> 'hu' if that language is supported."""
    if not name:
        return None
    code = name.replace('-', '_').split('_')[0].split('.')[0].lower()
    return code if code in LANGUAGES else None


def system_language() -> str:
    """The desktop's language if it is supported, otherwise English."""
    if sys.platform == 'win32':
        try:
            import ctypes

            lang_id = ctypes.windll.kernel32.GetUserDefaultUILanguage()
            return {0x0E: 'hu', 0x09: 'en'}.get(lang_id & 0x3FF, DEFAULT)
        except (AttributeError, OSError):
            pass
    for var in ('LANGUAGE', 'LC_ALL', 'LC_MESSAGES', 'LANG'):
        value = os.environ.get(var)
        if value:
            # LANGUAGE is a priority list (hu:en); the first supported entry wins
            for part in value.split(':'):
                if code := _code(part):
                    return code
            if var != 'LANGUAGE':
                return DEFAULT  # the locale is set but not to a supported language
    try:
        return _code(locale.getlocale()[0]) or DEFAULT
    except ValueError:
        return DEFAULT


def resolve(setting: str | None) -> str:
    """A stored setting ('auto', 'en', 'hu', or anything else) -> a supported code."""
    if setting in LANGUAGES:
        return setting
    return system_language()


def set_language(setting: str | None) -> str:
    """Switch the language ('auto' or None = follow the system); returns the code in use."""
    global _language
    _language = resolve(setting)
    return _language


__all__ = ['AUTO', 'LANGUAGES', 'N_', 'language', 'resolve', 'set_language',
           'system_language', 'tr']
