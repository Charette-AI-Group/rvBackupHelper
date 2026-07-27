"""Unit tests for CameraService, using a fake capture backend."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from rvBackupHelper.models.captureModels import CaptureSettings
from rvBackupHelper.services.capture.cameraService import CameraError, CameraService


def makeFrame(width: int = 640, height: int = 480, value: int = 128) -> np.ndarray:
    return np.full((height, width, 3), value, dtype=np.uint8)


class FakeCapture:
    """Stands in for cv2.VideoCapture.

    `fixedProperties` models a device that ignores requested formats and
    delivers its own — exactly what cheap USB grabbers do.
    """

    def __init__(
        self,
        frames: list[np.ndarray] | None = None,
        opened: bool = True,
        fixedProperties: dict[int, float] | None = None,
    ) -> None:
        self.frames = list(frames or [])
        self.opened = opened
        self.fixedProperties = dict(fixedProperties or {})
        self.properties: dict[int, float] = {}
        self.readCount = 0
        self.released = False

    def isOpened(self) -> bool:
        return self.opened

    def read(self):
        if self.readCount >= len(self.frames):
            return False, None
        frame = self.frames[self.readCount]
        self.readCount += 1
        return True, frame

    def set(self, prop: int, value: float) -> bool:
        if prop in self.fixedProperties:
            return False
        self.properties[prop] = value
        return True

    def get(self, prop: int) -> float:
        if prop in self.fixedProperties:
            return self.fixedProperties[prop]
        return self.properties.get(prop, 0.0)

    def release(self) -> None:
        self.released = True


def factoryFor(captures: dict[int, FakeCapture]):
    """Capture factory serving a prepared FakeCapture per device index."""

    def factory(deviceIndex: int, backend: int) -> FakeCapture:
        return captures.get(deviceIndex, FakeCapture(opened=False))

    return factory


def testListDevicesKeepsOnlyDevicesThatDeliverAFrame() -> None:
    captures = {
        0: FakeCapture(frames=[makeFrame(640, 480)]),
        1: FakeCapture(opened=False),
        2: FakeCapture(frames=[]),  # opens, but never yields a frame
        3: FakeCapture(frames=[makeFrame(720, 576)]),
    }
    service = CameraService(captureFactory=factoryFor(captures), backend=0)

    devices = service.listDevices(maxIndex=4)

    assert [device.index for device in devices] == [0, 3]
    assert devices[0].frameWidth == 640
    assert devices[0].frameHeight == 480
    assert devices[1].frameWidth == 720
    assert "720x576" in devices[1].displayName


def testListDevicesReleasesEveryProbedDevice() -> None:
    captures = {0: FakeCapture(frames=[makeFrame()]), 1: FakeCapture(opened=False)}
    service = CameraService(captureFactory=factoryFor(captures), backend=0)

    service.listDevices(maxIndex=2)

    assert captures[0].released
    assert captures[1].released


def testOpenRaisesWhenDeviceWillNotOpen() -> None:
    captures = {0: FakeCapture(opened=False)}
    service = CameraService(captureFactory=factoryFor(captures), backend=0)

    with pytest.raises(CameraError, match="Could not open capture device 0"):
        service.open(CaptureSettings(deviceIndex=0))

    assert not service.isOpen


def testOpenReportsTheFormatTheDeviceActuallyGranted() -> None:
    # Device insists on 720x576 @ 25 fps whatever we ask for.
    captures = {
        0: FakeCapture(
            frames=[makeFrame()],
            fixedProperties={
                cv2.CAP_PROP_FRAME_WIDTH: 720,
                cv2.CAP_PROP_FRAME_HEIGHT: 576,
                cv2.CAP_PROP_FPS: 25.0,
            },
        )
    }
    service = CameraService(captureFactory=factoryFor(captures), backend=0)

    effective = service.open(
        CaptureSettings(deviceIndex=0, frameWidth=640, frameHeight=480, framesPerSecond=30.0)
    )

    assert effective.frameWidth == 720
    assert effective.frameHeight == 576
    assert effective.framesPerSecond == 25.0
    assert service.isOpen


def testOpenFallsBackToRequestedSettingsWhenDeviceReportsNothing() -> None:
    captures = {0: FakeCapture(frames=[makeFrame()])}
    service = CameraService(captureFactory=factoryFor(captures), backend=0)
    # A device reporting 0 for everything must not yield a 0x0 capture.
    captures[0].properties.clear()
    captures[0].fixedProperties = {
        cv2.CAP_PROP_FRAME_WIDTH: 0,
        cv2.CAP_PROP_FRAME_HEIGHT: 0,
        cv2.CAP_PROP_FPS: 0,
    }

    effective = service.open(
        CaptureSettings(deviceIndex=0, frameWidth=640, frameHeight=480, framesPerSecond=30.0)
    )

    assert (effective.frameWidth, effective.frameHeight) == (640, 480)
    assert effective.framesPerSecond == 30.0


def testReadFrameWithoutOpenRaises() -> None:
    service = CameraService(captureFactory=factoryFor({}), backend=0)

    with pytest.raises(CameraError, match="No capture device is open"):
        service.readFrame()


def testReadFrameRaisesWhenTheDeviceStops() -> None:
    captures = {0: FakeCapture(frames=[makeFrame(value=10)])}
    service = CameraService(captureFactory=factoryFor(captures), backend=0)
    service.open(CaptureSettings(deviceIndex=0))

    first = service.readFrame()
    assert int(first.mean()) == 10

    with pytest.raises(CameraError, match="stopped delivering frames"):
        service.readFrame()


def testCloseReleasesTheDeviceAndClearsState() -> None:
    captures = {0: FakeCapture(frames=[makeFrame()])}
    service = CameraService(captureFactory=factoryFor(captures), backend=0)
    service.open(CaptureSettings(deviceIndex=0))

    service.close()

    assert captures[0].released
    assert not service.isOpen
    assert service.settings is None


def testCloseIsSafeToCallTwice() -> None:
    service = CameraService(captureFactory=factoryFor({}), backend=0)
    service.close()
    service.close()
    assert not service.isOpen
