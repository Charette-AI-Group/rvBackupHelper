"""Capture device discovery and frame grabbing.

Free of Qt and of GUI state. The capture backend and the name provider are both
injected, so every path in here can be unit tested with no camera attached.
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
# () -> friendly device names, in enumeration order
NameProvider = Callable[[], list[str]]


class CameraError(RuntimeError):
    """A capture device could not be opened, configured or read."""


def backendPriority() -> list[tuple[str, int]]:
    """Backends to try when probing, best first.

    DirectShow leads on Windows purely on speed — it opens a webcam in well
    under a second where Media Foundation has been measured taking eleven.
    But DirectShow flatly refuses to open a capture dongle with no input
    signal, which is the state a grabber is in whenever the camera is
    unplugged or unpowered, so Media Foundation follows as the fallback that
    can open those. probeDevice() tries both and prefers whichever actually
    delivers frames, so leading with the fast one costs nothing.
    """
    if sys.platform == "win32":
        return [("DirectShow", cv2.CAP_DSHOW), ("MSMF", cv2.CAP_MSMF)]
    return [("default", cv2.CAP_ANY)]


def defaultCaptureFactory(deviceIndex: int, backend: int) -> Any:
    return cv2.VideoCapture(deviceIndex, backend)


def deviceNames() -> list[str]:
    """Friendly device names in enumeration order, or [] if unavailable.

    Read through DirectShow, which *enumerates* every video device — including
    ones it cannot itself open — so a signal-less grabber still gets its real
    name. The order matches the index OpenCV uses.
    """
    if sys.platform != "win32":
        return []
    try:
        from pygrabber.dshow_graph import FilterGraph

        return list(FilterGraph().get_input_devices())
    except Exception:
        logger.debug("Friendly device names unavailable", exc_info=True)
        return []


class CameraService:
    """Opens one capture device at a time and reads frames from it."""

    def __init__(
        self,
        captureFactory: CaptureFactory | None = None,
        backends: list[tuple[str, int]] | None = None,
        nameProvider: NameProvider | None = None,
    ) -> None:
        self.captureFactory: CaptureFactory = captureFactory or defaultCaptureFactory
        self.backends = list(backends) if backends is not None else backendPriority()
        self.nameProvider: NameProvider = nameProvider or deviceNames
        self.capture: Any | None = None
        self.settings: CaptureSettings | None = None

    @property
    def isOpen(self) -> bool:
        return self.capture is not None

    @property
    def defaultBackend(self) -> int:
        return self.backends[0][1] if self.backends else cv2.CAP_ANY

    # -------------------------------------------------------- discovery ---

    def listDevices(self, maxIndex: int | None = None) -> list[CameraDevice]:
        """Probe device indices and return every one a backend could open.

        Slow — each probe opens and closes a device, and a device with no
        signal only reveals that by failing to deliver a frame — so callers
        must run this off the GUI thread.
        """
        names = self.nameProvider()
        limit = len(names) if names else appConfig.maxDeviceProbeIndex
        if maxIndex is not None:
            limit = min(limit, maxIndex) if names else maxIndex

        devices: list[CameraDevice] = []
        for index in range(limit):
            label = names[index] if index < len(names) else f"Camera {index}"
            device = self.probeDevice(index, label)
            if device is None:
                logger.debug("No backend could open device %d (%s)", index, label)
                continue
            devices.append(device)
        logger.info("Device probe found %d usable device(s)", len(devices))
        return devices

    def probeDevice(self, index: int, label: str | None = None) -> CameraDevice | None:
        """Try each backend for one index; prefer one that delivers frames.

        A device that opens but sends nothing is still returned (flagged
        hasSignal=False) when no backend does better — that is a real device
        waiting for video, not an absent one.
        """
        deviceLabel = label or f"Camera {index}"
        withoutSignal: CameraDevice | None = None
        for backendName, backendId in self.backends:
            device = self.probeBackend(index, deviceLabel, backendName, backendId)
            if device is None:
                continue
            if device.hasSignal:
                return device
            withoutSignal = withoutSignal or device
        return withoutSignal

    def probeBackend(
        self, index: int, label: str, backendName: str, backendId: int
    ) -> CameraDevice | None:
        capture = self.captureFactory(index, backendId)
        try:
            if not capture.isOpened():
                return None
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            ok, frame = capture.read()
            hasSignal = bool(ok and frame is not None)
            if hasSignal:
                height, width = frame.shape[:2]
            return CameraDevice(
                index=index,
                label=label,
                frameWidth=width,
                frameHeight=height,
                backend=backendId,
                backendName=backendName,
                hasSignal=hasSignal,
            )
        finally:
            capture.release()

    # ------------------------------------------------------------ capture --

    def open(self, settings: CaptureSettings) -> CaptureSettings:
        """Open a device and return the settings actually in effect."""
        self.close()
        backend = settings.backend if settings.backend is not None else self.defaultBackend
        capture = self.captureFactory(settings.deviceIndex, backend)
        if not capture.isOpened():
            capture.release()
            raise CameraError(f"Could not open capture device {settings.deviceIndex}.")

        capture.set(cv2.CAP_PROP_FRAME_WIDTH, settings.frameWidth)
        capture.set(cv2.CAP_PROP_FRAME_HEIGHT, settings.frameHeight)
        capture.set(cv2.CAP_PROP_FPS, settings.framesPerSecond)

        self.capture = capture
        self.settings = self.readBackSettings(settings, backend)
        logger.info("Opened device %d as %s", settings.deviceIndex, self.settings)
        return self.settings

    def readBackSettings(self, requested: CaptureSettings, backend: int) -> CaptureSettings:
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
            backend=backend,
        )

    def readFrame(self) -> np.ndarray | None:
        """Read one BGR frame, or None when the device delivered nothing.

        None is not fatal: a grabber with no input signal returns it forever,
        and starts returning frames the moment the camera comes to life. The
        caller decides how long to wait.
        """
        if self.capture is None:
            raise CameraError("No capture device is open.")
        ok, frame = self.capture.read()
        if not ok or frame is None:
            return None
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
