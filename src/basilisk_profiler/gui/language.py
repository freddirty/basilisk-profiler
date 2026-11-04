# SPDX-License-Identifier: GPL-2.0-or-later
"""Switch the interface language, including Qt's own texts (OK/Cancel, file dialogs)."""
from __future__ import annotations

from PySide6.QtCore import QLibraryInfo, QLocale, QTranslator
from PySide6.QtWidgets import QApplication

from .. import i18n

_qt_translator: QTranslator | None = None


def apply_language(app: QApplication, setting: str | None) -> str:
    """``setting``: 'auto', 'en' or 'hu'. Returns the language now in use."""
    global _qt_translator
    code = i18n.set_language(setting)
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator = None
    QLocale.setDefault(QLocale(code))
    if code != 'en':
        translator = QTranslator(app)
        folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if translator.load(f'qtbase_{code}', folder):
            app.installTranslator(translator)
            _qt_translator = translator
    return code
