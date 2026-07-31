"""Plain data types for the distance calibration.

A calibration is the bridge between the camera image and the real world: a set
of scan lines in the captured frame, each tagged with how far behind the RV
that line actually is.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import StrEnum

from rvBackupHelper import appConfig


class Edge(StrEnum):
    """Which side of the vehicle a width marker belongs to."""

    left = "left"
    right = "right"


@dataclass(frozen=True, order=True)
class CalibrationPoint:
    """One measured distance, the scan line it falls on, and the vehicle width
    at that distance if it was marked.

    Distance leads the field order so points sort naturally near-to-far. Only
    distance and scan line take part in ordering; the rest are measurements
    hanging off that key.

    `frameIndex` lives here rather than on the calibration because a measuring
    pole gets moved between distances, so each point comes from its own frame.
    """

    distanceFeet: float
    scanLine: int
    leftEdge: int | None = field(default=None, compare=False)
    rightEdge: int | None = field(default=None, compare=False)
    frameIndex: int = field(default=0, compare=False)

    @property
    def label(self) -> str:
        # %g drops a pointless trailing ".0" without truncating 2.5
        return f"{self.distanceFeet:g} ft"

    @property
    def hasWidth(self) -> bool:
        """True once both sides are marked; one edge alone draws nothing."""
        return self.leftEdge is not None and self.rightEdge is not None


@dataclass
class Calibration:
    """Measured points, plus the frame geometry they were measured in.

    The frame size is not decoration: a scan line means nothing without the
    height it was measured against, and converting to the OSD canvas needs it.
    """

    frameWidth: int = 0
    frameHeight: int = 0
    points: list[CalibrationPoint] = field(default_factory=list)
    sourceClip: str = ""
    frameIndex: int = 0

    @property
    def isEmpty(self) -> bool:
        return not self.points

    @property
    def sortedPoints(self) -> list[CalibrationPoint]:
        return sorted(self.points)

    def addPoint(self, point: CalibrationPoint) -> None:
        """Add a measurement, replacing any existing one at that distance.

        Re-clicking to correct a misplaced line is the common case, so the
        later click wins rather than leaving two lines for one distance.
        """
        self.points = [p for p in self.points if p.distanceFeet != point.distanceFeet]
        self.points.append(point)

    def setEdge(self, distanceFeet: float, edge: Edge, x: int, frameIndex: int) -> bool:
        """Record one width marker against an existing distance.

        False when that distance has not been marked yet: an edge without a
        line has nothing to attach to, and silently creating one would invent
        a scan line nobody measured.
        """
        for index, point in enumerate(self.points):
            if point.distanceFeet != distanceFeet:
                continue
            side = {"leftEdge": x} if edge is Edge.left else {"rightEdge": x}
            self.points[index] = replace(point, frameIndex=frameIndex, **side)
            return True
        return False

    @property
    def widthPoints(self) -> list[CalibrationPoint]:
        """Points with both edges marked, near to far."""
        return [point for point in self.sortedPoints if point.hasWidth]

    def removeDistance(self, distanceFeet: float) -> bool:
        remaining = [p for p in self.points if p.distanceFeet != distanceFeet]
        removed = len(remaining) != len(self.points)
        self.points = remaining
        return removed

    def clear(self) -> None:
        self.points = []

    def overlayRow(self, scanLine: int, overlayHeight: int | None = None) -> int:
        """Rescale a capture scan line onto the OSD canvas.

        The Video Experimenter draws into a 136x96 buffer while capture runs at
        the camera's own height, so every measured line needs this conversion
        before it can become a row in the Arduino sketch.
        """
        height = appConfig.overlayCanvasHeight if overlayHeight is None else overlayHeight
        if self.frameHeight <= 0 or height <= 0:
            return 0
        row = round(scanLine * height / self.frameHeight)
        return max(0, min(row, height - 1))

    def overlayColumn(self, x: int, overlayWidth: int | None = None) -> int:
        """Rescale a capture column onto the OSD canvas. The width twin of overlayRow."""
        width = appConfig.overlayCanvasWidth if overlayWidth is None else overlayWidth
        if self.frameWidth <= 0 or width <= 0:
            return 0
        column = round(x * width / self.frameWidth)
        return max(0, min(column, width - 1))

    def markers(self) -> list[tuple[int, str]]:
        """Guide lines for the video display, near to far."""
        return [(point.scanLine, point.label) for point in self.sortedPoints]

    def edgeMarkers(self) -> list[tuple[int, int]]:
        """(x, y) of every marked width edge, for the display to tick."""
        marks = []
        for point in self.sortedPoints:
            for edge in (point.leftEdge, point.rightEdge):
                if edge is not None:
                    marks.append((edge, point.scanLine))
        return marks
