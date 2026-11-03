# SPDX-License-Identifier: GPL-2.0-or-later
import os

import pytest

from basilisk_profiler.core import config as cfg
from basilisk_profiler.core import protocol as p
from basilisk_profiler.core.device import DeviceError
from basilisk_profiler.core.events import BatteryLevel, DpiChanged
from basilisk_profiler.core.model import WindowInfo
from basilisk_profiler.daemon import service as svc


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class FakeDevice:
    def __init__(self, fail=False):
        self.reports = []
        self.mode = p.DeviceMode.DRIVER
        self.fail = fail
        self.closed = False
        self.active_store = 0x03  # an onboard slot was active when the service started
        self.selected = []

    def transact(self, report):
        if self.fail:
            raise DeviceError('gone')
        self.reports.append(report)
        return report

    def device_mode(self):
        return self.mode

    def set_device_mode(self, mode):
        self.mode = mode

    def active_profile(self):
        if self.fail:
            raise DeviceError('gone')
        return self.active_store

    def set_active_profile(self, store):
        self.active_store = store
        self.selected.append(store)

    stage_table = (400, 800, 1600, 3200, 6400)
    dpi_active = 3

    def dpi_stages(self, store=p.STORE_LIVE):
        if self.fail:
            raise DeviceError('gone')
        return p.DpiStages(tuple(p.DpiStage(v, v) for v in self.stage_table),
                           active=self.dpi_active, store=store)

    def battery_percent(self):
        if self.fail:
            raise DeviceError('gone')
        return 80

    dock = p.BATTERY_EFFECT
    dock_now = None

    def dock_effect(self, store=p.DOCK_STORE):
        return self.dock

    def set_dock_effect(self, effect, store=p.DOCK_STORE):
        if store == p.DOCK_STORE:
            self.dock = effect
        else:
            self.dock_now = effect

    def close(self):
        self.closed = True

    def written(self):
        return [p.parse_button_mapping(r).action for r in self.reports if r.command == (2, 0x0C)]


@pytest.fixture
def env(tmp_path):
    path = tmp_path / 'config.toml'
    path.write_text(cfg.EXAMPLE)
    clock = Clock()
    device = FakeDevice()
    opened = []

    def open_device():
        opened.append(1)
        if device.fail:
            raise DeviceError('absent')
        return device

    service = svc.Service(path, open_device=open_device, clock=clock)
    return service, clock, device, path, opened


def test_default_profile_applied_at_start(env):
    service, clock, device, *_ = env
    service.tick()
    assert service.active.name == 'general'
    expected = service.config.profiles['general'].reports()
    assert [r.command for r in device.reports] == [r.command for r in expected]


def test_window_switch_is_debounced(env):
    service, clock, device, *_ = env
    service.tick()
    device.reports.clear()
    service.on_window(WindowInfo(process='firefox'))
    service.tick()
    assert device.reports == []  # still inside the debounce window
    clock.now += svc.DEBOUNCE
    service.tick()
    assert service.active.name == 'browser'
    assert len(device.reports) == len(service.config.profiles['browser'].reports())


def test_quick_switch_back_writes_nothing(env):
    service, clock, device, *_ = env
    service.tick()
    device.reports.clear()
    service.on_window(WindowInfo(process='firefox'))
    service.tick()
    clock.now += 0.1
    service.on_window(WindowInfo(process='code'))
    service.tick()
    clock.now += svc.DEBOUNCE
    service.tick()
    assert device.reports == []
    assert service.active.name == 'general'


def test_same_profile_not_rewritten(env):
    service, clock, device, *_ = env
    service.tick()
    device.reports.clear()
    for process in ('firefox', 'chrome', 'firefox'):
        service.on_window(WindowInfo(process=process))
        service.tick()
        clock.now += svc.DEBOUNCE
        service.tick()
    # written once for firefox; chrome and brave use the same profile
    assert len(device.reports) == len(service.config.profiles['browser'].reports())


def test_pause_holds_writes(env):
    service, clock, device, *_ = env
    service.tick()
    device.reports.clear()
    service.set_paused(True)
    service.on_window(WindowInfo(process='firefox'))
    clock.now += svc.DEBOUNCE
    service.tick()
    assert device.reports == []
    service.set_paused(False)
    service.tick()
    assert service.active.name == 'browser'


