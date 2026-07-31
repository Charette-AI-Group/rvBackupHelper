"""Widget that paints BGR video frames."""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt, Signal
from PySide6.QtGui import QColor, QImage, QMouseEvent, QPainter, QPaintEvent
from PySide6.QtWidgets import QSizePolicy, QWidget

backgroundColor = "#101010"
placeholderColor = "#909090"
# Distinct enough from the placeholder to read as guidance rather than status.
hintColor = "#6ea8d8"
hintGapPixels = 6
# Guide lines have to stay readable over arbitrary video, light or dark.
markerColor = "#ffd166"
markerLabelPadding = 6
markerLabelLift = 4
# Width edges get their own colour so they read as a different measurement
# from the distance lines they sit on.
edgeMarkerColor = "#8ce99a"
edgeTickHalfHeight = 7


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

    # A left click inside the frame, in source-frame pixel coordinates.
    framePointClicked = Signal(int, int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.image = QImage()
        self.placeholderText = "No video"
        self.hintText = ""
        self.markers: list[tuple[int, str]] = []
        self.edgeMarkers: list[tuple[int, int]] = []
        self.setMinimumSize(320, 240)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    @property
    def hasFrame(self) -> bool:
        return not self.image.isNull()

    def setMarkers(self, markers: Sequence[tuple[int, str]]) -> None:
        """Horizontal guides to draw, as (scan line in frame pixels, label)."""
        self.markers = list(markers)
        self.update()

    def setEdgeMarkers(self, marks: Sequence[tuple[int, int]]) -> None:
        """Short vertical ticks at (x, y) in frame pixels, for width edges."""
        self.edgeMarkers = list(marks)
        self.update()

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
        self.paintMarkers(painter)

    def paintMarkers(self, painter: QPainter) -> None:
        if self.image.height() <= 0 or self.image.width() <= 0:
            return
        rect = self.frameRect()
        painter.setPen(QColor(markerColor))
        for scanLine, label in self.markers:
            y = rect.top() + round(scanLine * rect.height() / self.image.height())
            painter.drawLine(rect.left(), y, rect.right(), y)
            if label:
                painter.drawText(
                    rect.left() + markerLabelPadding, y - markerLabelLift, label
                )

        painter.setPen(QColor(edgeMarkerColor))
        for edgeX, scanLine in self.edgeMarkers:
            x = rect.left() + round(edgeX * rect.width() / self.image.width())
            y = rect.top() + round(scanLine * rect.height() / self.image.height())
            painter.drawLine(x, y - edgeTickHalfHeight, x, y + edgeTickHalfHeight)

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

    def toFramePoint(self, widgetPoint: QPoint) -> QPoint | None:
        """Map a widget coordinate back to a pixel in the source frame.

        None when there is no frame, or the click landed on the letterbox
        rather than the picture. Calibration reads distances off exact scan
        lines, so this has to undo the scaling, not approximate it.
        """
        if self.image.isNull():
            return None
        rect = self.frameRect()
        if rect.width() <= 0 or rect.height() <= 0 or not rect.contains(widgetPoint):
            return None
        # Round rather than truncate. The picture is normally scaled down, so one
        # widget row covers several scan lines; flooring would pick the top of
        # that band every time and bias every measurement a pixel low.
        x = round((widgetPoint.x() - rect.left()) * self.image.width() / rect.width())
        y = round((widgetPoint.y() - rect.top()) * self.image.height() / rect.height())
        # The far edge maps one past the last pixel; keep it in range.
        return QPoint(min(x, self.image.width() - 1), min(y, self.image.height() - 1))

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        framePoint = self.toFramePoint(event.position().toPoint())
        if framePoint is not None:
            self.framePointClicked.emit(framePoint.x(), framePoint.y())
