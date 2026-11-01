# SPDX-License-Identifier: GPL-2.0-or-later
"""The background service: active window -> rule -> profile -> live slot 0x01.

Single owner of the device. Thread model: watchers call ``on_window`` from their own
thread; everything else happens in ``tick()``, called periodically by the tray's Qt
timer or by the headless loop.
"""
from __future__ import annotations

import logging
import queue
import time
from collections.abc import Callable
from pathlib import Path

from ..core import config as cfg
from ..core import protocol as p
from ..core.device import DeviceError, RazerDevice
from ..core.model import Config, Profile, WindowInfo

log = logging.getLogger(__name__)

# A window must stay in front this long before its profile is written (alt-tab flicker).
DEBOUNCE = 0.4
# Retry interval while the mouse / dock is absent.
REOPEN_INTERVAL = 5.0


class Service:
    def __init__(self, config_path: Path, *,
                 open_device: Callable[[], RazerDevice] = RazerDevice.open,
                 clock: Callable[[], float] = time.monotonic,
                 on_change: Callable[[Service], None] | None = None):
        self.config_path = config_path
        self._open_device = open_device
        self._clock = clock
        self._on_change = on_change
        self._events: queue.SimpleQueue[WindowInfo] = queue.SimpleQueue()
        self._device: RazerDevice | None = None
        self._next_open = 0.0
        self._config_mtime: float | None = None
        self._pending: tuple[Profile | None, float] | None = None
        self.config: Config | None = None
        self.config_error: str | None = None
        self.window = WindowInfo()
        self.active: Profile | None = None  # last profile written to the device
        self.paused = False
        self.reload_config(force=True)

    # --- inputs ----------------------------------------------------------------

    def on_window(self, window: WindowInfo) -> None:
        """Thread-safe; called by the foreground watcher."""
        self._events.put(window)

    def set_paused(self, paused: bool) -> None:
        self.paused = paused
        if not paused:
            self._schedule(self._wanted(), now=True)
        self._notify()

    # --- main loop step ----------------------------------------------------------

    def tick(self) -> None:
        self.reload_config()
        while True:
            try:
                self.window = self._events.get_nowait()
            except queue.Empty:
                break
            self._schedule(self._wanted())
        if self._pending and not self.paused:
            profile, due = self._pending
            if self._clock() >= due and self._apply(profile):
                self._pending = None

    def shutdown(self) -> None:
        """Leave the mouse in normal mode so its profile button cycles onboard slots."""
        if self._device is None:
            return
        try:
            if self._device.device_mode() != p.DeviceMode.NORMAL:
                self._device.set_device_mode(p.DeviceMode.NORMAL)
        except (OSError, DeviceError) as e:
            log.warning('could not restore normal mode: %s', e)
        finally:
            self._device.close()
            self._device = None

    # --- internals ---------------------------------------------------------------

    def reload_config(self, force: bool = False) -> bool:
        try:
            mtime = self.config_path.stat().st_mtime
        except OSError:
            mtime = None
        if not force and mtime == self._config_mtime:
            return False
        self._config_mtime = mtime
        try:
            self.config = cfg.load(self.config_path)
            self.config_error = None
            log.info('config loaded: %s', self.config_path)
        except (OSError, cfg.ConfigError) as e:
            # keep running with the previous config
            self.config_error = str(e)
            log.error('config not loaded: %s', e)
            self._notify()
            return False
        self.active = None  # a reloaded profile may have new contents: write it again
        self._schedule(self._wanted(), now=True)
        self._notify()
        return True

    def _wanted(self) -> Profile | None:
        return self.config.profile_for(self.window) if self.config else None

    def _schedule(self, profile: Profile | None, now: bool = False) -> None:
        if profile is None or profile == self.active:
            self._pending = None  # nothing to do, or a quick switch back
            return
        self._pending = (profile, self._clock() + (0 if now else DEBOUNCE))

    def _device_or_none(self) -> RazerDevice | None:
        if self._device is None and self._clock() >= self._next_open:
            try:
                self._device = self._open_device()
                log.info('device opened')
            except (OSError, DeviceError) as e:
                log.debug('device not available: %s', e)
                self._next_open = self._clock() + REOPEN_INTERVAL
        return self._device

    def _apply(self, profile: Profile) -> bool:
        device = self._device_or_none()
        if device is None:
            return False
        try:
            for report in profile.reports():
                device.transact(report)
        except (OSError, DeviceError) as e:
            log.warning('writing profile %r failed: %s', profile.name, e)
            device.close()
            self._device = None
            self._next_open = self._clock() + REOPEN_INTERVAL
            return False
        log.info('profile %r applied (%s)', profile.name, self.window.process or '-')
        self.active = profile
        self._notify()
        return True

    def _notify(self) -> None:
        if self._on_change:
            self._on_change(self)
