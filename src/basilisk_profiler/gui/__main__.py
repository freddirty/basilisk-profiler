# SPDX-License-Identifier: GPL-2.0-or-later
"""``python -m basilisk_profiler.gui [--config PATH]``: settings window on its own."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from ..core import config as cfg
from .main_window import MainWindow


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='basilisk-profiler-gui')
    parser.add_argument('--config', type=Path, default=cfg.config_path())
    args = parser.parse_args(argv)
    app = QApplication(sys.argv)
    window = MainWindow(args.config)
    window.show()
    return app.exec()


if __name__ == '__main__':
    sys.exit(main())
