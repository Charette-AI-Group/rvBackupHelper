"""Tests for the video display widget and its frame conversion."""

from __future__ import annotations

import numpy as np
import pytest
from PySide6.QtGui import QImage

from rvBackupHelper.ui.widgets.videoDisplay import VideoDisplay, toQImage


def makeFrame(width: int = 64, height: int = 48, value: int = 128) -> np.ndarray:
    return np.full((height, width, 3), value, dtype=np.uint8)


def testToQImageMatchesFrameGeometry(qtbot) -> None:
    image = toQImage(makeFrame(64, 48))

    assert image.width() == 64
    assert image.height() == 48
    assert image.format() == QImage.Format.Format_BGR888


def testToQImageDoesNotAliasTheNumpyBuffer(qtbot) -> None:
    """The QImage must own its pixels — the capture loop reuses the frame."""
    frame = makeFrame(value=10)
    image = toQImage(frame)
    originalPixel = image.pixelColor(0, 0)

    frame[:] = 200

    assert image.pixelColor(0, 0) == originalPixel


def testToQImageRejectsNonBgrFrames(qtbot) -> None:
    grayscale = np.zeros((48, 64), dtype=np.uint8)

    with pytest.raises(ValueError, match="3-channel BGR frame"):
        toQImage(grayscale)


def testShowFrameThenClear(qtbot) -> None:
    display = VideoDisplay()
    qtbot.addWidget(display)

    assert not display.hasFrame

    display.showFrame(makeFrame())
    assert display.hasFrame

    display.clear("Nothing here")
    assert not display.hasFrame
    assert display.placeholderText == "Nothing here"


def testHintIsEmptyUntilSet(qtbot) -> None:
    display = VideoDisplay()
    qtbot.addWidget(display)

    assert display.hintText == ""


def testSetHintThenClearHint(qtbot) -> None:
    display = VideoDisplay()
    qtbot.addWidget(display)

    display.setHint("Press Scan Devices to start")
    assert display.hintText == "Press Scan Devices to start"

    display.clearHint()
    assert display.hintText == ""


def testHintChangesWhatIsPainted(qtbot) -> None:
    display = VideoDisplay()
    qtbot.addWidget(display)
    display.resize(400, 300)
    display.clear("No video")

    withoutHint = display.grab().toImage()
    display.setHint("Press Scan Devices to start")
    withHint = display.grab().toImage()

    assert withHint != withoutHint


def testHintIsNotPaintedOverAFrame(qtbot) -> None:
    """Once video is showing, the placeholder and its hint are gone."""
    display = VideoDisplay()
    qtbot.addWidget(display)
    display.resize(400, 300)
    display.setHint("Press Scan Devices to start")

    display.showFrame(makeFrame(400, 300, value=90))
    withHint = display.grab().toImage()
    display.clearHint()

    assert display.grab().toImage() == withHint


def testFrameRectKeepsAspectRatioAndCentres(qtbot) -> None:
    display = VideoDisplay()
    qtbot.addWidget(display)
    display.resize(800, 400)
    display.showFrame(makeFrame(640, 480))  # 4:3 into a 2:1 widget

    rect = display.frameRect()

    assert rect.height() == 400
    assert rect.width() == pytest.approx(533, abs=2)  # 400 * 4/3
    assert rect.left() == pytest.approx((800 - rect.width()) // 2, abs=1)
    assert rect.top() == 0
