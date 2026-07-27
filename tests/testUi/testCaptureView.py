"""Tests for the capture view's control state and device handling."""

from __future__ import annotations

from rvBackupHelper.models.captureModels import CameraDevice
from rvBackupHelper.ui.capture.captureView import CaptureView

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
        "USB Video (640x480, no signal)",
    ]


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


def testSignalLossUpdatesThePreviewPlaceholder(qtbot) -> None:
    view = CaptureView()
    qtbot.addWidget(view)
    messages: list[str] = []
    view.statusMessage.connect(messages.append)

    view.onSignalStateChanged(False)

    assert not view.videoDisplay.hasFrame
    assert "Waiting for a video signal" in messages[-1]

    view.onSignalStateChanged(True)
    assert "acquired" in messages[-1]
