# SPDX-License-Identifier: GPL-2.0-or-later
"""Entry point of the frozen Windows build: the tray service (settings window via the tray)."""
import sys

from basilisk_profiler.daemon.__main__ import main

if __name__ == '__main__':
    sys.exit(main())
