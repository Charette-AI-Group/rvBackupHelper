"""Tests for the calibration data types."""

from __future__ import annotations

from rvBackupHelper.models.calibrationModels import (
    Calibration,
    CalibrationPoint,
    Edge,
)


def makeCalibration(**overrides) -> Calibration:
    values = {"frameWidth": 640, "frameHeight": 480}
    values.update(overrides)
    return Calibration(**values)


def testPointsSortNearToFar() -> None:
    calibration = makeCalibration()
    for distance, scanLine in ((10.0, 300), (3.0, 420), (6.0, 360)):
        calibration.addPoint(CalibrationPoint(distance, scanLine))

    assert [p.distanceFeet for p in calibration.sortedPoints] == [3.0, 6.0, 10.0]


def testLabelDropsAPointlessDecimalButKeepsARealOne() -> None:
    assert CalibrationPoint(3.0, 420).label == "3 ft"
    assert CalibrationPoint(2.5, 440).label == "2.5 ft"


def testReMarkingADistanceReplacesTheEarlierPoint() -> None:
    """Correcting a misplaced line must not leave two lines for one distance."""
    calibration = makeCalibration()
    calibration.addPoint(CalibrationPoint(3.0, 420))

    calibration.addPoint(CalibrationPoint(3.0, 415))

    assert len(calibration.points) == 1
    assert calibration.points[0].scanLine == 415


def testRemoveDistanceReportsWhetherItRemovedAnything() -> None:
    calibration = makeCalibration()
    calibration.addPoint(CalibrationPoint(3.0, 420))

    assert calibration.removeDistance(3.0)
    assert not calibration.removeDistance(3.0)
    assert calibration.isEmpty


def testOverlayRowRescalesOntoTheShieldCanvas() -> None:
    """A 480-tall capture has to become a row in the 96-tall OSD buffer."""
    calibration = makeCalibration(frameHeight=480)

    assert calibration.overlayRow(0, overlayHeight=96) == 0
    assert calibration.overlayRow(240, overlayHeight=96) == 48
    assert calibration.overlayRow(420, overlayHeight=96) == 84


def testOverlayRowStaysInsideTheCanvas() -> None:
    calibration = makeCalibration(frameHeight=480)

    # The last scan line must not land one row past the buffer.
    assert calibration.overlayRow(480, overlayHeight=96) == 95
    assert calibration.overlayRow(9999, overlayHeight=96) == 95
    assert calibration.overlayRow(-10, overlayHeight=96) == 0


def testOverlayRowIsSafeBeforeAClipIsOpen() -> None:
    assert Calibration().overlayRow(100) == 0


def testMarkersAreOrderedAndLabelled() -> None:
    calibration = makeCalibration()
    calibration.addPoint(CalibrationPoint(6.0, 360))
    calibration.addPoint(CalibrationPoint(3.0, 420))

    assert calibration.markers() == [(420, "3 ft"), (360, "6 ft")]


def testAPointHasNoWidthUntilBothEdgesAreMarked() -> None:
    calibration = makeCalibration()
    calibration.addPoint(CalibrationPoint(4.0, 316))

    assert not calibration.points[0].hasWidth

    assert calibration.setEdge(4.0, Edge.left, 120, frameIndex=2265)
    assert not calibration.points[0].hasWidth  # one edge draws nothing

    assert calibration.setEdge(4.0, Edge.right, 520, frameIndex=2265)
    assert calibration.points[0].hasWidth
    assert calibration.widthPoints == calibration.points


def testEdgesRecordTheFrameTheyWereMarkedOn() -> None:
    """The pole moves between distances, so frames are per point."""
    calibration = makeCalibration()
    calibration.addPoint(CalibrationPoint(4.0, 316, frameIndex=2265))

    calibration.setEdge(4.0, Edge.left, 120, frameIndex=2270)

    assert calibration.points[0].frameIndex == 2270
    assert calibration.points[0].scanLine == 316


def testMarkingAnEdgeWithoutItsDistanceIsRefused() -> None:
    calibration = makeCalibration()

    assert not calibration.setEdge(4.0, Edge.left, 120, frameIndex=1)
    assert calibration.isEmpty


def testReMarkingAnEdgeReplacesIt() -> None:
    calibration = makeCalibration()
    calibration.addPoint(CalibrationPoint(4.0, 316))
    calibration.setEdge(4.0, Edge.left, 120, frameIndex=1)

    calibration.setEdge(4.0, Edge.left, 130, frameIndex=1)

    assert calibration.points[0].leftEdge == 130


def testOverlayColumnRescalesOntoTheCanvasWidth() -> None:
    calibration = makeCalibration(frameWidth=640)

    assert calibration.overlayColumn(0, overlayWidth=136) == 0
    assert calibration.overlayColumn(320, overlayWidth=136) == 68
    assert calibration.overlayColumn(640, overlayWidth=136) == 135
    assert calibration.overlayColumn(-5, overlayWidth=136) == 0


def testEdgeMarkersReportEveryMarkedSide() -> None:
    calibration = makeCalibration()
    calibration.addPoint(CalibrationPoint(4.0, 316))
    calibration.addPoint(CalibrationPoint(8.0, 193))
    calibration.setEdge(4.0, Edge.left, 120, frameIndex=1)
    calibration.setEdge(4.0, Edge.right, 520, frameIndex=1)
    calibration.setEdge(8.0, Edge.left, 200, frameIndex=2)

    assert calibration.edgeMarkers() == [(120, 316), (520, 316), (200, 193)]


def testWidthDoesNotDisturbNearToFarOrdering() -> None:
    calibration = makeCalibration()
    calibration.addPoint(CalibrationPoint(8.0, 193))
    calibration.addPoint(CalibrationPoint(4.0, 316))
    calibration.setEdge(8.0, Edge.left, 200, frameIndex=1)

    assert [p.distanceFeet for p in calibration.sortedPoints] == [4.0, 8.0]


def testClearEmptiesThePoints() -> None:
    calibration = makeCalibration()
    calibration.addPoint(CalibrationPoint(3.0, 420))

    calibration.clear()

    assert calibration.isEmpty
    assert calibration.markers() == []
