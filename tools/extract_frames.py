# SPDX-License-Identifier: GPL-2.0-or-later
"""Turn a tshark field dump of Razer control transfers into a fixture file.

Reads lines of ``usb.bmRequestType <TAB> usb.data_fragment <TAB> usb.control.Response``
on stdin and writes ``<dir> <90-byte hex>`` lines (``req`` = SET_REPORT payload,
``rsp`` = GET_REPORT payload). Chroma frame updates (class 0x0F, id 0x03) are dropped.

    tshark -r capture.pcap -Y "usb.transfer_type==2" \
        -T fields -e usb.bmRequestType -e usb.data_fragment -e usb.control.Response \
        | python tools/extract_frames.py > data/session1/frames.txt
"""
import sys

# PowerShell pipes may prepend a BOM, sometimes mis-decoded as cp1252
BOM_CHARS = ''.join(map(chr, (0xFEFF, 0xEF, 0xBB, 0xBF)))

for line in sys.stdin:
    fields = line.lstrip(BOM_CHARS).rstrip('\n').split('\t')
    if len(fields) < 3:
        continue
    req_type, fragment, response = fields[:3]
    data = (fragment or response).replace(':', '')
    if len(data) != 180:
        continue
    frame = bytes.fromhex(data)
    if (frame[6], frame[7]) == (0x0F, 0x03):
        continue
    print('req' if req_type == '0x21' else 'rsp', data)
