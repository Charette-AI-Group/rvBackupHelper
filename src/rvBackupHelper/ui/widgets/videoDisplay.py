"""Widget that paints BGR video frames."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPaintEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

backgroundColor = "#101010"
placeholderColor = "#909090"
# Distinct enough from the placeholder to read as guidance rather than status.
hintColor = "#6ea8d8"
hintGapPixels = 6


def toQImage(frame: np.ndarray) -> QImage:
    """Wrap a BGR frame as a QImage.

    The copy is not optional: without it the QImage points straight at the
    numpy buffer, which the capture loop reuses for the next frame.
    """
    if frame.ndim != 3 or frame.shape[2] != 3:
        raise ValueError(f"Expected a 3-channel BGR frame, got shape {frame.shape}")
    height, width, _ = frame.shape
    image = QImage(
        frame.data,
        width,
        height,
        frame.strides[0],
        QImage.Format.Format_BGR888,
    )
    return image.copy()


class VideoDisplay(QWidget):
    """Shows one frame at a time, centred and letterboxed."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.image = QImage()
        self.placeholderText = "No video"
        self.hintText = ""
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    @property
    def hasFrame(self) -> bool:
        return not self.image.isNull()

    def setHint(self, text: str) -> None:
        """Show a one-off instruction under the placeholder message."""
        self.hintText = text
        self.update()

    def clearHint(self) -> None:
        self.setHint("")

    def showFrame(self, frame: np.ndarray) -> None:
        self.image = toQImage(frame)
        self.update()

    def clear(self, placeholderText: str | None = None) -> None:
        if placeholderText is not None:
            self.placeholderText = placeholderText
        self.image = QImage()
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(backgroundColor))
        if self.image.isNull():
            self.paintPlaceholder(painter)
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(self.frameRect(), self.image)

    def paintPlaceholder(self, painter: QPainter) -> None:
        centred = Qt.AlignmentFlag.AlignCenter
        painter.setPen(QColor(placeholderColor))
        if not self.hintText:
            painter.drawText(self.rect(), centred, self.placeholderText)
            return

        # Two lines: shift each half a line off centre so the pair reads as a
        # centred block rather than the message sitting off-centre.
        shift = (painter.fontMetrics().height() + hintGapPixels) // 2
        painter.drawText(self.rect().translated(0, -shift), centred, self.placeholderText)

        hintFont = painter.font()
        hintFont.setItalic(True)
        painter.setFont(hintFont)
        painter.setPen(QColor(hintColor))
        painter.drawText(self.rect().translated(0, shift), centred, self.hintText)

    def frameRect(self) -> QRect:
        """Largest centred rectangle keeping the frame's aspect ratio."""
        scaled = self.image.size().scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio
        )
        left = (self.width() - scaled.width()) // 2
        top = (self.height() - scaled.height()) // 2
        return QRect(left, top, scaled.width(), scaled.height())