def test_config_hot_reload(env):
    service, clock, device, path, _ = env
    service.tick()
    device.reports.clear()
    path.write_text(cfg.EXAMPLE.replace('button5 = "mouse:5"', 'button5 = "key:8"'))
    os.utime(path, (clock.now, os.path.getmtime(path) + 5))
    service.tick()
    assert service.active.name == 'general'
    assert p.KeyAction(0x25) in device.written()


def test_broken_config_keeps_previous(env):
    service, clock, device, path, _ = env
    service.tick()
    path.write_text('[[profile]\n')
    os.utime(path, (clock.now, os.path.getmtime(path) + 5))
    service.tick()
    assert service.config_error
    assert service.config is not None and 'browser' in service.config.profiles


def test_device_absent_is_retried(env):
    service, clock, device, path, opened = env
    device.fail = True
    service.tick()
    service.tick()
    assert len(opened) == 1  # waits REOPEN_INTERVAL before trying again
    device.fail = False
    clock.now += svc.REOPEN_INTERVAL
    service.tick()
    assert service.active.name == 'general'


def test_write_error_drops_device_and_retries(env):
    service, clock, device, path, opened = env
    service.tick()
    device.reports.clear()
    device.fail = True
    service.on_window(WindowInfo(process='firefox'))
    service.tick()
    clock.now += svc.DEBOUNCE
    service.tick()
    assert device.closed and service.active.name == 'general'
    device.fail = False
    clock.now += svc.REOPEN_INTERVAL
    service.tick()
    assert service.active.name == 'browser'


def test_shutdown_restores_normal_mode(env):
    service, clock, device, *_ = env
    service.tick()
    service.shutdown()
    assert device.mode == p.DeviceMode.NORMAL and device.closed


def with_onboard(path, slots):
    """Example config with onboard slots: {'general': 1, 'browser': 4}."""
    text = cfg.EXAMPLE
    for name, slot in slots.items():
        text = text.replace(f'name = "{name}"\n', f'name = "{name}"\nonboard_slot = {slot}\n')
    path.write_text(text)


def stores_written(device):
    return sorted({r.args[0] for r in device.reports})


def test_onboard_profiles_written_once(env):
    service, clock, device, path, _ = env
    with_onboard(path, {'general': 1, 'browser': 4})
    os.utime(path, (clock.now, os.path.getmtime(path) + 5))
    service.tick()
    # general lives in slot 1 (store 0x02): it is selected there, not written to 0x01
    assert stores_written(device) == [0x02, 0x05]
    assert device.active_store == 0x02
    assert service.state_path.exists()
    device.reports.clear()
    path.write_text(path.read_text() + '\n# touched\n')
    os.utime(path, (clock.now, os.path.getmtime(path) + 10))
    service.tick()
    assert 0x02 not in stores_written(device) and 0x05 not in stores_written(device)


def test_onboard_state_survives_restart(env, tmp_path):
    service, clock, device, path, _ = env
    with_onboard(path, {'browser': 2})
    os.utime(path, (clock.now, os.path.getmtime(path) + 5))
    service.tick()
    device.reports.clear()
    again = svc.Service(path, open_device=lambda: device, clock=clock)
    again.tick()
    assert 0x03 not in stores_written(device)


def test_changed_onboard_profile_is_rewritten(env):
    service, clock, device, path, _ = env
    with_onboard(path, {'browser': 3})
    os.utime(path, (clock.now, os.path.getmtime(path) + 5))
    service.tick()
    device.reports.clear()
    path.write_text(path.read_text().replace('button5 = "ctrl+t"', 'button5 = "ctrl+n"'))
    os.utime(path, (clock.now, os.path.getmtime(path) + 10))
    service.tick()
    assert 0x04 in stores_written(device)


def test_onboard_sync_retries_when_device_absent(env):
    service, clock, device, path, opened = env
    device.fail = True
    with_onboard(path, {'general': 1})
    os.utime(path, (clock.now, os.path.getmtime(path) + 5))
    service.tick()
    device.fail = False
    clock.now += svc.REOPEN_INTERVAL
    service.tick()
    assert 0x02 in stores_written(device)


def test_duplicate_onboard_slot_rejected(tmp_path):
    path = tmp_path / 'c.toml'
    with_onboard(path, {'general': 2, 'browser': 2})
    with pytest.raises(cfg.ConfigError):
        cfg.load(path)


