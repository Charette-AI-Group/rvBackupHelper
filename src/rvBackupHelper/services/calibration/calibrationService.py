"""Reading and writing calibration files.

JSON on purpose: the data is small, belongs in version control, and stays
readable and diffable years after the drive it was measured on is gone.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from rvBackupHelper import appConfig
from rvBackupHelper.models.calibrationModels import Calibration, CalibrationPoint

logger = logging.getLogger(__name__)

calibrationFormatVersion = 1


class CalibrationError(RuntimeError):
    """A calibration file could not be read or was not valid."""


def defaultCalibrationPath() -> Path:
    return appConfig.calibrationDir / appConfig.defaultCalibrationName


class CalibrationService:
    """Persists a Calibration to a JSON file and back."""

    def save(self, calibration: Calibration, path: Path) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": calibrationFormatVersion,
            "sourceClip": calibration.sourceClip,
            "frameIndex": calibration.frameIndex,
            "frameWidth": calibration.frameWidth,
            "frameHeight": calibration.frameHeight,
            "overlayCanvasWidth": appConfig.overlayCanvasWidth,
            "overlayCanvasHeight": appConfig.overlayCanvasHeight,
            "points": [
                self.pointPayload(calibration, point)
                for point in calibration.sortedPoints
            ],
        }
        # Trailing newline keeps diffs clean in git.
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        logger.info("Saved %d calibration point(s) to %s", len(calibration.points), path)
        return path

    def pointPayload(self, calibration: Calibration, point: CalibrationPoint) -> dict:
        payload = {
            "distanceFeet": point.distanceFeet,
            "scanLine": point.scanLine,
            "frameIndex": point.frameIndex,
            # Written for readers that do not want to redo the maths;
            # scanLine plus frameHeight remains the source of truth.
            "overlayRow": calibration.overlayRow(point.scanLine),
        }
        # Width is optional: a calibration is useful with distances alone.
        if point.leftEdge is not None:
            payload["leftEdge"] = point.leftEdge
            payload["overlayLeft"] = calibration.overlayColumn(point.leftEdge)
        if point.rightEdge is not None:
            payload["rightEdge"] = point.rightEdge
            payload["overlayRight"] = calibration.overlayColumn(point.rightEdge)
        return payload

    def readPoint(self, item: dict, legacyFrameIndex: int) -> CalibrationPoint:
        edges = {
            name: int(item[name])
            for name in ("leftEdge", "rightEdge")
            if item.get(name) is not None
        }
        return CalibrationPoint(
            distanceFeet=float(item["distanceFeet"]),
            scanLine=int(item["scanLine"]),
            # Files written before frames were per-point fall back to the
            # calibration-wide one rather than losing the provenance.
            frameIndex=int(item.get("frameIndex", legacyFrameIndex)),
            **edges,
        )

    def load(self, path: Path) -> Calibration:
        payload = self.readPayload(path)
        version = payload.get("version")
        if version != calibrationFormatVersion:
            raise CalibrationError(
                f"{path.name} is format version {version!r}; "
                f"this build reads version {calibrationFormatVersion}."
            )
        legacyFrameIndex = int(payload.get("frameIndex", 0))
        try:
            points = [
                self.readPoint(item, legacyFrameIndex) for item in payload["points"]
            ]
            calibration = Calibration(
                frameWidth=int(payload["frameWidth"]),
                frameHeight=int(payload["frameHeight"]),
                points=points,
                sourceClip=str(payload.get("sourceClip", "")),
                frameIndex=legacyFrameIndex,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise CalibrationError(f"{path.name} has missing or invalid fields: {exc}") from exc

        logger.info("Loaded %d calibration point(s) from %s", len(points), path)
        return calibration

    def readPayload(self, path: Path) -> dict:
        if not path.exists():
            raise CalibrationError(f"Calibration file not found: {path}")
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise CalibrationError(f"{path.name} is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise CalibrationError(f"{path.name} does not contain a calibration object.")
        return payload
