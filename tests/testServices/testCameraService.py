"""Unit tests for CameraService, using a fake capture backend."""

from __future__ import annotations

import cv2
import numpy as np
import pytest

from rvBackupHelper.models.captureModels import CaptureSettings
from rvBackupHelper.services.capture.cameraService import CameraError, CameraService

# Stand-in backend ids, ordered the way the real ones are: the fast backend
# first, the one that copes with signal-less devices as the fallback.
primaryBackend = 101
secondaryBackend = 202
fakeBackends = [("Primary", primaryBackend), ("Secondary", secondaryBackend)]


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


def sizedCapture(width: int, height: int, frames: list[np.ndarray] | None = None) -> FakeCapture:
    """A capture reporting a size, optionally with frames to hand out."""
    return FakeCapture(
        frames=frames,
        fixedProperties={
            cv2.CAP_PROP_FRAME_WIDTH: width,
            cv2.CAP_PROP_FRAME_HEIGHT: height,
        },
    )


def factoryFor(captures: dict[tuple[int, int], FakeCapture]):
    """Capture factory serving a prepared FakeCapture per (index, backend)."""

    def factory(deviceIndex: int, backend: int) -> FakeCapture:
        return captures.get((deviceIndex, backend)) or FakeCapture(opened=False)

    return factory


def serviceWith(captures, names: list[str] | None = None) -> CameraService:
    return CameraService(
        captureFactory=factoryFor(captures),
        backends=fakeBackends,
        nameProvider=lambda: list(names or []),
    )


# ------------------------------------------------------------ discovery ---


def testListDevicesUsesFriendlyNamesAndBoundsTheProbe() -> None:
    captures = {
        (0, primaryBackend): FakeCapture(frames=[makeFrame(640, 480)]),
        (1, primaryBackend): FakeCapture(frames=[makeFrame(720, 576)]),
    }
    service = serviceWith(captures, names=["HD Pro Webcam C920", "USB Video"])

    devices = service.listDevices()

    assert [device.label for device in devices] == ["HD Pro Webcam C920", "USB Video"]
    assert devices[0].displayName == "HD Pro Webcam C920 (640x480)"


def testListDevicesFallsBackToGenericLabelsWithoutNames() -> None:
    captures = {(0, primaryBackend): FakeCapture(frames=[makeFrame()])}
    service = serviceWith(captures)

    devices = service.listDevices(maxIndex=2)

    assert [device.label for device in devices] == ["Camera 0"]


def testDeviceWithNoSignalIsStillListed() -> None:
    """A grabber with nothing plugged in opens but sends nothing. It is real."""
    captures = {
        # Opens on both backends, never yields a frame.
        (0, primaryBackend): sizedCapture(720, 576),
        (0, secondaryBackend): sizedCapture(720, 576),
    }
    service = serviceWith(captures, names=["USB Video"])

    devices = service.listDevices()

    assert len(devices) == 1
    device = devices[0]
    assert device.label == "USB Video"
    assert not device.hasSignal
    assert (device.frameWidth, device.frameHeight) == (720, 576)
    assert device.displayName == "USB Video (720x576, no signal)"


def testDeviceNoBackendCanOpenIsSkipped() -> None:
    """A virtual camera whose app is not running cannot be captured from."""
    service = serviceWith({}, names=["OBS Virtual Camera"])

    assert service.listDevices() == []


def testProbePrefersTheBackendThatDeliversFrames() -> None:
    captures = {
        (0, primaryBackend): sizedCapture(640, 480),  # opens, no frames
        (0, secondaryBackend): FakeCapture(frames=[makeFrame(640, 480)]),
    }
    service = serviceWith(captures, names=["Some Camera"])

    device = service.listDevices()[0]

    assert device.hasSignal
    assert device.backend == secondaryBackend
    assert device.backendName == "Secondary"


def testProbeFallsBackToABackendThatOpensWithoutSignal() -> None:
    captures = {(0, primaryBackend): sizedCapture(640, 480)}
    service = serviceWith(captures, names=["USB Video"])

    device = service.listDevices()[0]

    assert not device.hasSignal
    assert device.backend == primaryBackend


