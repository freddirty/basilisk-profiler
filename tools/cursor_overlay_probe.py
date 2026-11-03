# SPDX-License-Identifier: GPL-2.0-or-later
"""Probe: replace the X11 pointer with a big custom cursor (.cur file) for a while.

Hides the real pointer with XFixes and shows the image in a click-through, always-on-top
ARGB override-redirect window that follows XInput2 raw motion events (no polling). The
X server shows the real pointer again as soon as this process exits, even after a crash.

    .venv/bin/python tools/cursor_overlay_probe.py CURSOR.cur --seconds 120 --scale 2
"""
from __future__ import annotations

import argparse
import struct
import sys
import time
from pathlib import Path


def load_cur(path: Path) -> tuple[int, int, int, int, bytes]:
    """Largest 32-bit image of a .cur/.ico → (w, h, hot_x, hot_y, premultiplied BGRA)."""
    data = path.read_bytes()
    _, kind, count = struct.unpack_from('<HHH', data, 0)
    entries = []
    for i in range(count):
        w, h, _, _, p1, p2, size, offset = struct.unpack_from('<BBBBHHII', data, 6 + 16 * i)
        entries.append((w or 256, h or 256, p1, p2, size, offset))
    w, h, hx, hy, size, offset = max(entries, key=lambda e: e[0] * e[1])
    if kind != 2:
        hx = hy = 0
    blob = data[offset:offset + size]
    if blob[:8] == b'\x89PNG\r\n\x1a\n':
        raise SystemExit('PNG-compressed cursors are not supported by this probe')
    hdr_size, bw, bh2, _, bpp = struct.unpack_from('<IiiHH', blob, 0)
    if bpp != 32:
        raise SystemExit(f'only 32-bit cursors are supported by this probe (got {bpp} bpp)')
    stride = bw * 4
    pixels = blob[hdr_size:hdr_size + stride * h]
    rows = [pixels[r * stride:(r + 1) * stride] for r in range(h)][::-1]  # BMP is bottom-up
    out = bytearray()
    for row in rows:
        for x in range(0, stride, 4):
            b, g, r, a = row[x:x + 4]
            out += bytes((b * a // 255, g * a // 255, r * a // 255, a))
    return w, h, hx, hy, bytes(out)


def scale_nearest(w: int, h: int, px: bytes, factor: float) -> tuple[int, int, bytes]:
    nw, nh = max(1, round(w * factor)), max(1, round(h * factor))
    out = bytearray()
    for y in range(nh):
        sy = min(h - 1, int(y / factor))
        for x in range(nw):
            sx = min(w - 1, int(x / factor))
            i = (sy * w + sx) * 4
            out += px[i:i + 4]
    return nw, nh, bytes(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('cur', type=Path)
    ap.add_argument('--seconds', type=float, default=60)
    ap.add_argument('--scale', type=float, default=1.0)
    args = ap.parse_args()

    from Xlib import X, display
    from Xlib.ext import shape, xinput

    w, h, hx, hy, px = load_cur(args.cur)
    if args.scale != 1.0:
        w, h, px = scale_nearest(w, h, px, args.scale)
        hx, hy = round(hx * args.scale), round(hy * args.scale)

    disp = display.Display()
    screen = disp.screen()
    root = screen.root
    visual = next((v.visual_id for d in screen.allowed_depths if d.depth == 32
                   for v in d.visuals if v.visual_class == X.TrueColor), None)
    if visual is None:
        print('no 32-bit ARGB visual (compositing off?)', file=sys.stderr)
        return 1
    colormap = root.create_colormap(visual, X.AllocNone)
    pixmap = root.create_pixmap(w, h, 32)
    gc = pixmap.create_gc()
    pixmap.put_image(gc, 0, 0, w, h, X.ZPixmap, 32, 0, px)

    pos = root.query_pointer()
    win = root.create_window(pos.root_x - hx, pos.root_y - hy, w, h, 0, 32, X.InputOutput, visual,
                             override_redirect=True, background_pixmap=pixmap, border_pixel=0,
                             colormap=colormap)
    win.set_wm_name('basilisk-profiler cursor')
    win.set_wm_class('basilisk-cursor', 'BasiliskProfiler')
    win.shape_rectangles(shape.SO.Set, shape.SK.Input, X.Unsorted, 0, 0, [])  # click-through
    win.map()

    root.xinput_select_events([(xinput.AllMasterDevices, xinput.RawMotionMask)])
    disp.xfixes_query_version()
    root.xfixes_hide_cursor()
    disp.flush()

    deadline = time.monotonic() + args.seconds
    moves = 0
    import select
    try:
        while time.monotonic() < deadline:
            if not disp.pending_events():
                ready, _, _ = select.select([disp], [], [], max(0.0, deadline - time.monotonic()))
                if not ready:
                    break
            while disp.pending_events():  # coalesce a burst of 1000 Hz motion into one move
                disp.next_event()
            pos = root.query_pointer()
            win.configure(x=pos.root_x - hx, y=pos.root_y - hy, stack_mode=X.Above)
            disp.flush()
            moves += 1
    except KeyboardInterrupt:
        pass
    finally:
        root.xfixes_show_cursor()
        win.destroy()
        disp.flush()
    print(f'done, {moves} moves')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
