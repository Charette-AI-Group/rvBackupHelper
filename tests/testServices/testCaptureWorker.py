"""Tests for the capture worker thread.

Exercises the real QThread with fake services: the threading and the
start/stop/record handshakes are the parts most likely to break.
"""

from __future__ import annotations

import time
from pathlib import Path

import numpy as np

from rvBackupHelper.models.captureModels import CaptureSettings
from rvBackupHelper.services.capture.cameraService import CameraError
from rvBackupHelper.services.capture.captureWorker import CaptureWorker
from rvBackupHelper.services.capture.recordingService import RecordingService

signalTimeout = 5000
grantedSettings = CaptureSettings(
    deviceIndex=0, frameWidth=320, frameHeight=240, framesPerSecond=30.0
)


class FakeCameraService:
    """Delivers frames forever, slowly enough not to flood the signal queue."""

    def __init__(self, framePeriod: float = 0.005) -> None:
        self.framePeriod = framePeriod
        self.opened = False
        self.closed = False
        self.readCount = 0

    def open(self, settings: CaptureSettings) -> CaptureSettings:
        self.opened = True
        return grantedSettings

    def readFrame(self) -> np.ndarray:
        time.sleep(self.framePeriod)
        self.readCount += 1
        return np.full((240, 320, 3), 128, dtype=np.uint8)

    def close(self) -> None:
        self.closed = True


class FailingCameraService(FakeCameraService):
    def open(self, settings: CaptureSettings) -> CaptureSettings:
        raise CameraError("device 0 is not available")


class FakeWriter:
    def __init__(self) -> None:
        self.frames: list[np.ndarray] = []
        self.released = False

    def isOpened(self) -> bool:
        return True

    def write(self, frame: np.ndarray) -> None:
        self.frames.append(frame)

    def release(self) -> None:
        self.released = True


def makeWorker(camera: FakeCameraService, writer: FakeWriter | None = None) -> CaptureWorker:
    recording = RecordingService(writerFactory=lambda *args: writer or FakeWriter())
    return CaptureWorker(
        CaptureSettings(deviceIndex=0),
        cameraService=camera,
        recordingService=recording,
    )


def testWorkerDeliversFramesThenStopsAndClosesTheCamera(qtbot) -> None:
    camera = FakeCameraService()
    worker = makeWorker(camera)

    with qtbot.waitSignal(worker.captureStarted, timeout=signalTimeout) as started:
        worker.start()
    assert started.args[0] == grantedSettings

    with qtbot.waitSignal(worker.frameReady, timeout=signalTimeout) as frame:
        pass
    assert frame.args[0].shape == (240, 320, 3)

    with qtbot.waitSignal(worker.finished, timeout=signalTimeout):
        worker.requestStop()

    assert camera.opened
    assert camera.closed
    assert camera.readCount > 0


def testWorkerReportsAFailureToOpenAndDoesNotStart(qtbot) -> None:
    worker = makeWorker(FailingCameraService())

    with qtbot.waitSignal(worker.errorOccurred, timeout=signalTimeout) as error:
        worker.start()

    assert "not available" in error.args[0]
    worker.wait(signalTimeout)


def testRecordingStartsAndStopsWhileCapturing(qtbot, tmp_path: Path) -> None:
    camera = FakeCameraService()
    writer = FakeWriter()
    worker = makeWorker(camera, writer)
    clipPath = tmp_path / "clip.avi"

    with qtbot.waitSignal(worker.captureStarted, timeout=signalTimeout):
        worker.start()

    with qtbot.waitSignal(worker.recordingStarted, timeout=signalTimeout) as startedRecording:
        worker.requestRecordingStart(clipPath)
    assert startedRecording.args[0] == clipPath

    with qtbot.waitSignal(worker.recordingStopped, timeout=signalTimeout) as stoppedRecording:
        worker.requestRecordingStop()

    assert stoppedRecording.args[0] == clipPath
    assert stoppedRecording.args[1] > 0
    assert len(writer.frames) == stoppedRecording.args[1]
    assert writer.released

    with qtbot.waitSignal(worker.finished, timeout=signalTimeout):
        worker.requestStop()


def testStoppingCaptureWhileRecordingClosesTheClip(qtbot, tmp_path: Path) -> None:
    camera = FakeCameraService()
    writer = FakeWriter()
    worker = makeWorker(camera, writer)

    with qtbot.waitSignal(worker.captureStarted, timeout=signalTimeout):
        worker.start()
    with qtbot.waitSignal(worker.recordingStarted, timeout=signalTimeout):
        worker.requestRecordingStart(tmp_path / "clip.avi")

    # Stopping capture outright must still flush and close the recording.
    with qtbot.waitSignal(worker.recordingStopped, timeout=signalTimeout):
        worker.requestStop()

    worker.wait(signalTimeout)
    assert writer.released
    assert camera.closed
