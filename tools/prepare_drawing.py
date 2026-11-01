# SPDX-License-Identifier: GPL-2.0-or-later
"""Turn a mouse drawing on paper into an ink layer for the GUI.

    python tools/prepare_drawing.py assets/basilisk_v3_pro_drawing.png \
        src/basilisk_profiler/gui/assets/basilisk_v3_pro_ink.png

The paper becomes transparent: ink alpha = how much darker a pixel is than the paper. The
GUI tints the ink with the theme's text colour, so one file serves light and dark themes;
a dedicated dark drawing can still be dropped in (see DARK_DRAWING in gui/mouse_view.py).
"""
import sys

from PySide6.QtGui import QColor, QGuiApplication, QImage

PAPER_SAMPLE = (40, 40)


def main(src: str, dst: str) -> None:
    QGuiApplication([])
    img = QImage(src).convertToFormat(QImage.Format_ARGB32)
    paper_l = img.pixelColor(*PAPER_SAMPLE).lightness()
    scale = 255 / max(paper_l - 20, 1)
    out = QImage(img.size(), QImage.Format_ARGB32)
    for y in range(img.height()):
        for x in range(img.width()):
            ink = max(0, paper_l - img.pixelColor(x, y).lightness())
            out.setPixelColor(x, y, QColor(0, 0, 0, min(255, int(ink * scale))))
    out.save(dst)
    print(dst, out.width(), out.height())


if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2])
