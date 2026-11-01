# SPDX-License-Identifier: GPL-2.0-or-later
"""Mouse drawing with clickable button areas and Synapse-style callout labels.

DRAWING is the owner's pencil drawing turned into an ink layer by tools/prepare_drawing.py;
it is tinted with the palette's text colour, so it works on light and dark themes. If
DARK_DRAWING exists it is used as-is on dark themes instead. Hotspots are in drawing
pixels (1024x614); a replacement drawing of the same framing keeps them aligned.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QSizePolicy, QWidget

from ..core.model import BUTTON_IDS

ASSETS = Path(__file__).parent / 'assets'
DRAWING = ASSETS / 'basilisk_v3_pro_ink.png'
DARK_DRAWING = ASSETS / 'basilisk_v3_pro_dark.png'
ACCENT = QColor('#44d62c')
DIM = QColor('#8a8a8a')
LABEL_WIDTH = 190
LABEL_HEIGHT = 36
LABEL_GAP = 8


@dataclass(frozen=True)
class Hotspot:
    key: str  # config button name, or an info-only id
    title: str
    rect: QRectF  # in drawing pixels
    side: str  # 'left' or 'right' label column
    editable: bool = True
    # labels are stacked per side in HOTSPOTS order, chosen so callout lines do not cross:
    # on the right, the spot furthest right gets the top label and the lines fan out


# Names follow Synapse's button map. Left and right click stay unmappable on purpose, so a
# profile can never take away the primary buttons.
HOTSPOTS = (
    Hotspot('right_click', 'Jobb klikk', QRectF(130, 98, 90, 34), 'left', False),
    Hotspot('left_click', 'Bal klikk', QRectF(170, 185, 320, 110), 'left', False),
    Hotspot('button5', 'Elülső oldalgomb (Mouse 5)', QRectF(300, 322, 138, 30), 'left'),
    Hotspot('side_bottom', 'Érzékenység-clutch', QRectF(250, 346, 96, 40), 'left'),
    Hotspot('button4', 'Hátsó oldalgomb (Mouse 4)', QRectF(444, 334, 144, 44), 'left'),
    Hotspot('dpi_cycle', 'DPI-fokozat váltás', QRectF(462, 124, 46, 32), 'right'),
    Hotspot('scroll_mode', 'Görgő mód (racsnis / sima)', QRectF(406, 120, 50, 30), 'right'),
    Hotspot('tilt_right', 'Görgő döntés jobbra', QRectF(346, 112, 26, 36), 'right'),
    Hotspot('wheel_click', 'Görgőkattintás', QRectF(268, 100, 76, 52), 'right'),
    Hotspot('tilt_left', 'Görgő döntés balra', QRectF(238, 112, 26, 36), 'right'),
    Hotspot('profile', 'Profilváltó gomb (alul)', QRectF(620, 515, 120, 30), 'right'),
)


class MouseView(QWidget):
    buttonClicked = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.photo = QPixmap(str(DRAWING))
        self.dark_photo = QPixmap(str(DARK_DRAWING)) if DARK_DRAWING.exists() else None
        self._tint: tuple[int, QPixmap] | None = None
        self.labels: dict[str, str] = {}
        self.selected: str | None = None
        self.hover: str | None = None
        self.setMouseTracking(True)
        self.setMinimumSize(760, 420)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def set_labels(self, labels: dict[int, str]) -> None:
        names = {v: k for k, v in BUTTON_IDS.items()}
        self.labels = {names[b]: text for b, text in labels.items() if b in names}
        self.update()

    def select(self, button: int | None) -> None:
        names = {v: k for k, v in BUTTON_IDS.items()}
        self.selected = names.get(button)
        self.update()

    def _drawing(self) -> QPixmap:
        """The ink layer filled with the current text colour (cached per colour)."""
        color = self.palette().text().color()
        if self.dark_photo is not None and color.lightness() > 128:
            return self.dark_photo
        if self._tint is None or self._tint[0] != color.rgba():
            pixmap = QPixmap(self.photo)
            painter = QPainter(pixmap)
            painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
            painter.fillRect(pixmap.rect(), color)
            painter.end()
            self._tint = (color.rgba(), pixmap)
        return self._tint[1]

    # --- geometry ----------------------------------------------------------------

    def _photo_rect(self) -> QRectF:
        avail = QRectF(LABEL_WIDTH, 0, self.width() - 2 * LABEL_WIDTH, self.height())
        scale = min(avail.width() / self.photo.width(), avail.height() / self.photo.height())
        w, h = self.photo.width() * scale, self.photo.height() * scale
        return QRectF(avail.x() + (avail.width() - w) / 2, avail.y() + (avail.height() - h) / 2,
                      w, h)

    def _map(self, rect: QRectF) -> QRectF:
        target = self._photo_rect()
        s = target.width() / self.photo.width()
        return QRectF(target.x() + rect.x() * s, target.y() + rect.y() * s,
                      rect.width() * s, rect.height() * s)

    def _label_rects(self) -> dict[str, QRectF]:
        """Each label as close to its hotspot's height as possible without overlapping."""
        rects = {}
        step = LABEL_HEIGHT + LABEL_GAP
        for side in ('left', 'right'):
            spots = [h for h in HOTSPOTS if h.side == side]
            ys = []
            for h in spots:
                y = self._map(h.rect).center().y() - LABEL_HEIGHT / 2
                ys.append(max(y, ys[-1] + step) if ys else max(y, 4))
            overflow = (ys[-1] + LABEL_HEIGHT + 4) - self.height() if ys else 0
            if overflow > 0:  # push the stack back up from the bottom
                ys[-1] -= overflow
                for i in range(len(ys) - 2, -1, -1):
                    ys[i] = min(ys[i], ys[i + 1] - step)
            x = 6 if side == 'left' else self.width() - LABEL_WIDTH + 6
            for h, y in zip(spots, ys, strict=True):
                rects[h.key] = QRectF(x, y, LABEL_WIDTH - 12, LABEL_HEIGHT)
        return rects

    def _hit(self, pos: QPointF) -> str | None:
        labels = self._label_rects()
        for h in HOTSPOTS:
            if h.editable and (self._map(h.rect).contains(pos) or labels[h.key].contains(pos)):
                return h.key
        return None

    # --- events ------------------------------------------------------------------

    def mouseMoveEvent(self, event):
        hover = self._hit(event.position())
        if hover != self.hover:
            self.hover = hover
            self.setCursor(Qt.PointingHandCursor if hover else Qt.ArrowCursor)
            self.update()

    def mousePressEvent(self, event):
        key = self._hit(event.position())
        if key and event.button() == Qt.LeftButton:
            self.selected = key
            self.update()
            self.buttonClicked.emit(BUTTON_IDS[key])

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.SmoothPixmapTransform)
        painter.drawPixmap(self._photo_rect().toRect(), self._drawing())
        labels = self._label_rects()
        photo = self._photo_rect()
        for h in HOTSPOTS:
            spot = self._map(h.rect)
            label = labels[h.key]
            active = h.key in (self.selected, self.hover)
            color = ACCENT if active else (self.palette().text().color() if h.editable else DIM)
            # callout: label edge -> horizontally to just inside the photo -> hotspot centre
            start = QPointF(label.right() + 4, label.center().y()) if h.side == 'left' \
                else QPointF(label.left() - 4, label.center().y())
            end = spot.center()
            edge = photo.left() + 12 if h.side == 'left' else photo.right() - 12
            elbow = QPointF(min(edge, end.x()) if h.side == 'left' else max(edge, end.x()),
                            start.y())
            path = QPainterPath(start)
            path.lineTo(elbow)
            path.lineTo(end)
            painter.setPen(QPen(color, 2 if active else 1))
            painter.setBrush(Qt.NoBrush)
            painter.drawPath(path)
            painter.setBrush(color)
            painter.drawEllipse(end, 4, 4)
            if active and h.editable:
                painter.setBrush(Qt.NoBrush)
                painter.drawRoundedRect(spot, 6, 6)
            # label: title + current action
            painter.setPen(color)
            align = (Qt.AlignRight if h.side == 'left' else Qt.AlignLeft) | Qt.AlignVCenter
            text = h.title if not h.editable else f'{h.title}\n{self.labels.get(h.key, "")}'
            font = painter.font()
            font.setBold(h.key == self.selected)
            painter.setFont(font)
            painter.drawText(label, align, text)
        painter.end()
