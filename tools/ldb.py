# SPDX-License-Identifier: GPL-2.0-or-later
r"""Dump every key/value of a LevelDB table file (.ldb), e.g. Synapse 4's IndexedDB.

Copy the database out of %LOCALAPPDATA%\Razer\RazerAppEngine\User Data\Default\IndexedDB
first; Synapse keeps it locked while it runs.

    python tools/ldb.py 000622.ldb dump.bin
"""
import sys

from basilisk_profiler.core.leveldb import table_entries


def main():
    data = open(sys.argv[1], 'rb').read()
    out = bytearray()
    for key, value in table_entries(data):
        out += b'\n#KEY ' + key + b'\n' + value
    open(sys.argv[2], 'wb').write(out)
    print(len(out))


if __name__ == '__main__':
    main()
