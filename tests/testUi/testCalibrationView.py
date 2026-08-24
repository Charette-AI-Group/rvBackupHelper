"""Tests for the calibration panel's editing and file handling."""

from __future__ import annotations

import re
from pathlib import Path

import cv2
import numpy as np
import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QFileDialog

from rvBackupHelper import appConfig
from rvBackupHelper.services.settingsService import SettingsService
from rvBackupHelper.ui.calibration.calibrationView import CalibrationView

frameWidth = 640
frameHeight = 480


def writeClip(path: Path, frameCount: int = 4, width: int = frameWidth) -> Path:
    fourcc = cv2.VideoWriter.fourcc(*appConfig.recordingFourcc)
    writer = cv2.VideoWriter(str(path), fourcc, 30.0, (width, frameHeight))
    assert writer.isOpened()
    try:
        for index in range(frameCount):
            writer.write(
                np.full((frameHeight, width, 3), 40 + index * 20, dtype=np.uint8)
            )
    finally:
        writer.release()
    return path


@pytest.fixture
def settingsService(tmp_path: Path) -> SettingsService:
    """Isolated settings: the view now stores the last sketch it generated,
    and tests must not write that into the real user preferences."""
    return SettingsService(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )


@pytest.fixture
def view(qtbot, settingsService: SettingsService) -> CalibrationView:
    calibrationView = CalibrationView(settingsService=settingsService)
    qtbot.addWidget(calibrationView)
    return calibrationView


@pytest.fixture
def viewWithClip(view: CalibrationView, tmp_path: Path) -> CalibrationView:
    view.clipBrowser.openClip(writeClip(tmp_path / "clip.avi"))
    return view


def testStartsEmptyWithSavingDisabled(view: CalibrationView) -> None:
    assert view.calibration.isEmpty
    assert not view.saveButton.isEnabled()
    assert not view.clearButton.isEnabled()
    assert view.pointsTable.rowCount() == 0


def testOpeningAClipAdoptsItsGeometry(viewWithClip: CalibrationView) -> None:
    assert viewWithClip.calibration.frameWidth == frameWidth
    assert viewWithClip.calibration.frameHeight == frameHeight
    assert viewWithClip.calibration.sourceClip == "clip.avi"


def testClickingTheFrameRecordsTheScanLineAtTheChosenDistance(
    viewWithClip: CalibrationView,
) -> None:
    viewWithClip.distanceSpin.setValue(6.0)

    viewWithClip.onFramePointClicked(320, 360)

    assert len(viewWithClip.calibration.points) == 1
    point = viewWithClip.calibration.points[0]
    assert point.distanceFeet == 6.0
    assert point.scanLine == 360
    assert viewWithClip.saveButton.isEnabled()


def testMarkingRecordsWhichFrameItWasMeasuredOn(
    viewWithClip: CalibrationView,
) -> None:
    viewWithClip.clipBrowser.showFrame(2)

    viewWithClip.onFramePointClicked(100, 300)

    assert viewWithClip.calibration.frameIndex == 2


def testBumperLineAtZeroFeetCanBeEntered(viewWithClip: CalibrationView) -> None:
    """The first real calibration wanted a line on the bumper itself."""
    viewWithClip.distanceSpin.setValue(0.0)

    viewWithClip.onFramePointClicked(320, 461)

    assert viewWithClip.calibration.points[0].distanceFeet == 0.0
    assert viewWithClip.calibration.points[0].label == "0 ft"


def testClickingWithoutAClipIsRefused(view: CalibrationView) -> None:
    messages: list[str] = []
    view.statusMessage.connect(messages.append)

    view.onFramePointClicked(100, 200)

    assert view.calibration.isEmpty
    assert "Open a clip" in messages[-1]


def testTableAndMarkersFollowThePoints(viewWithClip: CalibrationView) -> None:
    viewWithClip.distanceSpin.setValue(6.0)
    viewWithClip.onFramePointClicked(320, 360)
    viewWithClip.distanceSpin.setValue(3.0)
    viewWithClip.onFramePointClicked(320, 420)

    # Nearest first, in both the table and the drawn guides.
    assert viewWithClip.pointsTable.rowCount() == 2
    assert viewWithClip.pointsTable.item(0, 0).text() == "3 ft"
    assert viewWithClip.pointsTable.item(0, 1).text() == "420"
    assert viewWithClip.pointsTable.item(0, 2).text() == "84"
    assert viewWithClip.clipBrowser.videoDisplay.markers == [
        (420, "3 ft"),
        (360, "6 ft"),
    ]