def test_live_profile_selects_live_slot(env):
    service, clock, device, *_ = env
    service.tick()
    assert device.active_store == p.STORE_LIVE  # was 0x03 at start; general is not onboard


def test_profile_button_choice_kept_until_next_window_change(env):
    service, clock, device, *_ = env
    service.tick()
    device.active_store = 0x04  # user pressed the profile button
    service.tick()
    assert device.active_store == 0x04
    service.on_window(WindowInfo(process='firefox'))
    service.tick()
    clock.now += svc.DEBOUNCE
    service.tick()
    assert device.active_store == p.STORE_LIVE


def test_onboard_window_profile_selected_without_rewrite(env):
    service, clock, device, path, _ = env
    with_onboard(path, {'browser': 4})
    os.utime(path, (clock.now, os.path.getmtime(path) + 5))
    service.tick()
    device.reports.clear()
    service.on_window(WindowInfo(process='brave'))
    service.tick()
    clock.now += svc.DEBOUNCE
    service.tick()
    assert device.reports == [] and device.active_store == 0x05


def test_shutdown_restores_initial_slot(env):
    service, clock, device, *_ = env
    service.tick()
    assert device.active_store == p.STORE_LIVE
    service.shutdown()
    assert device.active_store == 0x03


def test_live_status_read_after_profile_applied(env):
    service, clock, device, *_ = env
    service.tick()
    assert service.status.dpi == 1600
    assert (service.status.stage, service.status.stage_count) == (3, 5)
    assert service.status.battery == 80


def test_dpi_button_event_updates_status_and_notifies(env):
    service, clock, device, *_ = env
    seen = []
    service.on_dpi_changed = lambda status: seen.append((status.dpi, status.stage))
    service.tick()
    assert seen == []  # reading the status at start is not a user change
    device.dpi_active = 4
    service.on_device_event(DpiChanged(3200, 3200))
    service.tick()
    assert seen == [(3200, 4)]
    assert service.status.dpi == 3200


def test_no_polling_without_events(env):
    service, clock, device, *_ = env
    seen = []
    service.on_dpi_changed = lambda status: seen.append(status.dpi)
    service.tick()
    device.dpi_active = 1
    for _ in range(50):
        clock.now += 1
        service.tick()
    assert seen == [] and service.status.dpi == 1600  # nothing asked the device


def test_sleeping_mouse_keeps_device_open(env):
    service, clock, device, *_ = env
    service.tick()
    device.fail = True
    service.on_device_event(DpiChanged(3200, 3200))
    service.tick()
    assert not device.closed
    assert service.status.dpi == 3200  # from the event; the stage read failed


def test_battery_event(env):
    service, clock, device, *_ = env
    service.tick()
    service.on_device_event(BatteryLevel(55))
    service.tick()
    assert service.status.battery == 55


def test_dock_state_read_once_and_not_written(env):
    service, clock, device, *_ = env
    service.tick()
    service.tick()
    assert service.dock_battery is True
    assert device.dock == p.BATTERY_EFFECT


def test_dock_battery_off_restores_previous_effect(env):
    service, clock, device, *_ = env
    blue = p.static_effect(0, 0, 0xFF)
    device.dock = blue
    service.tick()
    assert service.dock_battery is False
    service.set_dock_battery(True)
    service.tick()
    assert device.dock == p.BATTERY_EFFECT and service.dock_battery is True
    assert device.dock_now == p.static_effect(*p.battery_color(80))  # shown right away
    service.set_dock_battery(False)
    service.tick()
    assert device.dock == blue and device.dock_now == blue
    assert service.dock_battery is False


def test_dock_battery_off_without_previous_is_white(env):
    service, clock, device, *_ = env
    service.tick()
    service.set_dock_battery(False)
    service.tick()
    assert device.dock == p.static_effect(0xFF, 0xFF, 0xFF)


def test_dock_choice_reapplied_after_reconnect(env):
    service, clock, device, *_ = env
    service.set_dock_battery(True)
    service.tick()
    device.dock = p.static_effect(1, 2, 3)  # e.g. changed by another program
    service._device = None  # unplugged
    service.tick()
    clock.now += svc.REOPEN_INTERVAL
    service.reload_config(force=True)  # anything that reopens the device
    service.tick()
    assert device.dock == p.BATTERY_EFFECT
