"""Plain data types for the distance calibration.

A calibration is the bridge between the camera image and the real world: a set
of scan lines in the captured frame, each tagged with how far behind the RV
that line actually is.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rvBackupHelper import appConfig


@dataclass(frozen=True, order=True)
class CalibrationPoint:
    """One measured distance and the scan line it falls on.

    Distance leads the field order so points sort naturally near-to-far.
    """

    distanceFeet: float
    scanLine: int

    @property
    def label(self) -> str:
        # %g drops a pointless trailing ".0" without truncating 2.5
        return f"{self.distanceFeet:g} ft"


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

    def markers(self) -> list[tuple[int, str]]:
        """Guide lines for the video display, near to far."""
        return [(point.scanLine, point.label) for point in self.sortedPoints]
