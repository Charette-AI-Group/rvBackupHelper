"""Plain data types for capture devices, capture settings and recorded clips."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CameraDevice:
    """A capture device that answered a probe with a real frame."""

    index: int
    label: str
    frameWidth: int
    frameHeight: int

    @property
    def displayName(self) -> str:
        return f"{self.label} ({self.frameWidth}x{self.frameHeight})"


@dataclass(frozen=True)
class CaptureSettings:
    """What to ask the device for. The device may deliver something else."""

    deviceIndex: int = 0
    frameWidth: int = 640
    frameHeight: int = 480
    framesPerSecond: float = 30.0


@dataclass(frozen=True)
class ClipInfo:
    """Properties of a recorded clip, read once when the file is opened."""

    path: Path
    frameCount: int
    framesPerSecond: float
    frameWidth: int
    frameHeight: int

    @property
    def durationSeconds(self) -> float:
        if self.framesPerSecond <= 0:
            return 0.0
        return self.frameCount / self.framesPerSecond

    def timestampOf(self, frameIndex: int) -> float:
        """Seconds from the start of the clip to the given frame."""
        if self.framesPerSecond <= 0:
            return 0.0
        return frameIndex / self.framesPerSecond
