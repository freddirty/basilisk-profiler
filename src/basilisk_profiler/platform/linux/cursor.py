# SPDX-License-Identifier: GPL-2.0-or-later
"""Big custom pointer on X11, YoloMouse style, without touching the game.

The real pointer is hidden with XFixes and the image is shown in a click-through
(empty input shape), always-on-top, override-redirect ARGB window. It is moved only when
XInput2 raw motion events arrive (no polling). XFixes hiding belongs to our X connection,
so the X server shows the normal pointer again by itself if this process dies.
"""
from __future__ import annotations

import logging
import os
import select
import threading

from ...core.cursor import CursorImage

log = logging.getLogger(__name__)


class CursorOverlay:
    """``show(image)`` / ``hide()`` from any thread; each shown image gets its own thread."""

    def __init__(self):
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._wake: tuple[int, int] | None = None
        self._image: CursorImage | None = None

    @property
    def image(self) -> CursorImage | None:
        return self._image

    def show(self, image: CursorImage) -> None:
        with self._lock:
            if image == self._image and self._thread and self._thread.is_alive():
                return
            self._stop_locked()
            r, w = os.pipe()
            self._wake = (r, w)
            self._image = image
            self._thread = threading.Thread(target=self._run, args=(image, r),
                                            name='cursor-overlay', daemon=True)
            self._thread.start()

    def hide(self) -> None:
        with self._lock:
            self._stop_locked()

    close = hide

    def _stop_locked(self) -> None:
        thread, wake = self._thread, self._wake
        self._thread = self._wake = self._image = None
        if wake:
            os.write(wake[1], b'x')
        if thread:
            thread.join(2)
        if wake:
            for fd in wake:
                os.close(fd)

    def _run(self, image: CursorImage, wake_fd: int) -> None:
        try:
            _overlay_loop(image, wake_fd)
        except Exception:  # noqa: BLE001 - never take the daemon down for the pointer
            log.exception('cursor overlay failed')


def _overlay_loop(image: CursorImage, wake_fd: int) -> None:
    from Xlib import X, display
    from Xlib.ext import shape, xinput

    disp = display.Display()
    try:
        screen = disp.screen()
        root = screen.root
        visual = next((v.visual_id for d in screen.allowed_depths if d.depth == 32
                       for v in d.visuals if v.visual_class == X.TrueColor), None)
        if visual is None:
            log.warning('no 32-bit visual: custom cursor needs a compositing desktop')
            return
        w, h = image.width, image.height
        colormap = root.create_colormap(visual, X.AllocNone)
        pixmap = root.create_pixmap(w, h, 32)
        gc = pixmap.create_gc()
        pixmap.put_image(gc, 0, 0, w, h, X.ZPixmap, 32, 0, image.pixels)
        gc.free()

        pos = root.query_pointer()
        win = root.create_window(pos.root_x - image.hot_x, pos.root_y - image.hot_y, w, h, 0,
                                 32, X.InputOutput, visual, override_redirect=True,
                                 background_pixmap=pixmap, border_pixel=0, colormap=colormap)
        win.set_wm_name('basilisk-profiler cursor')
        win.set_wm_class('basilisk-cursor', 'BasiliskProfiler')
        win.shape_rectangles(shape.SO.Set, shape.SK.Input, X.Unsorted, 0, 0, [])
        win.map()
        root.xinput_select_events([(xinput.AllMasterDevices, xinput.RawMotionMask)])
        disp.xfixes_query_version()
        root.xfixes_hide_cursor()
        disp.flush()
        log.info('custom cursor on (%dx%d)', w, h)
        try:
            while True:
                if not disp.pending_events():
                    ready, _, _ = select.select([disp, wake_fd], [], [])
                    if wake_fd in ready:
                        break
                    if disp not in ready:
                        continue
                while disp.pending_events():  # a 1000 Hz burst becomes one move
                    disp.next_event()
                pos = root.query_pointer()
                # Above every time: a game raised later (e.g. going fullscreen) is not on top
                win.configure(x=pos.root_x - image.hot_x, y=pos.root_y - image.hot_y,
                              stack_mode=X.Above)
                disp.flush()
        finally:
            root.xfixes_show_cursor()
            win.destroy()
            pixmap.free()
            colormap.free()
            disp.flush()
            log.info('custom cursor off')
    finally:
        disp.close()
