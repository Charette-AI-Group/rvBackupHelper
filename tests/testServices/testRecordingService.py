"""Tests for RecordingService — error handling with a fake writer, plus one
real round trip through OpenCV to prove the configured codec actually works."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pytest

from rvBackupHelper import appConfig
from rvBackupHelper.services.capture.recordingService import (
    RecordingError,
    RecordingService,
    buildClipPath,
)


def makeFrame(width: int = 320, height: int = 240, value: int = 128) -> np.ndarray:
    return np.full((height, width, 3), value, dtype=np.uint8)


class FakeWriter:
    def __init__(self, opened: bool = True) -> None:
        self.opened = opened
        self.frames: list[np.ndarray] = []
        self.released = False

    def isOpened(self) -> bool:
        return self.opened

    def write(self, frame: np.ndarray) -> None:
        self.frames.append(frame)

    def release(self) -> None:
        self.released = True


def factoryFor(writer: FakeWriter):
    def factory(path: str, fourcc: int, fps: float, size: tuple[int, int]) -> FakeWriter:
        writer.requestedPath = path
        writer.requestedFps = fps
        writer.requestedSize = size
        return writer

    return factory


def testBuildClipPathIsTimestampedAndUsesConfiguredExtension() -> None:
    path = buildClipPath(Path("W:/clips"), when=datetime(2026, 7, 27, 14, 30, 5))

    assert path.name == f"rvbh-20260727-143005{appConfig.recordingExtension}"
    assert path.parent == Path("W:/clips")


def testStartCountsFramesAndStopReportsThem(tmp_path: Path) -> None:
    writer = FakeWriter()
    service = RecordingService(writerFactory=factoryFor(writer))
    clipPath = tmp_path / "clip.avi"

    service.start(clipPath, 320, 240, 30.0)
    assert service.isRecording
    for _ in range(3):
        service.writeFrame(makeFrame())

    result = service.stop()

    assert result == (clipPath, 3)
    assert not service.isRecording
    assert writer.released
    assert len(writer.frames) == 3
    assert writer.requestedSize == (320, 240)


def testStartTwiceRaises(tmp_path: Path) -> None:
    service = RecordingService(writerFactory=factoryFor(FakeWriter()))
    service.start(tmp_path / "clip.avi", 320, 240, 30.0)

    with pytest.raises(RecordingError, match="already in progress"):
        service.start(tmp_path / "other.avi", 320, 240, 30.0)


def testStartRejectsAnImpossibleFrameRate(tmp_path: Path) -> None:
    service = RecordingService(writerFactory=factoryFor(FakeWriter()))

    with pytest.raises(RecordingError, match="Invalid frame rate"):
        service.start(tmp_path / "clip.avi", 320, 240, 0.0)


def testStartRaisesWhenTheWriterWillNotOpen(tmp_path: Path) -> None:
    writer = FakeWriter(opened=False)
    service = RecordingService(writerFactory=factoryFor(writer))

    with pytest.raises(RecordingError, match="Could not open a video writer"):
        service.start(tmp_path / "clip.avi", 320, 240, 30.0)

    assert not service.isRecording
    assert writer.released


def testWriteFrameWithoutStartRaises() -> None:
    service = RecordingService(writerFactory=factoryFor(FakeWriter()))

    with pytest.raises(RecordingError, match="No recording is in progress"):
        service.writeFrame(makeFrame())


def testStopWhileIdleReturnsNone() -> None:
    service = RecordingService(writerFactory=factoryFor(FakeWriter()))
    assert service.stop() is None


def testStartCreatesMissingParentDirectories(tmp_path: Path) -> None:
    service = RecordingService(writerFactory=factoryFor(FakeWriter()))
    clipPath = tmp_path / "nested" / "deeper" / "clip.avi"

    service.start(clipPath, 320, 240, 30.0)

    assert clipPath.parent.is_dir()


def testRealRecordingProducesAReadableClip(tmp_path: Path) -> None:
    """The configured fourcc/extension must actually round trip through OpenCV."""
    service = RecordingService()
    clipPath = tmp_path / f"clip{appConfig.recordingExtension}"

    service.start(clipPath, 320, 240, 30.0)
    for value in (20, 90, 160):
        service.writeFrame(makeFrame(value=value))
    result = service.stop()

    assert result == (clipPath, 3)
    assert clipPath.exists() and clipPath.stat().st_size > 0

    capture = cv2.VideoCapture(str(clipPath))
    try:
        assert capture.isOpened()
        assert int(capture.get(cv2.CAP_PROP_FRAME_COUNT)) == 3
        ok, frame = capture.read()
        assert ok
        assert frame.shape == (240, 320, 3)
    finally:
        capture.release()
