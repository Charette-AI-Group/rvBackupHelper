"""Frame-accurate reading of recorded clips.

Calibration works by finding one frame and measuring distances on it, so a
request for frame N has to land on frame N and not somewhere nearby.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from rvBackupHelper.models.captureModels import ClipInfo

logger = logging.getLogger(__name__)

# path -> something shaped like cv2.VideoCapture
ClipCaptureFactory = Callable[[str], Any]


class ClipError(RuntimeError):
    """A clip could not be opened or read."""


def defaultClipCaptureFactory(path: str) -> Any:
    return cv2.VideoCapture(path)


class ClipReaderService:
    """Random-access reader over a recorded clip."""

    def __init__(self, captureFactory: ClipCaptureFactory | None = None) -> None:
        self.captureFactory: ClipCaptureFactory = captureFactory or defaultClipCaptureFactory
        self.capture: Any | None = None
        self.clipInfo: ClipInfo | None = None
        self.nextFrameIndex = 0

    @property
    def isOpen(self) -> bool:
        return self.capture is not None

    def open(self, path: Path) -> ClipInfo:
        self.close()
        if not path.exists():
            raise ClipError(f"Clip not found: {path}")
        capture = self.captureFactory(str(path))
        if not capture.isOpened():
            capture.release()
            raise ClipError(f"Could not open clip: {path}")

        self.capture = capture
        self.clipInfo = self.readClipInfo(path)
        self.nextFrameIndex = 0
        logger.info("Opened clip %s (%d frames)", path, self.clipInfo.frameCount)
        return self.clipInfo

    def readClipInfo(self, path: Path) -> ClipInfo:
        assert self.capture is not None
        return ClipInfo(
            path=path,
            frameCount=max(int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT)), 0),
            framesPerSecond=float(self.capture.get(cv2.CAP_PROP_FPS)),
            frameWidth=int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)),
            frameHeight=int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )

    def readFrameAt(self, frameIndex: int) -> np.ndarray:
        """Read one frame by absolute index.

        A request for the next frame in sequence reads straight through;
        anything else seeks first. Seeking is the slow and codec-sensitive path,
        so the common case of stepping forward one frame avoids it.
        """
        if self.capture is None or self.clipInfo is None:
            raise ClipError("No clip is open.")
        self.assertFrameInRange(frameIndex)

        if frameIndex != self.nextFrameIndex:
            self.capture.set(cv2.CAP_PROP_POS_FRAMES, frameIndex)
        ok, frame = self.capture.read()
        if not ok or frame is None:
            # Position is now unknown; force a seek on the next read.
            self.nextFrameIndex = -1
            raise ClipError(f"Could not read frame {frameIndex}.")

        self.nextFrameIndex = frameIndex + 1
        return frame

    def assertFrameInRange(self, frameIndex: int) -> None:
        assert self.clipInfo is not None
        if frameIndex < 0:
            raise ClipError(f"Frame index {frameIndex} is negative.")
        # A frame count of 0 means the container did not report one; allow the
        # read and let the decoder decide.
        if self.clipInfo.frameCount and frameIndex >= self.clipInfo.frameCount:
            raise ClipError(
                f"Frame {frameIndex} is past the end of the clip "
                f"({self.clipInfo.frameCount} frames)."
            )

    def close(self) -> None:
        if self.capture is None:
            return
        try:
            self.capture.release()
        finally:
            self.capture = None
            self.clipInfo = None
            self.nextFrameIndex = 0
