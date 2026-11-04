# SPDX-License-Identifier: GPL-2.0-or-later
import pytest

from basilisk_profiler import i18n


@pytest.fixture(autouse=True)
def hungarian_ui():
    """The interface tests check the Hungarian texts; test_i18n.py covers English."""
    i18n.set_language('hu')
    yield
    i18n.set_language('hu')
