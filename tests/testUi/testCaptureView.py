"""Tests for the capture view's control state and device handling."""

from __future__ import annotations

from PySide6.QtCore import QObject, Qt, Signal

from rvBackupHelper.models.captureModels import CameraDevice
from rvBackupHelper.ui.capture.captureView import (
    CaptureView,
    gridOffText,
    gridOnText,
    startupHint,
)


class FakeScanWorker(QObject):
    """Stands in for DeviceScanWorker so tests never touch real hardware."""

    devicesFound = Signal(object)
    errorOccurred = Signal(str)
    finished = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.startCalled = False

    def start(self) -> None:
        self.startCalled = True

liveDevice = CameraDevice(
    index=0,
    label="HD Pro Webcam C920",
    frameWidth=640,
    frameHeight=480,
    backend=700,
    backendName="DirectShow",
    hasSignal=True,
)
signallessDevice = CameraDevice(
    index=1,
    label="USB Video",
    frameWidth=640,
    frameHeight=480,
    backend=1400,
    backendName="MSMF",
    hasSignal=False,
)


def testControlsStartDisabledWithNoDevices(qtbot) -> None:
    view = CaptureView()
    qtbot.addWidget(view)

    assert not view.captureButton.isEnabled()
    assert not view.recordButton.isEnabled()


def testFindingDevicesEnablesCaptureImmediately(qtbot) -> None:
    """Populating the list must enable the controls on its own."""
    view = CaptureView()
    qtbot.addWidget(view)

    view.onDevicesFound([liveDevice, signallessDevice])

    assert view.deviceCombo.count() == 2
    assert view.deviceCombo.isEnabled()
    assert view.captureButton.isEnabled()
    # Recording still needs a running capture.
    assert not view.recordButton.isEnabled()


def testDeviceListShowsNamesAndSignalState(qtbot) -> None:
    view = CaptureView()
    qtbot.addWidget(view)

    view.onDevicesFound([liveDevice, signallessDevice])

    labels = [view.deviceCombo.itemText(i) for i in range(view.deviceCombo.count())]
    assert labels == [
        "HD Pro Webcam C920 (640x480)",
        "USB Video (640x480, no video)",
    ]


def testSignallessDeviceCarriesAnExplanatoryTooltip(qtbot) -> None:
    """A device holding no video could be idle or held by another app."""
    view = CaptureView()
    qtbot.addWidget(view)

    view.onDevicesFound([liveDevice, signallessDevice])

    liveTip = view.deviceCombo.itemData(0, Qt.ItemDataRole.ToolTipRole)
    signallessTip = view.deviceCombo.itemData(1, Qt.ItemDataRole.ToolTipRole)

    assert liveTip == ""
    assert "another application" in signallessTip


def testSelectedDeviceCarriesItsBackend(qtbot) -> None:
    """The chosen device must keep the backend the probe found working."""
    view = CaptureView()
    qtbot.addWidget(view)
    view.onDevicesFound([liveDevice, signallessDevice])

    view.deviceCombo.setCurrentIndex(1)
    selected = view.selectedDevice()

    assert selected == signallessDevice
    assert selected.backend == 1400


def testEmptyScanResultLeavesCaptureDisabled(qtbot) -> None:
    view = CaptureView()
    qtbot.addWidget(view)
    view.onDevicesFound([liveDevice])

    view.onDevicesFound([])

    assert view.deviceCombo.count() == 0
    assert not view.captureButton.isEnabled()
    assert view.selectedDevice() is None


class FakeCaptureWorker:
    """Captures the path a recording request would have used."""

    def __init__(self) -> None:
        self.requestedPath = None

    def requestRecordingStart(self, path) -> None:
        self.requestedPath = path


def testRecordingsGoToTheConfiguredFolder(qtbot, tmp_path) -> None:
    view = CaptureView()
    qtbot.addWidget(view)
    view.setRecordingsDir(tmp_path)
    worker = FakeCaptureWorker()
    view.captureWorker = worker

    view.onRecordClicked()

    assert worker.requestedPath is not None
    assert worker.requestedPath.parent == tmp_path


def testStartsWithAHintTellingTheUserWhereToBegin(qtbot) -> None:
    view = CaptureView()
    qtbot.addWidget(view)

    assert view.videoDisplay.hintText == startupHint


def testPressingScanClearsTheHintForGood(qtbot, monkeypatch) -> None:
    monkeypatch.setattr(
        "rvBackupHelper.ui.capture.captureView.DeviceScanWorker", FakeScanWorker
    )
    view = CaptureView()
    qtbot.addWidget(view)

    view.onScanClicked()

    assert view.scanWorker.startCalled
    assert view.videoDisplay.hintText == ""

    # Later placeholder changes must not bring it back.
    view.onDevicesFound([liveDevice])
    assert view.videoDisplay.hintText == ""


def testGridToggleSitsWithTheRecordingControls(qtbot) -> None:
    """It belongs where recording happens, not where measuring happens."""
    view = CaptureView()
    qtbot.addWidget(view)

    assert view.gridToggle.isChecked()
    # Labelled with the state: a checked button is highlighted, and an action
    # label would then read as though the action were already in effect.
    assert view.gridToggle.text() == gridOnText
    # Usable before any device is found: you blank the grid, then record.
    assert view.gridToggle.isEnabled()


def testGridToggleReportsWhatTheBoardActuallySaid(qtbot) -> None:
    """The button follows the board's reply, not what was assumed."""
    view = CaptureView()
    qtbot.addWidget(view)
    messages: list[str] = []
    view.statusMessage.connect(messages.append)

    view.onGridReply(False, "grid off")

    assert not view.gridToggle.isChecked()
    assert view.gridToggle.text() == gridOffText
    assert "grid off" in messages[-1]


def testAFailedGridCommandPutsTheButtonBack(qtbot) -> None:
    """The board did not do as asked, so the button must not claim it did."""
    view = CaptureView()
    qtbot.addWidget(view)
    messages: list[str] = []
    view.statusMessage.connect(messages.append)
    view.gridToggle.setChecked(False)

    view.onGridFailed("No Arduino found.")

    assert view.gridToggle.isChecked()
    assert view.gridToggle.text() == gridOnText
    assert "No Arduino found." in messages[-1]


def testGridToggleIsIndependentOfCaptureState(qtbot) -> None:
    """Blanking the overlay must not need a capture running first."""
    view = CaptureView()
    qtbot.addWidget(view)

    view.updateControls()

    assert not view.recordButton.isEnabled()
    assert view.gridToggle.isEnabled()


def testSignalLossUpdatesThePreviewPlaceholder(qtbot) -> None:
    view = CaptureView()
    qtbot.addWidget(view)
    messages: list[str] = []
    view.statusMessage.connect(messages.append)

    view.onSignalStateChanged(False)

    assert not view.videoDisplay.hasFrame
    assert "device in use" in view.videoDisplay.placeholderText
    # Both causes named, so nobody hunts a dead camera that is merely busy.
    assert "powered" in messages[-1]
    assert "other application" in messages[-1]

    view.onSignalStateChanged(True)
    assert "Video arriving" in messages[-1]
