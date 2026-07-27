"""Tests for the shared clip browser."""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytest

from rvBackupHelper import appConfig
from rvBackupHelper.ui.widgets.clipBrowser import ClipBrowser

frameCount = 8


def writeClip(path: Path, width: int = 640, height: int = 480) -> Path:
    fourcc = cv2.VideoWriter.fourcc(*appConfig.recordingFourcc)
    writer = cv2.VideoWriter(str(path), fourcc, 30.0, (width, height))
    assert writer.isOpened()
    try:
        for index in range(frameCount):
            writer.write(np.full((height, width, 3), 20 + index * 25, dtype=np.uint8))
    finally:
        writer.release()
    return path


@pytest.fixture
def browser(qtbot, tmp_path: Path) -> ClipBrowser:
    widget = ClipBrowser()
    qtbot.addWidget(widget)
    widget.openClip(writeClip(tmp_path / "clip.avi"))
    return widget


def testTransportIsDisabledUntilAClipIsOpen(qtbot) -> None:
    widget = ClipBrowser()
    qtbot.addWidget(widget)

    assert not widget.frameSlider.isEnabled()
    assert not widget.nextButton.isEnabled()


def testOpeningAClipStartsAtTheFirstFrame(browser: ClipBrowser) -> None:
    assert browser.clipInfo is not None
    assert browser.currentFrameIndex == 0
    assert browser.frameSlider.maximum() == frameCount - 1
    assert browser.videoDisplay.hasFrame
    assert browser.frameSlider.isEnabled()


def testShowFrameKeepsTheTransportInStep(browser: ClipBrowser) -> None:
    """A caller jumping to a frame must not leave the slider contradicting it."""
    browser.showFrame(5)

    assert browser.currentFrameIndex == 5
    assert browser.frameSlider.value() == 5
    assert browser.frameSpin.value() == 5
    assert "frame 5 /" in browser.positionLabel.text()


def testShowFrameClampsToTheClip(browser: ClipBrowser) -> None:
    browser.showFrame(999)

    assert browser.currentFrameIndex == frameCount - 1
    assert browser.frameSlider.value() == frameCount - 1


def testSteppingWithTheButtonsMovesOneFrame(browser: ClipBrowser) -> None:
    browser.showFrame(3)

    browser.onNextClicked()
    assert browser.currentFrameIndex == 4

    browser.onPreviousClicked()
    assert browser.currentFrameIndex == 3


def testSteppingStopsAtTheEnds(browser: ClipBrowser) -> None:
    browser.onPreviousClicked()
    assert browser.currentFrameIndex == 0

    browser.showFrame(frameCount - 1)
    browser.onNextClicked()
    assert browser.currentFrameIndex == frameCount - 1


def testSpinBoxAndSliderStayPaired(browser: ClipBrowser) -> None:
    browser.frameSpin.setValue(6)
    assert browser.frameSlider.value() == 6

    browser.frameSlider.setValue(2)
    assert browser.frameSpin.value() == 2
    assert browser.currentFrameIndex == 2


def testFrameShownReportsEachMove(browser: ClipBrowser) -> None:
    seen: list[int] = []
    browser.frameShown.connect(seen.append)

    browser.showFrame(4)

    assert seen == [4]


def testOpeningAMissingClipReportsItAndKeepsTheCurrentOne(
    browser: ClipBrowser, tmp_path: Path
) -> None:
    messages: list[str] = []
    browser.statusMessage.connect(messages.append)

    browser.openClip(tmp_path / "nope.avi")

    assert browser.clipInfo is not None  # still on the good clip
    assert "not found" in messages[-1]
