# SPDX-License-Identifier: GPL-2.0-or-later
"""List Razer 90-byte feature-report commands from a tshark field dump on stdin.

Input columns: frame.time_epoch, usb.bmRequestType, usb.setup.bRequest,
usb.irp_info.direction, usb.data_fragment (or usb.control.Response).
Arguments are class+id pairs to hide, e.g. ``0f03`` for Chroma frame updates.
"""
import datetime
import sys

# PowerShell pipes may prepend a BOM, sometimes mis-decoded as cp1252
BOM_CHARS = ''.join(map(chr, (0xFEFF, 0xEF, 0xBB, 0xBF)))

skip = {tuple(bytes.fromhex(x)) for x in sys.argv[1:]}
for line in sys.stdin:
    f = line.lstrip(BOM_CHARS).rstrip('\n').split('\t')
    if len(f) < 5:
        continue
    ts, rt, req, dirn, data = f[:5]
    data = data.replace(':', '')
    if len(data) < 180:
        continue
    b = bytes.fromhex(data[:180])
    cls_id = (b[6], b[7])
    if cls_id in skip:
        continue
    size = b[5]
    crc = 0
    for x in b[2:88]:
        crc ^= x
    t = datetime.datetime.fromtimestamp(float(ts)).strftime('%H:%M:%S.%f')[:-3]
    kind = 'SET' if rt == '0x21' else ('GET' if rt == '0xa1' else rt or 'RSP')
    print(f"{t} {kind:3} st={b[0]:02x} tid={b[1]:02x} cls={b[6]:02x} id={b[7]:02x} n={size:2d} "
          f"args={b[8:8 + size].hex()} crc={'ok' if crc == b[88] else 'BAD'}")
