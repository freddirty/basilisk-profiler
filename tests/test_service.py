# SPDX-License-Identifier: GPL-2.0-or-later
import os

import pytest

from basilisk_profiler.core import config as cfg
from basilisk_profiler.core import protocol as p
from basilisk_profiler.core.device import DeviceError
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

    def transact(self, report):
        if self.fail:
            raise DeviceError('gone')
        self.reports.append(report)
        return report

    def device_mode(self):
        return self.mode

    def set_device_mode(self, mode):
        self.mode = mode

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
    assert [r.command for r in device.reports] == [(4, 6), (2, 0x0C), (2, 0x0C)]


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
    assert len(device.reports) == 2


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
    assert len(device.reports) == 2  # written once for firefox, chrome uses the same profile


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
