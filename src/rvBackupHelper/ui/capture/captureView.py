"""Capture tab: pick a device, watch the live feed, record clips."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Signal
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
from rvBackupHelper.services.capture.captureWorker import CaptureWorker
from rvBackupHelper.services.capture.deviceScanWorker import DeviceScanWorker
from rvBackupHelper.services.capture.recordingService import buildClipPath
from rvBackupHelper.ui.widgets.videoDisplay import VideoDisplay

logger = logging.getLogger(__name__)


class CaptureView(QWidget):
    """Live preview plus recording controls."""

    statusMessage = Signal(str)
    # Payload is the Path of a clip that finished recording.
    clipRecorded = Signal(object)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.captureWorker: CaptureWorker | None = None
        self.scanWorker: DeviceScanWorker | None = None
        self.devices: list[CameraDevice] = []
        self.recordingPath: Path | None = None
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

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Device:"))
        controls.addWidget(self.deviceCombo)
        controls.addWidget(self.scanButton)
        controls.addStretch()
        controls.addWidget(self.captureButton)
        controls.addWidget(self.recordButton)

        self.videoDisplay = VideoDisplay()
        self.videoDisplay.clear("Scan for a device, then start capture")
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

    def selectedDeviceIndex(self) -> int | None:
        data = self.deviceCombo.currentData()
        return None if data is None else int(data)

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
        for device in devices:
            self.deviceCombo.addItem(device.displayName, device.index)
        if devices:
            self.statusMessage.emit(f"Found {len(devices)} capture device(s).")
            self.videoDisplay.clear("Ready - press Start Capture")
        else:
            self.statusMessage.emit("No capture devices found.")
            self.videoDisplay.clear("No capture devices found")

    def onScanFailed(self, message: str) -> None:
        self.statusMessage.emit(f"Device scan failed: {message}")

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
        deviceIndex = self.selectedDeviceIndex()
        if deviceIndex is None:
            self.statusMessage.emit("Pick a capture device first.")
            return

        settings = CaptureSettings(
            deviceIndex=deviceIndex,
            frameWidth=appConfig.defaultFrameWidth,
            frameHeight=appConfig.defaultFrameHeight,
            framesPerSecond=appConfig.defaultFramesPerSecond,
        )
        worker = CaptureWorker(settings, parent=self)
        worker.frameReady.connect(self.videoDisplay.showFrame)
        worker.captureStarted.connect(self.onCaptureStarted)
        worker.recordingStarted.connect(self.onRecordingStarted)
        worker.recordingStopped.connect(self.onRecordingStopped)
        worker.errorOccurred.connect(self.onCaptureError)
        worker.finished.connect(self.onCaptureFinished)

        self.captureWorker = worker
        worker.start()
        self.statusMessage.emit(f"Starting capture on device {deviceIndex}...")
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
        self.detailLabel.setText(
            f"Device {settings.deviceIndex} - "
            f"{settings.frameWidth}x{settings.frameHeight} @ "
            f"{settings.framesPerSecond:.0f} fps"
        )
        self.statusMessage.emit("Capturing.")

    def onCaptureError(self, message: str) -> None:
        logger.warning("Capture error: %s", message)
        self.statusMessage.emit(message)

    def onCaptureFinished(self) -> None:
        if self.captureWorker is not None:
            self.captureWorker.deleteLater()
            self.captureWorker = None
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
            worker.requestRecordingStart(buildClipPath())

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

    # --------------------------------------------------------- shutdown ---

    def shutdown(self) -> None:
        """Stop worker threads and block until they are done."""
        if self.captureWorker is not None:
            self.captureWorker.requestStop()
            self.captureWorker.wait(3000)
        if self.scanWorker is not None:
            self.scanWorker.wait(5000)
