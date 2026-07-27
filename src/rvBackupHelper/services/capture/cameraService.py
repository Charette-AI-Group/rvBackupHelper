"""Capture device discovery and frame grabbing.

Free of Qt and of GUI state. The capture backend is injected, so every path in
here can be unit tested with no camera attached.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from typing import Any

import cv2
import numpy as np

from rvBackupHelper import appConfig
from rvBackupHelper.models.captureModels import CameraDevice, CaptureSettings

logger = logging.getLogger(__name__)

# (deviceIndex, backend) -> something shaped like cv2.VideoCapture
CaptureFactory = Callable[[int, int], Any]


class CameraError(RuntimeError):
    """A capture device could not be opened, configured or read."""


def preferredBackend() -> int:
    """Pick the capture backend for this platform.

    On Windows, DirectShow opens USB capture dongles far more reliably than the
    default Media Foundation backend, which frequently stalls on open or reports
    no frames at all for cheap grabbers.
    """
    if sys.platform == "win32":
        return cv2.CAP_DSHOW
    return cv2.CAP_ANY


def defaultCaptureFactory(deviceIndex: int, backend: int) -> Any:
    return cv2.VideoCapture(deviceIndex, backend)


class CameraService:
    """Opens one capture device at a time and reads frames from it."""

    def __init__(
        self,
        captureFactory: CaptureFactory | None = None,
        backend: int | None = None,
    ) -> None:
        self.captureFactory: CaptureFactory = captureFactory or defaultCaptureFactory
        self.backend = preferredBackend() if backend is None else backend
        self.capture: Any | None = None
        self.settings: CaptureSettings | None = None

    @property
    def isOpen(self) -> bool:
        return self.capture is not None

    def listDevices(self, maxIndex: int | None = None) -> list[CameraDevice]:
        """Probe device indices and return the ones that deliver a frame.

        Slow — each probe opens and closes a device — so callers should run this
        off the GUI thread.
        """
        limit = appConfig.maxDeviceProbeIndex if maxIndex is None else maxIndex
        devices: list[CameraDevice] = []
        for index in range(limit):
            device = self.probeDevice(index)
            if device is not None:
                devices.append(device)
        logger.info("Device probe found %d device(s)", len(devices))
        return devices

    def probeDevice(self, index: int) -> CameraDevice | None:
        """Open one index and read a frame from it. None if that fails."""
        capture = self.captureFactory(index, self.backend)
        try:
            if not capture.isOpened():
                return None
            ok, frame = capture.read()
            if not ok or frame is None:
                logger.debug("Device %d opened but delivered no frame", index)
                return None
            height, width = frame.shape[:2]
            return CameraDevice(
                index=index,
                label=f"Camera {index}",
                frameWidth=width,
                frameHeight=height,
            )
        finally:
            capture.release()

    def open(self, settings: CaptureSettings) -> CaptureSettings:
        """Open a device and return the settings actually in effect."""
        self.close()
        capture = self.captureFactory(settings.deviceIndex, self.backend)
        if not capture.isOpened():
            capture.release()
            raise CameraError(f"Could not open capture device {settings.deviceIndex}.")

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, settings.frameWidth)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.frameHeight)
        capture.set(cv2.CAP_PROP_FPS, settings.framesPerSecond)

        self.capture = capture
        self.settings = self.readBackSettings(settings)
        logger.info("Opened device %d as %s", settings.deviceIndex, self.settings)
        return self.settings

    def readBackSettings(self, requested: CaptureSettings) -> CaptureSettings:
        """Devices substitute their own format silently — record what we got."""
        if self.capture is None:
            return requested
        width = int(self.capture.get(cv2.CAP_PROP_FRAME_WIDTH)) or requested.frameWidth
        height = int(self.capture.get(cv2.CAP_PROP_FRAME_HEIGHT)) or requested.frameHeight
        fps = float(self.capture.get(cv2.CAP_PROP_FPS)) or requested.framesPerSecond
        return CaptureSettings(
            deviceIndex=requested.deviceIndex,
            frameWidth=width,
            frameHeight=height,
            framesPerSecond=fps,
        )

    def readFrame(self) -> np.ndarray:
        """Read one BGR frame. Raises CameraError when the device gives up."""
        if self.capture is None:
            raise CameraError("No capture device is open.")
        ok, frame = self.capture.read()
        if not ok or frame is None:
            raise CameraError("The capture device stopped delivering frames.")
        return frame

    def close(self) -> None:
        if self.capture is None:
            return
        try:
            self.capture.release()
        finally:
            self.capture = None
            self.settings = None
            logger.info("Capture device closed")
