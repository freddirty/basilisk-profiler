# SPDX-License-Identifier: GPL-2.0-or-later
"""Entry point of the frozen Linux build.

``basilisk-profiler``            tray service (settings window via the tray)
``basilisk-profiler cli ARGS``   the command-line tool (info, backup, restore, ...)
"""
import sys

if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'cli':
        from basilisk_profiler.cli import main as cli_main
        sys.exit(cli_main(sys.argv[2:]))
    from basilisk_profiler.daemon.__main__ import main
    sys.exit(main())
