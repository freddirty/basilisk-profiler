# SPDX-License-Identifier: GPL-2.0-or-later
import sys

import pytest

from basilisk_profiler.platform.linux.conflicts import warnings

# sysfs names contain ':', which Windows does not allow in file names
linux_only = pytest.mark.skipif(sys.platform == 'win32', reason='sysfs-style paths')


def test_no_conflicts_on_clean_system(tmp_path):
    (tmp_path / 'sys').mkdir()
    (tmp_path / 'proc' / '42').mkdir(parents=True)
    (tmp_path / 'proc' / '42' / 'comm').write_text('bash\n')
    assert warnings(tmp_path / 'sys', tmp_path / 'proc') == []


@linux_only
def test_openrazer_driver_bound_to_dock(tmp_path):
    driver = tmp_path / 'sys' / 'bus' / 'hid' / 'drivers' / 'razermouse'
    (driver / '0003:1532:00A4.0007').mkdir(parents=True)
    (driver / 'bind').touch()
    (tmp_path / 'proc').mkdir()
    found = warnings(tmp_path / 'sys', tmp_path / 'proc')
    assert len(found) == 1 and 'razermouse' in found[0]


@linux_only
def test_openrazer_driver_for_other_device_is_ignored(tmp_path):
    driver = tmp_path / 'sys' / 'bus' / 'hid' / 'drivers' / 'razermouse'
    (driver / '0003:1532:0084.0001').mkdir(parents=True)
    (tmp_path / 'proc').mkdir()
    assert warnings(tmp_path / 'sys', tmp_path / 'proc') == []


def test_openrazer_daemon_running(tmp_path):
    (tmp_path / 'sys').mkdir()
    (tmp_path / 'proc' / '1234').mkdir(parents=True)
    (tmp_path / 'proc' / '1234' / 'comm').write_text('openrazer-daemo\n')
    found = warnings(tmp_path / 'sys', tmp_path / 'proc')
    assert len(found) == 1 and 'openrazer-daemon' in found[0]


@pytest.mark.skipif(not sys.platform.startswith('linux'), reason='Linux HID backend')
def test_linux_uses_kernel_hidraw_not_libusb():
    from basilisk_profiler.platform import hid_backend

    assert hid_backend().__name__ == 'hidraw'


def test_autostart_desktop_entry(tmp_path, monkeypatch):
    from basilisk_profiler.platform.linux import autostart

    monkeypatch.setenv('XDG_CONFIG_HOME', str(tmp_path))
    assert not autostart.is_enabled()
    autostart.set_enabled(True)
    path = tmp_path / 'autostart' / 'basilisk-profiler.desktop'
    assert autostart.is_enabled() and path.is_file()
    text = path.read_text()
    assert text.startswith('[Desktop Entry]\n')
    assert 'Exec=' in text and '-m basilisk_profiler.daemon' in text
    autostart.set_enabled(False)
    assert not path.exists()
    autostart.set_enabled(False)  # already off: no error


class FakeProp:
    def __init__(self, value):
        self.value = value


class FakeWindow:
    def __init__(self, wm_class, title, pid=None):
        self._wm_class, self._title, self._pid = wm_class, title, pid

    def get_wm_class(self):
        return self._wm_class

    def get_wm_name(self):
        return self._title

    def get_full_property(self, atom, _type):
        if atom == 'name':
            return FakeProp(self._title.encode())
        if atom == 'pid' and self._pid:
            return FakeProp([self._pid])
        return None


ATOMS = {'_NET_WM_NAME': 'name', 'UTF8_STRING': 'utf8', '_NET_WM_PID': 'pid'}


@linux_only
def test_window_info_reads_process_from_proc():
    import os

    from basilisk_profiler.platform.linux.x11 import window_info

    info = window_info(FakeWindow(('xed', 'Xed'), 'Doc 1', os.getpid()), ATOMS, 0)
    assert info.wm_class == 'Xed' and info.title == 'Doc 1'
    assert info.process == open(f'/proc/{os.getpid()}/comm').read().strip().lower()


def test_window_info_falls_back_to_class_for_sandboxed_apps():
    pytest.importorskip('Xlib')
    from basilisk_profiler.platform.linux.x11 import window_info

    info = window_info(FakeWindow(('missioncenter', 'MissionCenter'), 'Mission Center'), ATOMS, 0)
    assert info.process == 'missioncenter'