def testRemovingTheSelectedRow(viewWithClip: CalibrationView) -> None:
    viewWithClip.distanceSpin.setValue(3.0)
    viewWithClip.onFramePointClicked(320, 420)
    viewWithClip.distanceSpin.setValue(6.0)
    viewWithClip.onFramePointClicked(320, 360)
    viewWithClip.pointsTable.selectRow(0)

    viewWithClip.onRemoveClicked()

    assert [p.distanceFeet for p in viewWithClip.calibration.points] == [6.0]


def testClearAllEmptiesEverything(viewWithClip: CalibrationView) -> None:
    viewWithClip.onFramePointClicked(320, 420)

    viewWithClip.onClearClicked()

    assert viewWithClip.calibration.isEmpty
    assert viewWithClip.pointsTable.rowCount() == 0
    assert viewWithClip.clipBrowser.videoDisplay.markers == []


def testOpeningADifferentlySizedClipDiscardsPoints(
    viewWithClip: CalibrationView, tmp_path: Path
) -> None:
    """Scan lines from another frame size would quietly mean other distances."""
    viewWithClip.onFramePointClicked(320, 420)
    messages: list[str] = []
    viewWithClip.statusMessage.connect(messages.append)

    viewWithClip.clipBrowser.openClip(writeClip(tmp_path / "wide.avi", width=800))

    assert viewWithClip.calibration.isEmpty
    assert viewWithClip.calibration.frameWidth == 800
    assert any("different frame size" in message for message in messages)


def testReopeningTheSameSizedClipKeepsPoints(
    viewWithClip: CalibrationView, tmp_path: Path
) -> None:
    viewWithClip.onFramePointClicked(320, 420)

    viewWithClip.clipBrowser.openClip(writeClip(tmp_path / "second.avi"))

    assert len(viewWithClip.calibration.points) == 1


def testSaveThenLoadRestoresThePoints(
    viewWithClip: CalibrationView, tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "saved.json"
    viewWithClip.distanceSpin.setValue(3.0)
    viewWithClip.onFramePointClicked(320, 420)
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *args: (str(target), ""))
    )
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *args: (str(target), ""))
    )

    viewWithClip.onSaveClicked()
    viewWithClip.onClearClicked()
    assert viewWithClip.calibration.isEmpty

    viewWithClip.onLoadClicked()

    assert [p.scanLine for p in viewWithClip.calibration.points] == [420]
    assert viewWithClip.pointsTable.rowCount() == 1
    assert viewWithClip.clipBrowser.videoDisplay.markers == [(420, "3 ft")]


def testSavingNothingIsRefused(view: CalibrationView, monkeypatch) -> None:
    messages: list[str] = []
    view.statusMessage.connect(messages.append)
    called: list[bool] = []
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args: called.append(True) or ("", "")),
    )

    view.onSaveClicked()

    assert not called
    assert "Nothing to save" in messages[-1]


def testSketchButtonNeedsPoints(view: CalibrationView) -> None:
    assert not view.sketchButton.isEnabled()


def testGeneratingASketchWritesACompilableFile(
    viewWithClip: CalibrationView, tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "rvbhGrid" / "rvbhGrid.ino"
    viewWithClip.distanceSpin.setValue(3.0)
    viewWithClip.onFramePointClicked(320, 430)
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *args: (str(target), ""))
    )

    assert viewWithClip.sketchButton.isEnabled()
    viewWithClip.onGenerateSketchClicked()

    sketch = target.read_text(encoding="utf-8")
    assert "#include <TVout.h>" in sketch
    # The row, and its label in flash, without pinning the struct's layout.
    assert re.search(r"\{\s*86,", sketch)
    assert 'PROGMEM = "3 ft";' in sketch
    assert "clip.avi" in sketch


