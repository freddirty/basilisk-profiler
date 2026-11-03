# SPDX-License-Identifier: GPL-2.0-or-later
"""Reads the dock's event interface (hidraw, interface 1) on a background thread.

The kernel hands every hidraw reader its own copy of the input reports, so this does not
take anything away from the desktop's mouse / keyboard input.
"""
from __future__ import annotations

import logging
import os
import select
import threading
from collections.abc import Callable

from ... import RAZER_VID
from ...core.device import SUPPORTED_PIDS
from ...core.events import EVENT_INTERFACE, DeviceEvent, parse_event

log = logging.getLogger(__name__)
RETRY_INTERVAL = 5.0


def event_paths() -> list[bytes]:
    import hidraw

    found = []
    for d in hidraw.enumerate(RAZER_VID, 0):
        if (d['product_id'] in SUPPORTED_PIDS and d['interface_number'] == EVENT_INTERFACE
                and d['path'] not in found):
            found.append(d['path'])
    return found


class EventReader:
    def __init__(self, callback: Callable[[DeviceEvent], None]):
        self._callback = callback
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name='hidraw-events', daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()  # the daemon thread notices within one select timeout

    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                paths = event_paths()
            except Exception as e:  # noqa: BLE001 - enumeration must never kill the thread
                log.debug('event interface enumeration failed: %s', e)
                paths = []
            if not paths:
                self._stop.wait(RETRY_INTERVAL)
                continue
            try:
                fd = os.open(paths[0], os.O_RDONLY | os.O_NONBLOCK)
            except OSError as e:
                log.debug('cannot open %r: %s', paths[0], e)
                self._stop.wait(RETRY_INTERVAL)
                continue
            log.info('listening for device events on %s', paths[0].decode())
            try:
                self._read(fd)
            finally:
                os.close(fd)

    def _read(self, fd: int) -> None:
        while not self._stop.is_set():
            ready, _, _ = select.select([fd], [], [], 5.0)  # blocks; wakes only for events
            if not ready:
                continue
            try:
                data = os.read(fd, 64)
            except BlockingIOError:
                continue
            except OSError as e:  # dock unplugged
                log.info('event interface closed: %s', e)
                return
            event = parse_event(data)
            if event is not None:
                self._callback(event)