def testListDevicesReleasesEveryProbedDevice() -> None:
    captures = {
        (0, primaryBackend): FakeCapture(frames=[makeFrame()]),
        (1, primaryBackend): sizedCapture(640, 480),
        (1, secondaryBackend): sizedCapture(640, 480),
    }
    service = serviceWith(captures, names=["A", "B"])

    service.listDevices()

    assert all(capture.released for capture in captures.values())


# -------------------------------------------------------------- capture ---


def testOpenRaisesWhenDeviceWillNotOpen() -> None:
    service = serviceWith({})

    with pytest.raises(CameraError, match="Could not open capture device 0"):
        service.open(CaptureSettings(deviceIndex=0))

    assert not service.isOpen


def testOpenUsesTheBackendNamedInTheSettings() -> None:
    captures = {(0, secondaryBackend): FakeCapture(frames=[makeFrame()])}
    service = serviceWith(captures)

    effective = service.open(CaptureSettings(deviceIndex=0, backend=secondaryBackend))

    assert service.isOpen
    assert effective.backend == secondaryBackend


def testOpenWithoutABackendUsesTheFirstPriorityBackend() -> None:
    captures = {(0, primaryBackend): FakeCapture(frames=[makeFrame()])}
    service = serviceWith(captures)

    effective = service.open(CaptureSettings(deviceIndex=0))

    assert effective.backend == primaryBackend


def testOpenReportsTheFormatTheDeviceActuallyGranted() -> None:
    captures = {
        (0, primaryBackend): FakeCapture(
            frames=[makeFrame()],
            fixedProperties={
                cv2.CAP_PROP_FRAME_WIDTH: 720,
                cv2.CAP_PROP_FRAME_HEIGHT: 576,
                cv2.CAP_PROP_FPS: 25.0,
            },
        )
    }
    service = serviceWith(captures)

    effective = service.open(
        CaptureSettings(deviceIndex=0, frameWidth=640, frameHeight=480, framesPerSecond=30.0)
    )

    assert (effective.frameWidth, effective.frameHeight) == (720, 576)
    assert effective.framesPerSecond == 25.0


def testOpenFallsBackToRequestedSettingsWhenDeviceReportsNothing() -> None:
    captures = {
        (0, primaryBackend): FakeCapture(
            frames=[makeFrame()],
            fixedProperties={
                cv2.CAP_PROP_FRAME_WIDTH: 0,
                cv2.CAP_PROP_FRAME_HEIGHT: 0,
                cv2.CAP_PROP_FPS: 0,
            },
        )
    }
    service = serviceWith(captures)

    effective = service.open(
        CaptureSettings(deviceIndex=0, frameWidth=640, frameHeight=480, framesPerSecond=30.0)
    )

    assert (effective.frameWidth, effective.frameHeight) == (640, 480)
    assert effective.framesPerSecond == 30.0


def testReadFrameWithoutOpenRaises() -> None:
    service = serviceWith({})

    with pytest.raises(CameraError, match="No capture device is open"):
        service.readFrame()


def testReadFrameReturnsNoneWhenTheDeviceSendsNothing() -> None:
    """No frame is not an error — the signal may simply not have arrived yet."""
    captures = {(0, primaryBackend): FakeCapture(frames=[makeFrame(value=10)])}
    service = serviceWith(captures)
    service.open(CaptureSettings(deviceIndex=0))

    first = service.readFrame()
    assert first is not None
    assert int(first.mean()) == 10

    assert service.readFrame() is None


def testCloseReleasesTheDeviceAndClearsState() -> None:
    capture = FakeCapture(frames=[makeFrame()])
    service = serviceWith({(0, primaryBackend): capture})
    service.open(CaptureSettings(deviceIndex=0))

    service.close()

    assert capture.released
    assert not service.isOpen
    assert service.settings is None


def testCloseIsSafeToCallTwice() -> None:
    service = serviceWith({})
    service.close()
    service.close()
    assert not service.isOpen
