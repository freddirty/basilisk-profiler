# SPDX-License-Identifier: GPL-2.0-or-later
import struct
import tomllib

import pytest

from basilisk_profiler.core import config as cfg
from basilisk_profiler.core import cursor as cur
from basilisk_profiler.core.model import WindowInfo
from basilisk_profiler.daemon import service as svc
from basilisk_profiler.gui.draft import ConfigDraft


def make_cur(w=4, h=2, hot=(1, 0), kind=2, bpp=32) -> bytes:
    """A .cur with one 32-bit image: left half opaque red, right half transparent."""
    pixels = b''
    for _row in range(h):  # bottom-up, but every row is the same
        for x in range(w):
            pixels += bytes((0, 0, 255, 255)) if x < w // 2 else bytes((10, 20, 30, 0))
    bmp = struct.pack('<IiiHHIIiiII', 40, w, h * 2, 1, bpp, 0, 0, 0, 0, 0, 0) + pixels
    bmp += b'\0' * (((w + 31) // 32) * 4 * h)  # AND mask
    header = struct.pack('<HHH', 0, kind, 1)
    entry = struct.pack('<BBBBHHII', w, h, 0, 0, hot[0], hot[1], len(bmp), 22)
    return header + entry + bmp


def test_parse_premultiplies_and_keeps_hotspot():
    image = cur.parse(make_cur())
    assert (image.width, image.height, image.hot_x, image.hot_y) == (4, 2, 1, 0)
    assert image.pixels[:4] == bytes((0, 0, 255, 255))
    assert image.pixels[8:12] == bytes((0, 0, 0, 0))  # transparent pixel premultiplied
    assert len(image.pixels) == 4 * 2 * 4


def test_ico_has_no_hotspot():
    assert cur.parse(make_cur(kind=1)).hot_x == 0


def test_scaled_nearest():
    image = cur.parse(make_cur()).scaled(2)
    assert (image.width, image.height, image.hot_x) == (8, 4, 2)
    assert image.pixels[12:16] == bytes((0, 0, 255, 255))  # x=3 still from source x=1
    assert image.pixels[16:20] == bytes((0, 0, 0, 0))


@pytest.mark.parametrize('data', [b'', b'\0\0\3\0\1\0', make_cur(bpp=8)])
def test_bad_files(tmp_path, data):
    path = tmp_path / 'x.cur'
    path.write_bytes(data)
    with pytest.raises(cur.CursorError):
        cur.load(path)


def test_resolve(tmp_path):
    assert cur.resolve('a.cur', tmp_path) == tmp_path / 'cursors' / 'a.cur'
    absolute = tmp_path / 'elsewhere' / 'a.cur'
    assert cur.resolve(str(absolute), tmp_path) == absolute


CONFIG = cfg.EXAMPLE + '''
[[profile]]
name = "game"
cursor = "pink.cur"
cursor_scale = 2.0

[[rule]]
match_class = "steam_app_899770"
profile = "game"
'''


def test_config_round_trip(tmp_path):
    config = cfg.parse(tomllib.loads(CONFIG))
    assert config.profiles['game'].cursor == 'pink.cur'
    assert config.profiles['game'].cursor_scale == 2.0
    assert config.profiles['general'].cursor is None
    path = tmp_path / 'c.toml'
    cfg.save(config, path)
    assert cfg.load(path) == config


def test_config_rejects_bad_scale():
    with pytest.raises(cfg.ConfigError):
        cfg.parse(tomllib.loads(CONFIG.replace('cursor_scale = 2.0', 'cursor_scale = 9.0')))


def test_draft_set_cursor():
    d = ConfigDraft(tomllib.loads(cfg.EXAMPLE))
    d.set_cursor('general', 'pink.cur', 1.5)
    assert d.cursor('general') == ('pink.cur', 1.5)
    assert d.config().profiles['general'].cursor_scale == 1.5
    d.set_cursor('general', None)
    assert d.cursor('general') == (None, 1.0)


class FakeOverlay:
    def __init__(self):
        self.shown = []  # image or None per change

    def show(self, image):
        self.shown.append(image)

    def hide(self):
        self.shown.append(None)


@pytest.fixture
def game(tmp_path):
    path = tmp_path / 'config.toml'
    path.write_text(CONFIG)
    (tmp_path / 'cursors').mkdir()
    (tmp_path / 'cursors' / 'pink.cur').write_bytes(make_cur())
    overlay = FakeOverlay()

    def no_device():
        raise OSError('absent')

    service = svc.Service(path, open_device=no_device, cursor_overlay=overlay)
    return service, overlay


def test_cursor_follows_window_without_device(game):
    service, overlay = game
    service.tick()
    assert overlay.shown == []  # general profile: normal pointer, nothing to do
    service.on_window(WindowInfo(process='last epoch', wm_class='steam_app_899770'))
    service.tick()
    assert overlay.shown[-1].width == 8  # scaled 2x, no debounce, no mouse needed
    service.tick()
    assert len(overlay.shown) == 1  # unchanged: not shown again
    service.on_window(WindowInfo(process='firefox'))
    service.tick()
    assert overlay.shown[-1] is None


def test_pause_and_shutdown_restore_pointer(game):
    service, overlay = game
    service.on_window(WindowInfo(wm_class='steam_app_899770'))
    service.tick()
    service.set_paused(True)
    assert overlay.shown[-1] is None
    service.set_paused(False)
    assert overlay.shown[-1] is not None
    service.shutdown()
    assert overlay.shown[-1] is None


def test_missing_cursor_file_reports_error(game, tmp_path):
    service, overlay = game
    (tmp_path / 'cursors' / 'pink.cur').unlink()
    service.on_window(WindowInfo(wm_class='steam_app_899770'))
    service.tick()
    assert overlay.shown[-1] is None
    assert 'pink.cur' in service.cursor_error
