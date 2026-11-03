# SPDX-License-Identifier: GPL-2.0-or-later
"""The background service: active window -> rule -> profile -> live slot 0x01.

Single owner of the device. Thread model: watchers call ``on_window`` from their own
thread; everything else happens in ``tick()``, called periodically by the tray's Qt
timer or by the headless loop.
"""
from __future__ import annotations

import hashlib
import json
import logging
import queue
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from ..core import config as cfg
from ..core import protocol as p
from ..core.device import DeviceError, RazerDevice
from ..core.events import BatteryLevel, DeviceEvent, DpiChanged
from ..core.model import Config, Profile, WindowInfo, onboard_store

log = logging.getLogger(__name__)

# A window must stay in front this long before its profile is written (alt-tab flicker).
DEBOUNCE = 0.4
# Retry interval while the mouse / dock is absent.
REOPEN_INTERVAL = 5.0


@dataclass
class LiveStatus:
    """What the mouse is doing right now, for the tray and the settings window."""
    dpi: int | None = None
    stage: int | None = None  # 1-based
    stage_count: int | None = None
    battery: int | None = None  # percent


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
        self._device_events: queue.SimpleQueue[DeviceEvent] = queue.SimpleQueue()
        self.status = LiveStatus()
        self._status_stale = True  # re-read DPI and battery at the next chance
        # called with the new DPI when the user changes it with the DPI button
        self.on_dpi_changed: Callable[[LiveStatus], None] | None = None
        self._device: RazerDevice | None = None
        self._next_open = 0.0
        self._config_mtime: float | None = None
        self._pending: tuple[Profile | None, float] | None = None
        self.config: Config | None = None
        self.config_error: str | None = None
        self.window = WindowInfo()
        self.active: Profile | None = None  # last profile written to the device
        self.paused = False
        # onboard slot -> hash of what was last written there; persisted so a restart does
        # not rewrite the mouse's flash memory
        self.state_path = config_path.with_name('onboard-state.json')
        self._onboard_written: dict[str, str] = self._load_state()
        self._onboard_pending = False
        self._initial_store: int | None = None  # slot active when the device was first opened
        self.reload_config(force=True)

    # --- inputs ----------------------------------------------------------------

    def on_window(self, window: WindowInfo) -> None:
        """Thread-safe; called by the foreground watcher."""
        self._events.put(window)

    def on_device_event(self, event: DeviceEvent) -> None:
        """Thread-safe; called by the platform's event reader."""
        self._device_events.put(event)

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
        # onboard slots first: a window profile kept onboard is applied by selecting its slot
        if self._onboard_pending and not self.paused and self._sync_onboard():
            self._onboard_pending = False
        if self._pending and not self.paused:
            profile, due = self._pending
            if self._clock() >= due and self._apply(profile):
                self._pending = None
        self._update_status()

    def shutdown(self) -> None:
        """Give the mouse back as found: the slot that was active at start, normal mode."""
        if self._device is None:
            return
        try:
            initial = self._initial_store
            if initial is not None and self._device.active_profile() != initial:
                self._device.set_active_profile(initial)
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
        self._onboard_pending = True
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
                if self._initial_store is None:
                    self._initial_store = self._device.active_profile()
                    log.info('active slot at start: 0x%02x', self._initial_store)
            except (OSError, DeviceError) as e:
                log.debug('device not available: %s', e)
                self._next_open = self._clock() + REOPEN_INTERVAL
        return self._device

    def _write(self, profile: Profile, store: int) -> bool:
        device = self._device_or_none()
        if device is None:
            return False
        try:
            for report in profile.reports(store):
                device.transact(report)
        except (OSError, DeviceError) as e:
            log.warning('writing profile %r to store 0x%02x failed: %s', profile.name, store, e)
            device.close()
            self._device = None
            self._next_open = self._clock() + REOPEN_INTERVAL
            return False
        return True

    def _sync_onboard(self) -> bool:
        """Write changed onboard profiles to their slots; True when all are up to date."""
        if self.config is None:
            return True
        for slot, profile in sorted(self.config.onboard().items()):
            digest = _digest(profile, onboard_store(slot))
            if self._onboard_written.get(str(slot)) == digest:
                continue
            if not self._write(profile, onboard_store(slot)):
                return False
            log.info('profile %r written to onboard slot %d', profile.name, slot)
            self._onboard_written[str(slot)] = digest
            self._save_state()
        return True

    def _load_state(self) -> dict[str, str]:
        try:
            return json.loads(self.state_path.read_text())
        except (OSError, ValueError):
            return {}

    def _save_state(self) -> None:
        try:
            self.state_path.write_text(json.dumps(self._onboard_written, indent=2))
        except OSError as e:
            log.warning('could not save %s: %s', self.state_path, e)

    def _select(self, store: int) -> bool:
        """Make ``store`` the slot the mouse uses (it ignores all others)."""
        device = self._device_or_none()
        if device is None:
            return False
        try:
            if device.active_profile() != store:
                device.set_active_profile(store)
        except (OSError, DeviceError) as e:
            log.warning('selecting store 0x%02x failed: %s', store, e)
            device.close()
            self._device = None
            self._next_open = self._clock() + REOPEN_INTERVAL
            return False
        return True

    def _onboard_ready(self, profile: Profile) -> bool:
        slot = profile.onboard_slot
        if not slot:
            return False
        return self._onboard_written.get(str(slot)) == _digest(profile, onboard_store(slot))

    def _apply(self, profile: Profile) -> bool:
        """Onboard profiles are selected by slot; others are written to the live slot."""
        if self._onboard_ready(profile):
            if not self._select(onboard_store(profile.onboard_slot)):
                return False
        elif not (self._write(profile, p.STORE_LIVE) and self._select(p.STORE_LIVE)):
            return False
        log.info('profile %r applied (%s)', profile.name, self.window.process or '-')
        self.active = profile
        self._status_stale = True
        self._notify()
        return True

    def _update_status(self) -> None:
        """Track DPI / stage / battery from device events; the device is never polled.

        The status is read once when a profile is applied and once per DPI button event
        (for the stage index). Without an event reader (Windows for now) the DPI shown is
        the one from the last profile switch.
        """
        changed_by_user = False
        while True:
            try:
                event = self._device_events.get_nowait()
            except queue.Empty:
                break
            if isinstance(event, DpiChanged):
                changed_by_user = True
                self.status.dpi = event.x
                self._status_stale = True  # read the stage index for it
            elif isinstance(event, BatteryLevel):
                if event.percent != self.status.battery:
                    self.status.battery = event.percent
                    self._notify()
        if self._status_stale and self._device is not None:
            self._status_stale = False  # one attempt; a sleeping mouse just keeps old values
            self._read_dpi()
            if self.status.battery is None:
                try:
                    self.status.battery = self._device.battery_percent()
                except (OSError, DeviceError, p.ProtocolError) as e:
                    log.debug('battery read failed: %s', e)
            self._notify()
        if changed_by_user and self.on_dpi_changed:
            self.on_dpi_changed(self.status)

    def _read_dpi(self) -> bool:
        """Read the active slot's stage table; errors leave the device open (mouse asleep)."""
        try:
            store = self._device.active_profile()
            stages = self._device.dpi_stages(store)
        except (OSError, DeviceError, p.ProtocolError) as e:
            log.debug('DPI read failed: %s', e)
            return False
        self.status.stage = stages.active
        self.status.stage_count = len(stages.stages)
        self.status.dpi = stages.stages[stages.active - 1].x
        return True

    def _notify(self) -> None:
        if self._on_change:
            self._on_change(self)


def _digest(profile: Profile, store: int) -> str:
    """Identifies exactly what writing ``profile`` to ``store`` sends to the device."""
    return hashlib.sha1(b''.join(r.to_bytes() for r in profile.reports(store))).hexdigest()
