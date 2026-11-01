# SPDX-License-Identifier: GPL-2.0-or-later
"""Active-window watcher for X11 (Linux Mint Cinnamon): follows _NET_ACTIVE_WINDOW."""
from __future__ import annotations

import threading
from collections.abc import Callable
from pathlib import Path

from ...core.model import WindowInfo, normalize_process


class ForegroundWatcher:
    def __init__(self, callback: Callable[[WindowInfo], None]):
        from Xlib import X, display  # python-xlib, Linux only

        self._X = X
        self._callback = callback
        self._display = display.Display()
        self._root = self._display.screen().root
        self._atoms = {name: self._display.intern_atom(name) for name in
                       ('_NET_ACTIVE_WINDOW', '_NET_WM_PID', '_NET_WM_NAME', 'UTF8_STRING')}
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._root.change_attributes(event_mask=self._X.PropertyChangeMask)
        self._thread = threading.Thread(target=self._run, name='x11-watcher', daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(2)

    def _active_window(self):
        prop = self._root.get_full_property(self._atoms['_NET_ACTIVE_WINDOW'],
                                            self._X.AnyPropertyType)
        if not prop or not prop.value or not prop.value[0]:
            return None
        return self._display.create_resource_object('window', prop.value[0])

    def window_info(self, window) -> WindowInfo:
        wm_class = ''
        title = ''
        process = ''
        try:
            cls = window.get_wm_class()
            wm_class = cls[1] if cls else ''
            name = window.get_full_property(self._atoms['_NET_WM_NAME'],
                                            self._atoms['UTF8_STRING'])
            title = name.value.decode('utf-8', 'replace') if name else (window.get_wm_name() or '')
            pid = window.get_full_property(self._atoms['_NET_WM_PID'], self._X.AnyPropertyType)
            if pid and pid.value:
                comm = Path(f'/proc/{pid.value[0]}/comm')
                process = normalize_process(comm.read_text().strip()) if comm.exists() else ''
        except Exception:  # noqa: BLE001 - windows may vanish while being inspected
            pass
        return WindowInfo(process=process, wm_class=wm_class, title=title)

    def _emit(self) -> None:
        window = self._active_window()
        if window is not None:
            self._callback(self.window_info(window))

    def _run(self) -> None:
        self._emit()
        active = self._atoms['_NET_ACTIVE_WINDOW']
        while not self._stop.is_set():
            # poll so stop() is honoured; pending_events avoids blocking in next_event
            if not self._display.pending_events():
                self._stop.wait(0.1)
                continue
            event = self._display.next_event()
            if event.type == self._X.PropertyNotify and event.atom == active:
                self._emit()
