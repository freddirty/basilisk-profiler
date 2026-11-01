# SPDX-License-Identifier: GPL-2.0-or-later
"""Foreground-window watcher: SetWinEventHook(EVENT_SYSTEM_FOREGROUND) via ctypes.

The hook is out-of-context, so it needs a message loop on the thread that installed it;
the watcher runs its own thread for that.
"""
from __future__ import annotations

import ctypes
import threading
from collections.abc import Callable
from ctypes import wintypes

from ...core.model import WindowInfo, normalize_process

_user32 = ctypes.WinDLL('user32', use_last_error=True)
_k32 = ctypes.WinDLL('kernel32', use_last_error=True)

_EVENT_SYSTEM_FOREGROUND = 0x0003
_WINEVENT_OUTOFCONTEXT = 0x0000
_WINEVENT_SKIPOWNPROCESS = 0x0002
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_WM_QUIT = 0x0012

_WinEventProc = ctypes.WINFUNCTYPE(None, wintypes.HANDLE, wintypes.DWORD, wintypes.HWND,
                                   wintypes.LONG, wintypes.LONG, wintypes.DWORD, wintypes.DWORD)
_user32.SetWinEventHook.restype = wintypes.HANDLE
_user32.SetWinEventHook.argtypes = [wintypes.UINT, wintypes.UINT, wintypes.HMODULE,
                                    _WinEventProc, wintypes.DWORD, wintypes.DWORD, wintypes.UINT]
_user32.UnhookWinEvent.argtypes = [wintypes.HANDLE]
_user32.GetForegroundWindow.restype = wintypes.HWND
_user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
_user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
_user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT,
                                wintypes.UINT]
_user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM,
                                       wintypes.LPARAM]
_k32.OpenProcess.restype = wintypes.HANDLE
_k32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_k32.QueryFullProcessImageNameW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR,
                                            ctypes.POINTER(wintypes.DWORD)]
_k32.CloseHandle.argtypes = [wintypes.HANDLE]


def _process_name(hwnd) -> str:
    pid = wintypes.DWORD()
    _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    handle = _k32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return ''
    try:
        size = wintypes.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if not _k32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return ''
        return normalize_process(buf.value)
    finally:
        _k32.CloseHandle(handle)


def window_info(hwnd) -> WindowInfo:
    title = ctypes.create_unicode_buffer(512)
    _user32.GetWindowTextW(hwnd, title, 512)
    cls = ctypes.create_unicode_buffer(256)
    _user32.GetClassNameW(hwnd, cls, 256)
    return WindowInfo(process=_process_name(hwnd), wm_class=cls.value, title=title.value)


_EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
_user32.EnumWindows.argtypes = [_EnumWindowsProc, wintypes.LPARAM]
_user32.IsWindowVisible.argtypes = [wintypes.HWND]
_user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]


def list_windows() -> list[WindowInfo]:
    """Visible top-level windows with a title, for the rule editor's picker."""
    found: list[WindowInfo] = []

    @_EnumWindowsProc
    def collect(hwnd, _):
        if _user32.IsWindowVisible(hwnd) and _user32.GetWindowTextLengthW(hwnd) > 0:
            found.append(window_info(hwnd))
        return True

    _user32.EnumWindows(collect, 0)
    return found


class ForegroundWatcher:
    def __init__(self, callback: Callable[[WindowInfo], None]):
        self._callback = callback
        self._thread: threading.Thread | None = None
        self._thread_id = 0
        self._ready = threading.Event()

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name='foreground-watcher', daemon=True)
        self._thread.start()
        self._ready.wait(5)

    def stop(self) -> None:
        if self._thread_id:
            _user32.PostThreadMessageW(self._thread_id, _WM_QUIT, 0, 0)
        if self._thread:
            self._thread.join(2)

    def _emit(self, hwnd) -> None:
        if hwnd:
            try:
                self._callback(window_info(hwnd))
            except Exception:  # noqa: BLE001 - never let a callback kill the hook thread
                pass

    def _run(self) -> None:
        self._thread_id = _k32.GetCurrentThreadId()

        @_WinEventProc
        def on_event(hook, event, hwnd, id_object, id_child, thread, time_ms):
            if id_object == 0:  # OBJID_WINDOW
                self._emit(hwnd)

        hook = _user32.SetWinEventHook(_EVENT_SYSTEM_FOREGROUND, _EVENT_SYSTEM_FOREGROUND,
                                       None, on_event, 0, 0,
                                       _WINEVENT_OUTOFCONTEXT | _WINEVENT_SKIPOWNPROCESS)
        self._ready.set()
        self._emit(_user32.GetForegroundWindow())
        msg = wintypes.MSG()
        try:
            while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                pass
        finally:
            if hook:
                _user32.UnhookWinEvent(hook)
