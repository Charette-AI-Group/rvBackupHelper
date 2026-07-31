"""Tests for generating the Arduino sketch from a calibration."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pytest

from rvBackupHelper import appConfig
from rvBackupHelper.models.calibrationModels import Calibration, CalibrationPoint
from rvBackupHelper.services.sketch.sketchService import (
    SketchError,
    SketchService,
    defaultSketchPath,
)


@pytest.fixture
def calibration() -> Calibration:
    return Calibration(
        frameWidth=640,
        frameHeight=480,
        points=[
            CalibrationPoint(10.0, 330),
            CalibrationPoint(3.0, 430),
            CalibrationPoint(6.0, 372),
        ],
        sourceClip="rvbh-20260727-101154.avi",
        frameIndex=137,
    )


@pytest.fixture
def sketch(calibration: Calibration) -> str:
    return SketchService().generate(
        calibration, generatedAt=datetime(2026, 7, 27, 10, 32)
    )


gridEntry = re.compile(r"\{\s*(\d+),\s*(\d+),\s*(\d+),\s*\"([^\"]+)\"\s*\}")


def gridRows(sketch: str) -> list[tuple[int, str]]:
    """The (row, label) pairs actually emitted into the GRID array."""
    return [(int(row), label) for row, _, _, label in gridEntry.findall(sketch)]


def gridLabels(sketch: str) -> list[tuple[int, int, str]]:
    """The (labelX, labelY, label) placements emitted into the GRID array."""
    return [
        (int(x), int(y), label) for _, x, y, label in gridEntry.findall(sketch)
    ]


def testGridRowsAreScaledSortedAndLabelled(sketch: str) -> None:
    # 430, 372 and 330 of 480, rescaled onto the 96-row canvas.
    assert gridRows(sketch) == [(86, "3 ft"), (74, "6 ft"), (66, "10 ft")]


def testEachRowRecordsTheScanLineItCameFrom(sketch: str) -> None:
    """Provenance per line, so a suspect grid can be traced back."""
    assert "// scan line 430 of 480" in sketch
    assert "// scan line 372 of 480" in sketch


def testHeaderCarriesTheProvenance(sketch: str) -> None:
    assert "rvbh-20260727-101154.avi (frame 137)" in sketch
    assert "640 x 480 capture" in sketch
    assert "2026-07-27 10:32" in sketch
    assert "GENERATED FILE" in sketch


def testHeaderWarnsAboutTheBoardAndLibrary(sketch: str) -> None:
    """The hardware traps belong with the sketch, not only in the README."""
    assert "Uno R4" in sketch
    assert "arduino-tvout-ve" in sketch
    assert "OUTPUT SELECT" in sketch


def testSketchHasTheOverlayBoilerplate(sketch: str) -> None:
    assert "#include <TVout.h>" in sketch
    assert "void initOverlay()" in sketch
    assert "ISR(INT0_vect)" in sketch
    assert "display.scanLine = 0;" in sketch
    assert f"#define W {appConfig.overlayCanvasWidth}" in sketch
    assert f"#define H {appConfig.overlayCanvasHeight}" in sketch


def testGridCountMatchesThePoints(sketch: str) -> None:
    assert "GRID_COUNT" in sketch
    assert len(gridRows(sketch)) == 3


def testBracesAreBalanced(sketch: str) -> None:
    """Cheap guard that templating did not mangle the C structure."""
    assert sketch.count("{") == sketch.count("}")
    assert sketch.count("(") == sketch.count(")")


def testLabelsNeverOverlapOnRealRvData() -> None:
    """Regression: the first real calibration put two labels on top of each other.

    Rows 5 and 12 are seven apart, but the top-of-canvas clamp pushes the
    upper label down to y=7 while the lower one sits at y=5 — two rows apart,
    with 6px glyphs. On screen they merged into unreadable mush.
    """
    calibration = Calibration(
        frameWidth=640,
        frameHeight=480,
        points=[
            CalibrationPoint(0.5, 461),
            CalibrationPoint(1.0, 427),
            CalibrationPoint(2.0, 388),
            CalibrationPoint(4.0, 316),
            CalibrationPoint(8.0, 193),
            CalibrationPoint(16.0, 58),
            CalibrationPoint(20.0, 23),
        ],
        sourceClip="rvbh-20260730-100335.avi",
        frameIndex=3998,
    )

    labels = gridLabels(SketchService().generate(calibration))

    assert len(labels) == 7
    for index, (x, y, label) in enumerate(labels):
        for otherX, otherY, otherLabel in labels[index + 1 :]:
            verticallyClose = abs(y - otherY) < 6
            horizontallyClose = (
                x < otherX + 4 * len(otherLabel) and otherX < x + 4 * len(label)
            )
            assert not (verticallyClose and horizontallyClose), (
                f"'{label}' at ({x},{y}) overlaps '{otherLabel}' at ({otherX},{otherY})"
            )


def testCrowdedLabelsMoveToTheOppositeSide() -> None:
    calibration = Calibration(
        frameWidth=640,
        frameHeight=480,
        points=[CalibrationPoint(16.0, 58), CalibrationPoint(20.0, 23)],
    )

    labels = gridLabels(SketchService().generate(calibration))

    # One stays left, the other is pushed right rather than being drawn over it.
    assert min(x for x, _, _ in labels) <= 2
    assert max(x for x, _, _ in labels) > 50


def testLabelsStayInsideTheCanvas() -> None:
    calibration = Calibration(
        frameWidth=640,
        frameHeight=480,
        points=[CalibrationPoint(16.0, 58), CalibrationPoint(20.0, 23)],
    )

    for x, y, label in gridLabels(SketchService().generate(calibration)):
        assert 0 <= x
        assert x + 4 * len(label) <= appConfig.overlayCanvasWidth
        assert 0 <= y < appConfig.overlayCanvasHeight


def testGeneratingWithNoPointsRaises() -> None:
    with pytest.raises(SketchError, match="no points"):
        SketchService().generate(Calibration(frameWidth=640, frameHeight=480))


def testGeneratingWithoutAFrameHeightRaises() -> None:
    calibration = Calibration(points=[CalibrationPoint(3.0, 430)])

    with pytest.raises(SketchError, match="no frame height"):
        SketchService().generate(calibration)


def testCollidingRowsAreReported() -> None:
    """480 into 96 is 5:1, so scan lines a few apart collapse onto one row."""
    calibration = Calibration(
        frameWidth=640,
        frameHeight=480,
        points=[CalibrationPoint(3.0, 430), CalibrationPoint(4.0, 428)],
    )

    collisions = SketchService().collidingRows(calibration)

    assert list(collisions) == [86]
    assert [point.label for point in collisions[86]] == ["3 ft", "4 ft"]


def testWellSpacedRowsDoNotCollide(calibration: Calibration) -> None:
    assert SketchService().collidingRows(calibration) == {}


def testSaveWritesTheSketchAndCreatesItsFolder(
    tmp_path: Path, calibration: Calibration
) -> None:
    path = tmp_path / "rvbhGrid" / "rvbhGrid.ino"

    SketchService().save(calibration, path)

    assert path.exists()
    assert "#include <TVout.h>" in path.read_text(encoding="utf-8")


def testDefaultPathPutsTheSketchInItsOwnFolder() -> None:
    """The Arduino IDE requires the .ino to match its parent folder name."""
    path = defaultSketchPath()

    assert path.suffix == ".ino"
    assert path.stem == path.parent.name
