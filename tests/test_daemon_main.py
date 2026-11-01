# SPDX-License-Identifier: GPL-2.0-or-later
import sys

import pytest

from basilisk_profiler.daemon.__main__ import single_instance


def test_single_instance_lock(tmp_path):
    first = single_instance(tmp_path / 'daemon.lock')
    assert first is not None
    if sys.platform == 'win32':  # flock is per process on Linux; msvcrt locks per handle
        assert single_instance(tmp_path / 'daemon.lock') is None
    first.close()
    again = single_instance(tmp_path / 'daemon.lock')
    assert again is not None
    again.close()


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows registry')
def test_autostart_command_points_at_pythonw():
    from basilisk_profiler.platform.win import autostart

    assert autostart.command().endswith('-m basilisk_profiler.daemon')
    assert 'pythonw' in autostart.command().lower()
