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


def single_instance(path: Path):
    """Exclusive lock on ``path``; None if another daemon holds it. Released on exit."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(path, 'a+')  # noqa: SIM115 - kept open for the process lifetime
    try:
        if sys.platform == 'win32':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        handle.close()
        return None
    return handle


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
    log_options = {}
    if sys.stderr is None:  # pythonw / frozen windowed build: no console
        args.config.parent.mkdir(parents=True, exist_ok=True)
        log_options['filename'] = args.config.parent / 'basilisk-profiler.log'
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format='%(asctime)s %(levelname)s %(message)s', **log_options)

    lock = single_instance(args.config.parent / 'daemon.lock')
    if lock is None:
        log.warning('another instance is already running')
        return 1
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
