"""Tests for ClipReaderService.

These write real clips and read them back: frame-accurate seeking is the whole
point of the service, and only a real decoder can prove it.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from rvBackupHelper import appConfig
from rvBackupHelper.services.review.clipReaderService import (
    ClipError,
    ClipReaderService,
)

frameWidth = 320
frameHeight = 240
# Distinct enough to survive MJPG compression and identify a frame by its mean.
frameValues = [20, 60, 100, 140, 180, 220]
# MJPG is lossy; the mean of a flat frame drifts by a couple of levels.
meanTolerance = 8.0


def writeClip(path: Path, values: list[int], fps: float = 30.0) -> Path:
    fourcc = cv2.VideoWriter.fourcc(*appConfig.recordingFourcc)
    writer = cv2.VideoWriter(str(path), fourcc, fps, (frameWidth, frameHeight))
    assert writer.isOpened(), "test clip writer failed to open"
    try:
        for value in values:
            writer.write(np.full((frameHeight, frameWidth, 3), value, dtype=np.uint8))
    finally:
        writer.release()
    return path


@pytest.fixture
def clipPath(tmp_path: Path) -> Path:
    return writeClip(tmp_path / f"clip{appConfig.recordingExtension}", frameValues)


def assertFrameIs(frame: np.ndarray, expectedValue: int) -> None:
    assert abs(float(frame.mean()) - expectedValue) < meanTolerance, (
        f"expected a frame near {expectedValue}, got mean {frame.mean():.1f}"
    )


def testOpenReportsClipProperties(clipPath: Path) -> None:
    reader = ClipReaderService()
    try:
        info = reader.open(clipPath)

        assert info.path == clipPath
        assert info.frameCount == len(frameValues)
        assert (info.frameWidth, info.frameHeight) == (frameWidth, frameHeight)
        assert info.framesPerSecond == pytest.approx(30.0, abs=0.5)
        assert info.durationSeconds == pytest.approx(len(frameValues) / 30.0, abs=0.05)
    finally:
        reader.close()


def testOpenMissingFileRaises(tmp_path: Path) -> None:
    reader = ClipReaderService()

    with pytest.raises(ClipError, match="Clip not found"):
        reader.open(tmp_path / "nope.avi")


def testSequentialReadsReturnConsecutiveFrames(clipPath: Path) -> None:
    reader = ClipReaderService()
    try:
        reader.open(clipPath)
        for index, expected in enumerate(frameValues):
            assertFrameIs(reader.readFrameAt(index), expected)
            assert reader.nextFrameIndex == index + 1
    finally:
        reader.close()


def testRandomAccessLandsOnTheRequestedFrame(clipPath: Path) -> None:
    reader = ClipReaderService()
    try:
        reader.open(clipPath)
        # Jump around, including backwards, which is what scrubbing does.
        for index in (4, 1, 5, 0, 3, 2):
            assertFrameIs(reader.readFrameAt(index), frameValues[index])
    finally:
        reader.close()


def testSteppingBackOneFrameWorks(clipPath: Path) -> None:
    reader = ClipReaderService()
    try:
        reader.open(clipPath)
        reader.readFrameAt(3)
        assertFrameIs(reader.readFrameAt(2), frameValues[2])
    finally:
        reader.close()


def testReadPastTheEndRaises(clipPath: Path) -> None:
    reader = ClipReaderService()
    try:
        reader.open(clipPath)
        with pytest.raises(ClipError, match="past the end"):
            reader.readFrameAt(len(frameValues))
    finally:
        reader.close()


def testNegativeFrameIndexRaises(clipPath: Path) -> None:
    reader = ClipReaderService()
    try:
        reader.open(clipPath)
        with pytest.raises(ClipError, match="negative"):
            reader.readFrameAt(-1)
    finally:
        reader.close()


def testReadWithoutOpenRaises() -> None:
    reader = ClipReaderService()

    with pytest.raises(ClipError, match="No clip is open"):
        reader.readFrameAt(0)


def testReopeningADifferentClipResetsPosition(tmp_path: Path, clipPath: Path) -> None:
    otherValues = [200, 40]
    otherPath = writeClip(tmp_path / f"other{appConfig.recordingExtension}", otherValues)
    reader = ClipReaderService()
    try:
        reader.open(clipPath)
        reader.readFrameAt(4)

        info = reader.open(otherPath)

        assert info.frameCount == len(otherValues)
        assert reader.nextFrameIndex == 0
        assertFrameIs(reader.readFrameAt(0), otherValues[0])
    finally:
        reader.close()


def testCloseIsSafeToCallTwice(clipPath: Path) -> None:
    reader = ClipReaderService()
    reader.open(clipPath)
    reader.close()
    reader.close()
    assert not reader.isOpen
