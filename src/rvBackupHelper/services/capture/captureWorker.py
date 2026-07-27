"""Background thread owning the live capture loop.

The GUI thread never touches the camera. It starts and stops this worker and
receives frames by signal. Recording is toggled by leaving a request that the
loop picks up between frames, so the video writer is only ever touched from
this thread.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QMutex, QMutexLocker, QThread, Signal

from rvBackupHelper.models.captureModels import CaptureSettings
from rvBackupHelper.services.capture.cameraService import CameraError, CameraService
from rvBackupHelper.services.capture.recordingService import (
    RecordingError,
    RecordingService,
)

logger = logging.getLogger(__name__)


class CaptureWorker(QThread):
    """Grabs frames until asked to stop, recording them when asked to."""

    # Payload is a BGR numpy frame; Qt has no type for it, so it stays `object`.
    frameReady = Signal(object)
    # Payload is the CaptureSettings the device actually granted.
    captureStarted = Signal(object)
    # Payload is the clip Path.
    recordingStarted = Signal(object)
    # Payload is the clip Path and the number of frames written.
    recordingStopped = Signal(object, int)
    errorOccurred = Signal(str)

    def __init__(
        self,
        settings: CaptureSettings,
        cameraService: CameraService | None = None,
        recordingService: RecordingService | None = None,
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings
        self.cameraService = cameraService or CameraService()
        self.recordingService = recordingService or RecordingService()
        self.mutex = QMutex()
        self.stopRequested = False
        self.recordPathRequest: Path | None = None
        self.stopRecordingRequested = False

    # ------------------------------------------------ called from the GUI --

    def requestStop(self) -> None:
        with QMutexLocker(self.mutex):
            self.stopRequested = True

    def requestRecordingStart(self, path: Path) -> None:
        with QMutexLocker(self.mutex):
            self.recordPathRequest = path
            self.stopRecordingRequested = False

    def requestRecordingStop(self) -> None:
        with QMutexLocker(self.mutex):
            self.recordPathRequest = None
            self.stopRecordingRequested = True

    # ------------------------------------------------ the worker thread ----

    def run(self) -> None:
        try:
            effectiveSettings = self.cameraService.open(self.settings)
        except CameraError as exc:
            logger.exception("Capture could not start")
            self.errorOccurred.emit(str(exc))
            return

        self.captureStarted.emit(effectiveSettings)
        try:
            self.captureLoop(effectiveSettings)
        finally:
            self.finishRecording()
            self.cameraService.close()

    def captureLoop(self, effectiveSettings: CaptureSettings) -> None:
        while not self.isStopRequested():
            try:
                frame = self.cameraService.readFrame()
            except CameraError as exc:
                logger.warning("Capture loop ended: %s", exc)
                self.errorOccurred.emit(str(exc))
                return
            self.serviceRecordingRequests(effectiveSettings)
            if self.recordingService.isRecording:
                self.recordingService.writeFrame(frame)
            self.frameReady.emit(frame)

    def isStopRequested(self) -> bool:
        with QMutexLocker(self.mutex):
            return self.stopRequested

    def takeRecordingRequests(self) -> tuple[Path | None, bool]:
        """Consume any pending recording request. Clears it in the same lock."""
        with QMutexLocker(self.mutex):
            path = self.recordPathRequest
            stopRequested = self.stopRecordingRequested
            self.recordPathRequest = None
            self.stopRecordingRequested = False
        return path, stopRequested

    def serviceRecordingRequests(self, effectiveSettings: CaptureSettings) -> None:
        path, stopRequested = self.takeRecordingRequests()
        if stopRequested:
            self.finishRecording()
        if path is None:
            return
        try:
            self.recordingService.start(
                path,
                effectiveSettings.frameWidth,
                effectiveSettings.frameHeight,
                effectiveSettings.framesPerSecond,
            )
        except RecordingError as exc:
            logger.exception("Recording could not start")
            self.errorOccurred.emit(str(exc))
            return
        self.recordingStarted.emit(path)

    def finishRecording(self) -> None:
        result = self.recordingService.stop()
        if result is None:
            return
        path, frameCount = result
        self.recordingStopped.emit(path, frameCount)
