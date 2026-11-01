# SPDX-License-Identifier: GPL-2.0-or-later
"""Turn the mouse photo into a monochrome line drawing for the GUI (Qt only, no numpy).

    python tools/photo_to_lineart.py photo.png \
        src/basilisk_profiler/gui/assets/basilisk_v3_pro_lines.png

The source is the reference photo on the assets/basilisk-photo branch. Crops CROP (same as
SOURCE_CROP in gui/mouse_view.py), blurs away the mouse-pad texture, runs a
Sobel filter on the luminance and keeps the strong edges as an alpha mask. The GUI tints
the mask with the palette's text colour, so it follows light and dark themes.
"""
import math
import sys

from PySide6.QtCore import QPointF, QRect, Qt
from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter, QPainterPath, QPolygonF

CROP = QRect(100, 40, 1010, 640)
WIDTH = 960
BLUR_FACTOR = 3  # downscale factor used as a cheap blur
LOW, HIGH = 15, 40  # edge strength mapped to alpha 0..255
# Rough outline of the mouse in source-photo pixels; edges outside it (pad texture,
# underglow) are dropped.
OUTLINE = [(112, 148), (148, 110), (540, 56), (715, 66), (915, 160), (1060, 280), (1108, 400),
           (1095, 490), (1035, 560), (930, 610), (730, 672), (555, 680), (410, 612),
           (372, 516), (322, 480), (222, 388), (106, 220)]


def main(src: str, dst: str, low: int = LOW, high: int = HIGH) -> None:
    QGuiApplication([])
    img = QImage(src).copy(CROP).scaledToWidth(WIDTH, Qt.SmoothTransformation)
    gray = img.convertToFormat(QImage.Format_Grayscale8)
    w, h = gray.width(), gray.height()
    blurred = gray.scaled(w // BLUR_FACTOR, h // BLUR_FACTOR, Qt.IgnoreAspectRatio,
                          Qt.SmoothTransformation).scaled(w, h, Qt.IgnoreAspectRatio,
                                                          Qt.SmoothTransformation)
    stride = blurred.bytesPerLine()
    px = bytes(blurred.constBits())
    out = QImage(w, h, QImage.Format_ARGB32)
    out.fill(QColor(0, 0, 0, 0))
    for y in range(1, h - 1):
        r0, r1, r2 = (y - 1) * stride, y * stride, (y + 1) * stride
        for x in range(1, w - 1):
            gx = (px[r0 + x + 1] + 2 * px[r1 + x + 1] + px[r2 + x + 1]
                  - px[r0 + x - 1] - 2 * px[r1 + x - 1] - px[r2 + x - 1])
            gy = (px[r2 + x - 1] + 2 * px[r2 + x] + px[r2 + x + 1]
                  - px[r0 + x - 1] - 2 * px[r0 + x] - px[r0 + x + 1])
            mag = math.hypot(gx, gy) / 4
            if mag > low:
                alpha = min(255, int((mag - low) * 255 / (high - low)))
                out.setPixelColor(x, y, QColor(0, 0, 0, alpha))
    scale = WIDTH / CROP.width()
    outline = QPolygonF([QPointF((x - CROP.x()) * scale, (y - CROP.y()) * scale)
                         for x, y in OUTLINE])
    outside = QPainterPath()
    outside.addRect(0, 0, w, h)
    inside = QPainterPath()
    inside.addPolygon(outline)
    painter = QPainter(out)
    painter.setCompositionMode(QPainter.CompositionMode_Clear)
    painter.fillPath(outside.subtracted(inside), Qt.black)
    painter.end()
    out.save(dst)
    print(dst, w, h)


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], *(int(v) for v in sys.argv[3:5]))
