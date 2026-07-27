"""Widget that paints BGR video frames."""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QImage, QPainter, QPaintEvent
from PySide6.QtWidgets import QSizePolicy, QWidget


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
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    @property
    def hasFrame(self) -> bool:
        return not self.image.isNull()

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
        painter.fillRect(self.rect(), QColor("#101010"))
        if self.image.isNull():
            painter.setPen(QColor("#909090"))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, self.placeholderText
            )
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.drawImage(self.frameRect(), self.image)

    def frameRect(self) -> QRect:
        """Largest centred rectangle keeping the frame's aspect ratio."""
        scaled = self.image.size().scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio
        )
        left = (self.width() - scaled.width()) // 2
        top = (self.height() - scaled.height()) // 2
        return QRect(left, top, scaled.width(), scaled.height())
