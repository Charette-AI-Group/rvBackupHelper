"""Writing captured frames to a video file.

Kept separate from CameraService so recording can be started and stopped
without disturbing the live preview.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from rvBackupHelper import appConfig

logger = logging.getLogger(__name__)

# (path, fourcc, fps, (width, height)) -> something shaped like cv2.VideoWriter
WriterFactory = Callable[[str, int, float, tuple[int, int]], Any]


class RecordingError(RuntimeError):
    """A recording could not be started or written to."""


def defaultWriterFactory(path: str, fourcc: int, fps: float, size: tuple[int, int]) -> Any:
    return cv2.VideoWriter(path, fourcc, fps, size)


def buildClipPath(directory: Path | None = None, when: datetime | None = None) -> Path:
    """Timestamped clip path, so recordings sort chronologically by name."""
    targetDir = appConfig.recordingsDir if directory is None else directory
    stamp = (when or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return targetDir / f"rvbh-{stamp}{appConfig.recordingExtension}"


class RecordingService:
    """Writes BGR frames to a video file."""

    def __init__(self, writerFactory: WriterFactory | None = None) -> None:
        self.writerFactory: WriterFactory = writerFactory or defaultWriterFactory
        self.writer: Any | None = None
        self.path: Path | None = None
        self.frameCount = 0

    @property
    def isRecording(self) -> bool:
        return self.writer is not None

    def start(
        self,
        path: Path,
        frameWidth: int,
        frameHeight: int,
        framesPerSecond: float,
    ) -> Path:
        if self.isRecording:
            raise RecordingError("A recording is already in progress.")
        if framesPerSecond <= 0:
            raise RecordingError(f"Invalid frame rate for recording: {framesPerSecond}")

        path.parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter.fourcc(*appConfig.recordingFourcc)
        writer = self.writerFactory(str(path), fourcc, framesPerSecond, (frameWidth, frameHeight))
        if not writer.isOpened():
            writer.release()
            raise RecordingError(f"Could not open a video writer for {path}")

        self.writer = writer
        self.path = path
        self.frameCount = 0
        logger.info("Recording to %s at %.1f fps", path, framesPerSecond)
        return path

    def writeFrame(self, frame: np.ndarray) -> None:
        if self.writer is None:
            raise RecordingError("No recording is in progress.")
        self.writer.write(frame)
        self.frameCount += 1

    def stop(self) -> tuple[Path, int] | None:
        """Close the file. Returns (path, frameCount), or None if idle."""
        if self.writer is None:
            return None
        path = self.path
        frameCount = self.frameCount
        try:
            self.writer.release()
        finally:
            self.writer = None
            self.path = None
        assert path is not None
        logger.info("Recording stopped: %s (%d frames)", path, frameCount)
        return path, frameCount
