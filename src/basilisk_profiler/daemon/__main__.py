# SPDX-License-Identifier: GPL-2.0-or-later
"""``python -m basilisk_profiler.daemon [--config PATH] [--no-tray]``

Quit Synapse first: both programs would write the mouse.
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import time
from pathlib import Path

from ..core import config as cfg
from ..platform import foreground_watcher
from .service import Service

log = logging.getLogger('basilisk_profiler')


def run_headless(service: Service) -> None:
    stop = False

    def handle(*_):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle)
    signal.signal(signal.SIGTERM, handle)
    while not stop:
        service.tick()
        time.sleep(0.1)


def run_tray(service: Service) -> None:
    from PySide6.QtWidgets import QApplication

    from .tray import Tray

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    tray = Tray(app, service)  # noqa: F841 - must stay alive while the app runs
    signal.signal(signal.SIGINT, lambda *_: app.quit())
    app.exec()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog='basilisk-profiler-daemon', description=__doc__)
    parser.add_argument('--config', type=Path, default=cfg.config_path())
    parser.add_argument('--no-tray', action='store_true', help='run without the tray icon')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s')

    cfg.ensure_exists(args.config)
    service = Service(args.config)
    watcher = foreground_watcher(service.on_window)
    watcher.start()
    try:
        if args.no_tray:
            run_headless(service)
        else:
            try:
                run_tray(service)
            except ImportError:
                log.warning('PySide6 not installed; running without tray icon')
                run_headless(service)
    finally:
        watcher.stop()
        service.shutdown()
    return 0


if __name__ == '__main__':
    sys.exit(main())
