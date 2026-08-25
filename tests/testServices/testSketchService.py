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
    sketchFolderPath,
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


# Labels live in flash as named constants, so a GRID row names one rather than
# carrying the text inline.
labelDeclaration = re.compile(r'const char (gridLabel\d+)\[\] PROGMEM = "([^"]+)";')
gridEntry = re.compile(
    r"\{\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(\d+),\s*(gridLabel\d+)\s*\}"
)


def gridEntries(sketch: str) -> list[dict]:
    """Every GRID row as a dict, with its label text resolved from flash."""
    labels = dict(labelDeclaration.findall(sketch))
    return [
        {
            "row": int(row),
            "thickness": int(thickness),
            "labelX": int(labelX),
            "labelY": int(labelY),
            "labelWidth": int(labelWidth),
            "label": labels[symbol],
        }
        for row, thickness, labelX, labelY, labelWidth, symbol in gridEntry.findall(
            sketch
        )
    ]


def gridRows(sketch: str) -> list[tuple[int, str]]:
    """The (row, label) pairs actually emitted into the GRID array."""
    return [(entry["row"], entry["label"]) for entry in gridEntries(sketch)]


def gridLabels(sketch: str) -> list[tuple[int, int, str]]:
    """The (labelX, labelY, label) placements emitted into the GRID array."""
    return [
        (entry["labelX"], entry["labelY"], entry["label"]) for entry in gridEntries(sketch)
    ]


def testGridRowsAreScaledSortedAndLabelled(sketch: str) -> None:
    # 430, 372 and 330 of 480, rescaled onto the 96-row canvas.
    assert gridRows(sketch) == [(86, "3 ft"), (74, "6 ft"), (66, "10 ft")]


def testEachRowRecordsTheScanLineItCameFrom(sketch: str) -> None:
    """Provenance per line, so a suspect grid can be traced back."""
    assert "scan line 430 of 480" in sketch
    assert "scan line 372 of 480" in sketch


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


def testSketchRefusesToBuildAgainstTheStockTVout(sketch: str) -> None:
    """capture() exists only in the Video Experimenter fork.

    The stock library compiles and links without complaint and then leaves the
    input capture interrupt initOverlay() enables with no handler, so the board
    resets on every sync pulse. Better to fail at the compiler.
    """
    assert "(void)&TVout::capture;" in sketch


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
    """Lines closer together than a glyph is tall still need the right slot.

    Centring labels in their own lines fixed the common case, but two lines
    two rows apart would still overlap on the left.
    """
    calibration = Calibration(
        frameWidth=640,
        frameHeight=480,
        # Scan lines 100 and 110 rescale onto rows 20 and 22.
        points=[CalibrationPoint(3.0, 100), CalibrationPoint(4.0, 110)],
    )

    labels = gridLabels(SketchService().generate(calibration))

    assert min(x for x, _, _ in labels) <= 2
    assert max(x for x, _, _ in labels) > 50


def testLabelsStayInsideTheCanvas() -> None:
    calibration = Calibration(
        frameWidth=640,
        frameHeight=480,
        # Includes the topmost and bottommost rows the canvas allows.
        points=[
            CalibrationPoint(0.0, 479),
            CalibrationPoint(3.0, 100),
            CalibrationPoint(4.0, 110),
            CalibrationPoint(20.0, 0),
        ],
    )

    for x, y, label in gridLabels(SketchService().generate(calibration)):
        assert 0 <= x
        assert x + 4 * len(label) <= appConfig.overlayCanvasWidth
        assert 0 <= y
        assert y + 6 <= appConfig.overlayCanvasHeight


def testLabelsSitOnTheirOwnLineNotTheNeighbouringOne(sketch: str) -> None:
    """The label is centred in its line, which is what pairs the two.

    Floating labels above the line put "0 ft" exactly on the 1 ft line when
    rows were 7 apart, which is how the first real grid became ambiguous.
    """
    for entry in gridEntries(sketch):
        labelCentre = entry["labelY"] + 3
        assert abs(labelCentre - entry["row"]) <= 1, entry


def testOneFootLineIsDrawnHeavier() -> None:
    calibration = Calibration(
        frameWidth=640,
        frameHeight=480,
        points=[
            CalibrationPoint(0.0, 461),
            CalibrationPoint(1.0, 427),
            CalibrationPoint(4.0, 316),
        ],
    )

    entries = gridEntries(SketchService().generate(calibration))
    byLabel = {entry["label"]: entry["thickness"] for entry in entries}

    assert byLabel == {"0 ft": 1, "1 ft": 2, "4 ft": 1}


def testEmphasisFollowsTheConfiguredDistances(monkeypatch) -> None:
    monkeypatch.setattr(appConfig, "emphasisedDistancesFeet", (4.0,))
    calibration = Calibration(
        frameWidth=640,
        frameHeight=480,
        points=[CalibrationPoint(1.0, 427), CalibrationPoint(4.0, 316)],
    )

    entries = gridEntries(SketchService().generate(calibration))
    byLabel = {entry["label"]: entry["thickness"] for entry in entries}

    assert byLabel == {"1 ft": 1, "4 ft": 2}


