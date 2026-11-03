# SPDX-License-Identifier: GPL-2.0-or-later
"""Custom pointer images: Windows .cur / .ico files (e.g. the user's own YoloMouse cursors).

No cursor images ship with the program; profiles point at files the user has. A relative
path is looked up in the ``cursors`` folder next to the config file.
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path

SCALE_MIN = 0.25
SCALE_MAX = 4.0


class CursorError(ValueError):
    pass


@dataclass(frozen=True)
class CursorImage:
    width: int
    height: int
    hot_x: int
    hot_y: int
    pixels: bytes  # rows top-down, premultiplied BGRA (an X11 32-bit ARGB visual's layout)

    def scaled(self, factor: float) -> CursorImage:
        """Nearest-neighbour scaling, so the edges stay as sharp as YoloMouse's."""
        if factor == 1.0:
            return self
        w, h = max(1, round(self.width * factor)), max(1, round(self.height * factor))
        src = self.pixels
        rows = []
        for y in range(h):
            sy = min(self.height - 1, int(y / factor)) * self.width
            rows.append(b''.join(src[(sy + min(self.width - 1, int(x / factor))) * 4:][:4]
                                 for x in range(w)))
        return CursorImage(w, h, round(self.hot_x * factor), round(self.hot_y * factor),
                           b''.join(rows))


def cursor_dir(config_dir: Path) -> Path:
    return config_dir / 'cursors'


def resolve(path: str, config_dir: Path) -> Path:
    """``~`` is expanded; a relative path is taken from the cursors folder."""
    p = Path(path).expanduser()
    return p if p.is_absolute() else cursor_dir(config_dir) / p


def load(path: Path) -> CursorImage:
    """The largest image in a .cur / .ico file (32-bit, or PNG-compressed via Qt)."""
    try:
        data = path.read_bytes()
    except OSError as e:
        raise CursorError(f'{path}: {e.strerror or e}') from e
    try:
        return parse(data)
    except (struct.error, IndexError) as e:
        raise CursorError(f'{path}: not a valid cursor file') from e
    except CursorError as e:
        raise CursorError(f'{path}: {e}') from e


def parse(data: bytes) -> CursorImage:
    reserved, kind, count = struct.unpack_from('<HHH', data, 0)
    if reserved != 0 or kind not in (1, 2) or count == 0:
        raise CursorError('not a .cur / .ico file')
    entries = []
    for i in range(count):
        w, h, _, _, p1, p2, size, offset = struct.unpack_from('<BBBBHHII', data, 6 + 16 * i)
        entries.append((w or 256, h or 256, p1, p2, size, offset))
    w, h, hot_x, hot_y, size, offset = max(entries, key=lambda e: e[0] * e[1])
    if kind == 1:  # .ico: no hotspot, use the top left corner
        hot_x = hot_y = 0
    blob = data[offset:offset + size]
    if blob[:8] == b'\x89PNG\r\n\x1a\n':
        raise CursorError('PNG-compressed cursors are not supported')
    header_size, bmp_w, _, _, bpp = struct.unpack_from('<IiiHH', blob, 0)
    if bpp != 32:
        raise CursorError(f'only 32-bit colour cursors are supported (this one is {bpp}-bit)')
    stride = bmp_w * 4
    bitmap = blob[header_size:header_size + stride * h]
    if len(bitmap) < stride * h:
        raise CursorError('image data is cut short')
    out = bytearray()
    for row in range(h - 1, -1, -1):  # BMP rows are stored bottom-up
        line = bitmap[row * stride:(row + 1) * stride]
        for x in range(0, w * 4, 4):
            b, g, r, a = line[x:x + 4]
            out += bytes((b * a // 255, g * a // 255, r * a // 255, a))
    return CursorImage(w, h, min(hot_x, w - 1), min(hot_y, h - 1), bytes(out))
