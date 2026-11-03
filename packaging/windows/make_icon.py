# SPDX-License-Identifier: GPL-2.0-or-later
"""Regenerate app.ico and the Linux app.png (same rounded-mouse shape as the tray icon)."""
from pathlib import Path

from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter

app = QGuiApplication([])
image = QImage(256, 256, QImage.Format_ARGB32)
image.fill(QColor(0, 0, 0, 0))
painter = QPainter(image)
painter.setRenderHint(QPainter.Antialiasing)
painter.setBrush(QColor('#44d62c'))
painter.setPen(QColor('#101010'))
painter.drawRoundedRect(56, 16, 144, 224, 72, 72)
painter.setPen(QColor('#101010'))
painter.drawLine(128, 20, 128, 100)
painter.end()
out = Path(__file__).with_name('app.ico')
image.save(str(out), 'ICO')
png = Path(__file__).parents[1] / 'linux' / 'app.png'
image.save(str(png), 'PNG')
print(out, png)