def testLabelWidthMatchesTheTextSoTheBreakFits(sketch: str) -> None:
    for entry in gridEntries(sketch):
        assert entry["labelWidth"] == 4 * len(entry["label"])


def testSketchBreaksTheLineAroundTheLabel(sketch: str) -> None:
    assert "void drawBrokenLine" in sketch
    assert "LABEL_GAP" in sketch
    # The single full-width draw is gone.
    assert "tv.draw_line(0, GRID[i].row, W - 1" not in sketch


widthEntry = re.compile(r"\{\s*(\d+),\s*(\d+),\s*(\d+)\s*\}")


def widthRows(sketch: str) -> list[tuple[int, int, int]]:
    section = sketch.split("const WidthPoint WIDTH[] PROGMEM = {")[1].split("};")[0]
    return [
        (int(row), int(left), int(right))
        for row, left, right in widthEntry.findall(section)
    ]


def withWidth() -> Calibration:
    return Calibration(
        frameWidth=640,
        frameHeight=480,
        points=[
            CalibrationPoint(2.0, 388, leftEdge=60, rightEdge=580),
            CalibrationPoint(8.0, 193, leftEdge=180, rightEdge=460),
            CalibrationPoint(20.0, 23, leftEdge=250, rightEdge=390),
        ],
    )


def testWidthRowsRunTopOfCanvasDownwards() -> None:
    """Consecutive entries are joined, so they have to be in drawing order."""
    rows = widthRows(SketchService().generate(withWidth()))

    assert [row for row, _, _ in rows] == sorted(row for row, _, _ in rows)
    # 23, 193 and 388 of 480 onto the 96-row canvas.
    assert [row for row, _, _ in rows] == [5, 39, 78]


def testWidthColumnsAreRescaledOntoTheCanvas() -> None:
    rows = widthRows(SketchService().generate(withWidth()))

    # Entries run far to near, and the corridor narrows with distance: the far
    # end's left edge sits further right, its right edge further left.
    farLeft, farRight = rows[0][1], rows[0][2]
    nearLeft, nearRight = rows[-1][1], rows[-1][2]
    assert farLeft > nearLeft
    assert farRight < nearRight
    assert rows[-1] == (78, 13, 123)  # 60 and 580 of 640 onto 136


def testWidthEdgesAreDrawnDashed() -> None:
    sketch = SketchService().generate(withWidth())

    assert "DASH_LENGTH" in sketch
    assert "void drawDashedEdge" in sketch
    assert "tv.set_pixel" in sketch
    assert "drawWidthLines();" in sketch


def testPointsWithOnlyOneEdgeAreLeftOutOfTheCorridor() -> None:
    calibration = Calibration(
        frameWidth=640,
        frameHeight=480,
        points=[
            CalibrationPoint(2.0, 388, leftEdge=60, rightEdge=580),
            CalibrationPoint(8.0, 193, leftEdge=180),
            CalibrationPoint(20.0, 23, leftEdge=250, rightEdge=390),
        ],
    )

    assert [row for row, _, _ in widthRows(SketchService().generate(calibration))] == [
        5,
        78,
    ]


def testACalibrationWithoutWidthStillGeneratesACleanSketch(sketch: str) -> None:
    """Distances alone remain a complete, compilable grid."""
    assert "const uint8_t WIDTH_COUNT = 0;" in sketch
    assert "struct WidthPoint" not in sketch
    assert "void drawWidthLines()" in sketch
    assert sketch.count("{") == sketch.count("}")


def testGridRowsRecordTheFrameEachWasMeasuredOn() -> None:
    calibration = Calibration(
        frameWidth=640,
        frameHeight=480,
        points=[CalibrationPoint(4.0, 316, frameIndex=2265)],
    )

    assert "frame 2265" in SketchService().generate(calibration)


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


def testSketchKeepsItsPathWhenTheFolderAlreadyMatches(tmp_path: Path) -> None:
    chosen = tmp_path / "rvbhGrid" / "rvbhGrid.ino"

    assert sketchFolderPath(chosen) == chosen


def testAMismatchedSketchNameGetsItsOwnFolder(tmp_path: Path) -> None:
    """Saving rvbhGridV2.ino into a rvbhGrid folder builds nothing.

    Worse, a second .ino beside an existing one is treated as another tab of
    the same sketch and collides with it.
    """
    chosen = tmp_path / "rvbhGrid" / "rvbhGridV2.ino"

    assert sketchFolderPath(chosen) == tmp_path / "rvbhGrid" / "rvbhGridV2" / "rvbhGridV2.ino"


def testTheDefaultPathIsAlreadyWellFormed() -> None:
    assert sketchFolderPath(defaultSketchPath()) == defaultSketchPath()
