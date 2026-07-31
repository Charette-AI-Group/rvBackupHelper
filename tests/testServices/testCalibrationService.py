"""Tests for reading and writing calibration files."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from rvBackupHelper.models.calibrationModels import Calibration, CalibrationPoint
from rvBackupHelper.services.calibration.calibrationService import (
    CalibrationError,
    CalibrationService,
    calibrationFormatVersion,
)


@pytest.fixture
def calibration() -> Calibration:
    return Calibration(
        frameWidth=640,
        frameHeight=480,
        points=[CalibrationPoint(6.0, 360), CalibrationPoint(3.0, 420)],
        sourceClip="rvbh-20260727-101154.avi",
        frameIndex=137,
    )


def testSaveThenLoadRoundTrips(tmp_path: Path, calibration: Calibration) -> None:
    service = CalibrationService()
    path = tmp_path / "calibration.json"

    service.save(calibration, path)
    loaded = service.load(path)

    assert loaded.frameWidth == 640
    assert loaded.frameHeight == 480
    assert loaded.sourceClip == "rvbh-20260727-101154.avi"
    assert loaded.frameIndex == 137
    assert loaded.sortedPoints == calibration.sortedPoints


def testSavedFileIsReadableJsonSortedNearToFar(
    tmp_path: Path, calibration: Calibration
) -> None:
    """The file goes into git, so it has to stay legible and diffable."""
    path = tmp_path / "calibration.json"
    service = CalibrationService()

    service.save(calibration, path)
    text = path.read_text(encoding="utf-8")
    payload = json.loads(text)

    assert text.endswith("\n")
    assert "\n  " in text  # indented, not one long line
    assert payload["version"] == calibrationFormatVersion
    assert [p["distanceFeet"] for p in payload["points"]] == [3.0, 6.0]


def testSavedPointsCarryTheirOverlayRow(tmp_path: Path, calibration: Calibration) -> None:
    path = tmp_path / "calibration.json"
    CalibrationService().save(calibration, path)

    payload = json.loads(path.read_text(encoding="utf-8"))

    # 420 of 480 rescaled onto a 96-row canvas.
    nearest = payload["points"][0]
    assert nearest["scanLine"] == 420
    assert nearest["overlayRow"] == 84


def testSaveCreatesMissingDirectories(tmp_path: Path, calibration: Calibration) -> None:
    path = tmp_path / "nested" / "deeper" / "calibration.json"

    CalibrationService().save(calibration, path)

    assert path.exists()


def testWidthEdgesAndFramesRoundTrip(tmp_path: Path) -> None:
    calibration = Calibration(
        frameWidth=640,
        frameHeight=480,
        points=[
            CalibrationPoint(4.0, 316, leftEdge=120, rightEdge=520, frameIndex=2265),
            CalibrationPoint(8.0, 193, frameIndex=3089),
        ],
    )
    path = tmp_path / "calibration.json"
    service = CalibrationService()

    service.save(calibration, path)
    loaded = service.load(path)

    near, far = loaded.sortedPoints
    assert (near.leftEdge, near.rightEdge) == (120, 520)
    assert near.frameIndex == 2265
    assert far.leftEdge is None and far.rightEdge is None
    assert far.frameIndex == 3089
    assert loaded.widthPoints == [near]


def testSavedWidthCarriesItsOverlayColumns(tmp_path: Path) -> None:
    calibration = Calibration(
        frameWidth=640,
        frameHeight=480,
        points=[CalibrationPoint(4.0, 316, leftEdge=120, rightEdge=520)],
    )
    path = tmp_path / "calibration.json"
    CalibrationService().save(calibration, path)

    point = json.loads(path.read_text(encoding="utf-8"))["points"][0]

    assert point["overlayLeft"] == 26  # 120 of 640 onto a 136-wide canvas
    assert point["overlayRight"] == 110  # 520 -> 110.5, rounded half to even


def testAPointWithoutWidthOmitsTheEdgeKeys(tmp_path: Path) -> None:
    """Distance-only calibrations stay legible; absent is not zero."""
    calibration = Calibration(
        frameWidth=640, frameHeight=480, points=[CalibrationPoint(4.0, 316)]
    )
    path = tmp_path / "calibration.json"
    CalibrationService().save(calibration, path)

    point = json.loads(path.read_text(encoding="utf-8"))["points"][0]

    assert "leftEdge" not in point
    assert "rightEdge" not in point


def testOlderFilesWithoutPerPointFramesStillLoad(tmp_path: Path) -> None:
    """Frames used to live on the calibration; those files must still open."""
    path = tmp_path / "legacy.json"
    path.write_text(
        json.dumps(
            {
                "version": calibrationFormatVersion,
                "frameWidth": 640,
                "frameHeight": 480,
                "frameIndex": 3998,
                "points": [{"distanceFeet": 3.0, "scanLine": 430}],
            }
        ),
        encoding="utf-8",
    )

    loaded = CalibrationService().load(path)

    assert loaded.points[0].frameIndex == 3998
    assert loaded.points[0].leftEdge is None


def testLoadingAMissingFileRaises(tmp_path: Path) -> None:
    with pytest.raises(CalibrationError, match="not found"):
        CalibrationService().load(tmp_path / "nope.json")


def testLoadingBrokenJsonRaises(tmp_path: Path) -> None:
    path = tmp_path / "broken.json"
    path.write_text("{not json", encoding="utf-8")

    with pytest.raises(CalibrationError, match="not valid JSON"):
        CalibrationService().load(path)


def testLoadingANonObjectRaises(tmp_path: Path) -> None:
    path = tmp_path / "list.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")

    with pytest.raises(CalibrationError, match="does not contain a calibration"):
        CalibrationService().load(path)


def testLoadingAFutureVersionRaisesRatherThanGuessing(tmp_path: Path) -> None:
    path = tmp_path / "future.json"
    path.write_text(json.dumps({"version": 99, "points": []}), encoding="utf-8")

    with pytest.raises(CalibrationError, match="format version 99"):
        CalibrationService().load(path)


def testLoadingWithMissingFieldsRaises(tmp_path: Path) -> None:
    path = tmp_path / "partial.json"
    path.write_text(
        json.dumps({"version": calibrationFormatVersion, "points": []}),
        encoding="utf-8",
    )

    with pytest.raises(CalibrationError, match="missing or invalid fields"):
        CalibrationService().load(path)


def testLoadingWithAMalformedPointRaises(tmp_path: Path) -> None:
    path = tmp_path / "badPoint.json"
    path.write_text(
        json.dumps(
            {
                "version": calibrationFormatVersion,
                "frameWidth": 640,
                "frameHeight": 480,
                "points": [{"distanceFeet": "near", "scanLine": 420}],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(CalibrationError, match="missing or invalid fields"):
        CalibrationService().load(path)
