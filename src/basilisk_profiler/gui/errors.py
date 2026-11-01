# SPDX-License-Identifier: GPL-2.0-or-later
"""Unexpected exceptions: log them and show a dialog instead of a flashing traceback."""
from __future__ import annotations

import logging
import sys
import traceback

log = logging.getLogger('basilisk_profiler')


def install_excepthook() -> None:
    previous = sys.excepthook

    def hook(exc_type, exc, tb):
        if issubclass(exc_type, KeyboardInterrupt):
            previous(exc_type, exc, tb)
            return
        text = ''.join(traceback.format_exception(exc_type, exc, tb))
        log.error('unexpected error:\n%s', text)
        try:
            from PySide6.QtWidgets import QApplication, QMessageBox

            if QApplication.instance() is not None:
                box = QMessageBox(QMessageBox.Warning, 'Basilisk Profiler – hiba',
                                  f'Váratlan hiba történt: {exc}\n\n'
                                  'A részletek a naplófájlban vannak, és ide kattintva is '
                                  'kimásolhatók.')
                box.setDetailedText(text)
                box.exec()
        except Exception:  # noqa: BLE001 - the hook itself must never raise
            pass

    sys.excepthook = hook


def setup_logging(log_file, verbose: bool = False) -> None:
    """Log to ``log_file`` when there is no console (pythonw, frozen build)."""
    options = {}
    if sys.stderr is None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        options['filename'] = log_file
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO,
                        format='%(asctime)s %(levelname)s %(name)s %(message)s', **options)