def testCollidingRowsAreWarnedAboutBeforeGenerating(
    viewWithClip: CalibrationView,
) -> None:
    """Two distances on one OSD row cannot be drawn apart; say so up front."""
    viewWithClip.distanceSpin.setValue(3.0)
    viewWithClip.onFramePointClicked(320, 430)
    viewWithClip.distanceSpin.setValue(4.0)
    viewWithClip.onFramePointClicked(320, 428)

    assert "share an OSD row" in viewWithClip.summaryLabel.text()


def testNoCollisionWarningWhenRowsAreDistinct(viewWithClip: CalibrationView) -> None:
    viewWithClip.distanceSpin.setValue(3.0)
    viewWithClip.onFramePointClicked(320, 430)
    viewWithClip.distanceSpin.setValue(6.0)
    viewWithClip.onFramePointClicked(320, 372)

    assert "share an OSD row" not in viewWithClip.summaryLabel.text()


def testLoadingABrokenFileReportsItAndKeepsState(
    viewWithClip: CalibrationView, tmp_path: Path, monkeypatch
) -> None:
    viewWithClip.onFramePointClicked(320, 420)
    broken = tmp_path / "broken.json"
    broken.write_text("{not json", encoding="utf-8")
    messages: list[str] = []
    viewWithClip.statusMessage.connect(messages.append)
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName", staticmethod(lambda *args: (str(broken), ""))
    )

    viewWithClip.onLoadClicked()

    assert len(viewWithClip.calibration.points) == 1
    assert "not valid JSON" in messages[-1]


def makeSketch(folder: Path) -> Path:
    """A sketch laid out the way the Arduino tools require."""
    folder.mkdir(parents=True, exist_ok=True)
    sketch = folder / f"{folder.name}.ino"
    sketch.write_text("void setup(){}", encoding="utf-8")
    return sketch


def viewSharing(qtbot, settingsFile: Path) -> CalibrationView:
    """A view backed by a named settings file, so two can share one."""
    service = SettingsService(
        QSettings(str(settingsFile), QSettings.Format.IniFormat)
    )
    calibrationView = CalibrationView(settingsService=service)
    qtbot.addWidget(calibrationView)
    return calibrationView


def testUploadIsOfferedForTheLastSketchAfterARestart(qtbot, tmp_path: Path) -> None:
    """A sketch saved under its own name must still be offered next launch."""
    settingsFile = tmp_path / "settings.ini"
    sketch = makeSketch(tmp_path / "rvbhGridV2")
    first = viewSharing(qtbot, settingsFile)
    first.settingsService.setLastSketchPath(sketch)

    # A fresh view, as after restarting, sharing only the stored settings.
    reopened = viewSharing(qtbot, settingsFile)

    assert reopened.uploadTarget() == sketch
    assert reopened.uploadButton.isEnabled()
    assert "rvbhGridV2" in reopened.uploadButton.toolTip()


def testThisSessionsSketchWinsOverTheRememberedOne(
    view: CalibrationView, tmp_path: Path
) -> None:
    view.settingsService.setLastSketchPath(makeSketch(tmp_path / "rvbhGridV1"))
    justGenerated = makeSketch(tmp_path / "rvbhGridV3")

    view.sketchPath = justGenerated

    assert view.uploadTarget() == justGenerated


def testARememberedSketchThatIsGoneIsNotOffered(
    view: CalibrationView, tmp_path: Path
) -> None:
    """It may have been renamed or deleted since it was generated."""
    view.settingsService.setLastSketchPath(tmp_path / "vanished" / "vanished.ino")

    view.updateControls()

    assert not view.uploadButton.isEnabled()
    assert "Generate a sketch first" in view.uploadButton.toolTip()


def testGeneratingRemembersThePathForNextTime(
    viewWithClip: CalibrationView, tmp_path: Path, monkeypatch
) -> None:
    target = tmp_path / "rvbhGridV9" / "rvbhGridV9.ino"
    viewWithClip.onFramePointClicked(320, 430)
    monkeypatch.setattr(
        QFileDialog, "getSaveFileName", staticmethod(lambda *args: (str(target), ""))
    )

    viewWithClip.onGenerateSketchClicked()

    assert viewWithClip.settingsService.lastSketchPath() == target
