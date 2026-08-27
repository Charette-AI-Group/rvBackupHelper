"""Capture tab: pick a device, watch the live feed, record clips."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rvBackupHelper import appConfig
from rvBackupHelper.models.captureModels import CameraDevice, CaptureSettings
from rvBackupHelper.services.board.gridWorker import GridWorker
from rvBackupHelper.services.capture.captureWorker import CaptureWorker
from rvBackupHelper.services.capture.deviceScanWorker import DeviceScanWorker
from rvBackupHelper.services.capture.recordingService import buildClipPath
from rvBackupHelper.ui.dialogs.errorDialog import headlineOf
from rvBackupHelper.ui.widgets.videoDisplay import VideoDisplay

logger = logging.getLogger(__name__)

# Shown once on the empty preview so a first-time user knows where to start.
# Cleared for good the moment Scan Devices is pressed.
startupHint = "Press Scan Devices to start"

# State, not action: see the comment where the toggle is built.
gridOnText = "Arduino Grid: On"
gridOffText = "Arduino Grid: Off"


class CaptureView(QWidget):
    """Live preview plus recording controls."""

    statusMessage = Signal(str)
    # Failures, as (title, whole message). The status bar cannot hold them.
    errorMessage = Signal(str, str)
    # Payload is the Path of a clip that finished recording.
    clipRecorded = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.captureWorker: CaptureWorker | None = None
        self.scanWorker: DeviceScanWorker | None = None
        self.gridWorker: GridWorker | None = None
        self.devices: list[CameraDevice] = []
        self.activeDevice: CameraDevice | None = None
        self.recordingPath: Path | None = None
        self.recordingsDir = appConfig.recordingsDir
        self.buildUi()
        self.updateControls()

    def buildUi(self) -> None:
        self.deviceCombo = QComboBox()
        self.deviceCombo.setMinimumWidth(220)

        self.scanButton = QPushButton("Scan Devices")
        self.scanButton.clicked.connect(self.onScanClicked)

        self.captureButton = QPushButton("Start Capture")
        self.captureButton.clicked.connect(self.onCaptureClicked)

        self.recordButton = QPushButton("Start Recording")
        self.recordButton.clicked.connect(self.onRecordClicked)

        # Sits with the recording controls because that is when it matters: a
        # grid burned into a calibration clip covers the markings you need to
        # click later.
        # Labelled with the state, not the action. A checked button is drawn
        # highlighted, and "Hide Grid" highlighted reads as though hiding were
        # already in effect - the opposite of what it means.
        # Starts off. The board keeps the real state in EEPROM and nothing has
        # asked it yet - opening the port to ask would reset the board, which
        # is not a thing to do to a running overlay at startup. So the button
        # cannot know, and of the two guesses this is the one that does not
        # claim the grid is up when the picture is clean. It corrects itself
        # on the first toggle, which reports what the board actually said.
        self.gridToggle = QPushButton(gridOffText)
        self.gridToggle.setCheckable(True)
        self.gridToggle.setChecked(False)
        self.gridToggle.setToolTip(
            "Blanks the overlay so the camera passes through clean. Needs the "
            "generated grid sketch flashed; takes a moment because opening the "
            "port resets the board."
        )
        self.gridToggle.clicked.connect(self.onGridToggleClicked)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Device:"))
        controls.addWidget(self.deviceCombo)
        controls.addWidget(self.scanButton)
        controls.addStretch()
        controls.addWidget(self.captureButton)
        controls.addWidget(self.recordButton)
        controls.addWidget(self.gridToggle)

        self.videoDisplay = VideoDisplay()
        self.videoDisplay.clear("No video")
        self.videoDisplay.setHint(startupHint)
        self.detailLabel = QLabel("Idle")

        layout = QVBoxLayout(self)
        layout.addLayout(controls)
        layout.addWidget(self.videoDisplay, stretch=1)
        layout.addWidget(self.detailLabel)

    # ------------------------------------------------------------- state --

    @property
    def isCapturing(self) -> bool:
        return self.captureWorker is not None

    @property
    def isRecording(self) -> bool:
        return self.recordingPath is not None

    def selectedDevice(self) -> CameraDevice | None:
        return self.deviceCombo.currentData()

    def setRecordingsDir(self, path: Path) -> None:
        """Where the next clip is written. Takes effect on the next recording."""
        self.recordingsDir = path

    def updateControls(self) -> None:
        hasDevice = self.deviceCombo.count() > 0
        capturing = self.isCapturing
        self.deviceCombo.setEnabled(hasDevice and not capturing)
        self.scanButton.setEnabled(not capturing and self.scanWorker is None)
        self.captureButton.setEnabled(hasDevice or capturing)
        self.captureButton.setText("Stop Capture" if capturing else "Start Capture")
        self.recordButton.setEnabled(capturing)
        self.recordButton.setText(
            "Stop Recording" if self.isRecording else "Start Recording"
        )

    # ------------------------------------------------------ device scan ---

    def onScanClicked(self) -> None:
        if self.scanWorker is not None:
            return
        # The hint has served its purpose the moment the user acts on it.
        self.videoDisplay.clearHint()
        self.statusMessage.emit("Scanning for capture devices...")
        self.scanWorker = DeviceScanWorker(parent=self)
        self.scanWorker.devicesFound.connect(self.onDevicesFound)
        self.scanWorker.errorOccurred.connect(self.onScanFailed)
        self.scanWorker.finished.connect(self.onScanFinished)
        self.scanWorker.start()
        self.updateControls()

    def onDevicesFound(self, devices: list[CameraDevice]) -> None:
        self.devices = devices
        self.deviceCombo.clear()
        for position, device in enumerate(devices):
            self.deviceCombo.addItem(device.displayName, device)
            # The short "no video" label cannot say why; the tooltip can.
            self.deviceCombo.setItemData(
                position, device.statusDetail, Qt.ItemDataRole.ToolTipRole
            )
        if devices:
            self.statusMessage.emit(f"Found {len(devices)} capture device(s).")
            self.videoDisplay.clear("Ready - press Start Capture")
        else:
            self.statusMessage.emit("No capture devices found.")
            self.videoDisplay.clear("No capture devices found")
        # The controls key off the device list, so refresh them here rather
        # than relying on the scan's finished signal arriving afterwards.
        self.updateControls()

    def onScanFailed(self, message: str) -> None:
        self.reportError("Device scan failed", message)

    def onScanFinished(self) -> None:
        if self.scanWorker is not None:
            self.scanWorker.deleteLater()
            self.scanWorker = None
        self.updateControls()

    # ---------------------------------------------------------- capture ---

    def onCaptureClicked(self) -> None:
        if self.isCapturing:
            self.stopCapture()
        else:
            self.startCapture()

    def startCapture(self) -> None:
        device = self.selectedDevice()
        if device is None:
            self.statusMessage.emit("Pick a capture device first.")
            return

        settings = CaptureSettings(
            deviceIndex=device.index,
            frameWidth=appConfig.defaultFrameWidth,
            frameHeight=appConfig.defaultFrameHeight,
            framesPerSecond=appConfig.defaultFramesPerSecond,
            # Open on the backend the probe found working for this device.
            backend=device.backend,
        )
        worker = CaptureWorker(settings, parent=self)
        worker.frameReady.connect(self.videoDisplay.showFrame)
        worker.captureStarted.connect(self.onCaptureStarted)
        worker.signalStateChanged.connect(self.onSignalStateChanged)
        worker.recordingStarted.connect(self.onRecordingStarted)
        worker.recordingStopped.connect(self.onRecordingStopped)
        worker.errorOccurred.connect(self.onCaptureError)
        worker.finished.connect(self.onCaptureFinished)

        self.activeDevice = device
        self.captureWorker = worker
        worker.start()
        self.statusMessage.emit(f"Starting capture on {device.label}...")
        self.updateControls()

    def stopCapture(self) -> None:
        """Ask the worker to stop; cleanup happens in onCaptureFinished."""
        if self.captureWorker is None:
            return
        self.captureWorker.requestStop()
        self.captureButton.setEnabled(False)
        self.recordButton.setEnabled(False)
        self.statusMessage.emit("Stopping capture...")

    def onCaptureStarted(self, settings: CaptureSettings) -> None:
        device = self.activeDevice
        name = device.label if device is not None else f"Device {settings.deviceIndex}"
        backend = f" via {device.backendName}" if device is not None else ""
        self.detailLabel.setText(
            f"{name}{backend} - "
            f"{settings.frameWidth}x{settings.frameHeight} @ "
            f"{settings.framesPerSecond:.0f} fps"
        )
        self.statusMessage.emit("Capturing.")

    def onSignalStateChanged(self, hasSignal: bool) -> None:
        if hasSignal:
            self.statusMessage.emit("Video arriving.")
            return
        self.videoDisplay.clear("Waiting for video - no signal, or device in use")
        self.statusMessage.emit(
            "No frames yet - check the camera is connected and powered, and that "
            "no other application (such as OBS) is using the device."
        )

    def reportError(self, title: str, message: str) -> None:
        """A headline on the bar, the whole thing in a dialog.

        The bar elides, and what it elides is the end of the message - which
        is where a failure keeps the part worth acting on.
        """
        self.statusMessage.emit(headlineOf(message))
        self.errorMessage.emit(title, message)

    def onCaptureError(self, message: str) -> None:
        self.reportError("Capture failed", message)

    def onCaptureFinished(self) -> None:
        if self.captureWorker is not None:
            self.captureWorker.deleteLater()
            self.captureWorker = None
        self.activeDevice = None
        self.recordingPath = None
        self.detailLabel.setText("Idle")
        self.videoDisplay.clear("Capture stopped")
        self.updateControls()

    # -------------------------------------------------------- recording ---

    def onRecordClicked(self) -> None:
        worker = self.captureWorker
        if worker is None:
            return
        if self.isRecording:
            worker.requestRecordingStop()
        else:
            worker.requestRecordingStart(buildClipPath(self.recordingsDir))

    def onRecordingStarted(self, path: Path) -> None:
        self.recordingPath = path
        self.statusMessage.emit(f"Recording to {path.name}")
        self.updateControls()

    def onRecordingStopped(self, path: Path, frameCount: int) -> None:
        self.recordingPath = None
        self.updateControls()
        # Announce the clip first: whoever loads it will post its own status,
        # and the save confirmation should be what the user is left looking at.
        self.clipRecorded.emit(path)
        self.statusMessage.emit(f"Saved {path.name} ({frameCount} frames)")

    # -------------------------------------------------------- the board ---

    def onGridToggleClicked(self) -> None:
        if self.gridWorker is not None:
            return
        wanted = self.gridToggle.isChecked()
        self.gridToggle.setEnabled(False)
        self.statusMessage.emit(
            f"Asking the Arduino to {'show' if wanted else 'hide'} the grid..."
        )
        worker = GridWorker(wanted, parent=self)
        worker.finishedWithReply.connect(self.onGridReply)
        worker.errorOccurred.connect(self.onGridFailed)
        worker.finished.connect(self.onGridFinished)
        self.gridWorker = worker
        worker.start()

    def onGridReply(self, visible: bool, reply: str) -> None:
        self.gridToggle.setChecked(visible)
        self.updateGridToggleText()
        self.statusMessage.emit(f"Arduino says: {reply}")

    def onGridFailed(self, message: str) -> None:
        # Put the button back where it was: the board did not do as asked.
        self.gridToggle.setChecked(not self.gridToggle.isChecked())
        self.updateGridToggleText()
        self.reportError("Arduino", message)

    def onGridFinished(self) -> None:
        if self.gridWorker is not None:
            self.gridWorker.deleteLater()
            self.gridWorker = None
        self.gridToggle.setEnabled(True)

    def updateGridToggleText(self) -> None:
        self.gridToggle.setText(
            gridOnText if self.gridToggle.isChecked() else gridOffText
        )

    # --------------------------------------------------------- shutdown ---

    def shutdown(self) -> None:
        """Stop worker threads and block until they are done."""
        if self.captureWorker is not None:
            self.captureWorker.requestStop()
            self.captureWorker.wait(3000)
        if self.scanWorker is not None:
            self.scanWorker.wait(5000)
        if self.gridWorker is not None:
            self.gridWorker.wait(5000)
