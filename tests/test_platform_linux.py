# SPDX-License-Identifier: GPL-2.0-or-later
import sys

import pytest

from basilisk_profiler.platform.linux.conflicts import warnings


def test_no_conflicts_on_clean_system(tmp_path):
    (tmp_path / 'sys').mkdir()
    (tmp_path / 'proc' / '42').mkdir(parents=True)
    (tmp_path / 'proc' / '42' / 'comm').write_text('bash\n')
    assert warnings(tmp_path / 'sys', tmp_path / 'proc') == []


def test_openrazer_driver_bound_to_dock(tmp_path):
    driver = tmp_path / 'sys' / 'bus' / 'hid' / 'drivers' / 'razermouse'
    (driver / '0003:1532:00A4.0007').mkdir(parents=True)
    (driver / 'bind').touch()
    (tmp_path / 'proc').mkdir()
    found = warnings(tmp_path / 'sys', tmp_path / 'proc')
    assert len(found) == 1 and 'razermouse' in found[0]


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
