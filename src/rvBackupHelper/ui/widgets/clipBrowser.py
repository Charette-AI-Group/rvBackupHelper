"""Opens a recorded clip and steps through it frame by frame.

Embedded by the Calibrate tab. Kept as its own widget rather than folded in,
so the seek behaviour and the transport controls stay one implementation if a
second consumer ever appears.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from rvBackupHelper import appConfig
from rvBackupHelper.models.captureModels import ClipInfo
from rvBackupHelper.services.review.clipReaderService import (
    ClipError,
    ClipReaderService,
)
from rvBackupHelper.ui.widgets.videoDisplay import VideoDisplay

logger = logging.getLogger(__name__)

clipFilter = "Video clips (*.avi *.mp4 *.mkv);;All files (*)"


class ClipBrowser(QWidget):
    """A clip, a frame of it, and the controls to move between frames."""

    statusMessage = Signal(str)
    # Payload is the ClipInfo of a newly opened clip.
    clipOpened = Signal(object)
    # Payload is the index of the frame now on screen.
    frameShown = Signal(int)

    def __init__(self, parent: QWidget | None = None, opener=None) -> None:
        super().__init__(parent)
        # Injected so the folder button can be tested without a file
        # manager opening on whoever is running the suite.
        self.opener = QDesktopServices.openUrl if opener is None else opener
        self.reader = ClipReaderService()
        self.clipInfo: ClipInfo | None = None
        self.clipPath: Path | None = None
        self.currentFrameIndex = 0
        self.recordingsDir = appConfig.recordingsDir
        self.buildUi()
        self.updateControls()

    def setRecordingsDir(self, path: Path) -> None:
        """Where the Open dialog starts looking."""
        self.recordingsDir = path

    def buildUi(self) -> None:
        self.openButton = QPushButton("Open Clip...")
        self.openButton.clicked.connect(self.onOpenClicked)
        self.clipLabel = QLabel("No clip open")

        # Same folder the About box names under "Your files", and reached the
        # same way, from the tab where somebody is actually looking for the
        # clips and calibrations in it. In a frozen build that path is under
        # AppData and nobody would think to look there; in a checkout it is the
        # checkout, and the button is merely convenient.
        self.filesButton = QPushButton("Your Files")
        self.filesButton.setToolTip(f"Open {appConfig.userDataDir} in File Explorer")
        self.filesButton.clicked.connect(self.onFilesClicked)

        header = QHBoxLayout()
        header.addWidget(self.openButton)
        header.addWidget(self.clipLabel, stretch=1)
        header.addWidget(self.filesButton)

        self.videoDisplay = VideoDisplay()
        self.videoDisplay.clear("Open a clip")

        self.previousButton = QPushButton("< Previous")
        self.previousButton.clicked.connect(self.onPreviousClicked)
        self.nextButton = QPushButton("Next >")
        self.nextButton.clicked.connect(self.onNextClicked)

        self.frameSlider = QSlider(Qt.Orientation.Horizontal)
        self.frameSlider.valueChanged.connect(self.onSliderChanged)

        self.frameSpin = QSpinBox()
        self.frameSpin.valueChanged.connect(self.onSpinChanged)

        self.positionLabel = QLabel("-")
        # Reserve room for the widest reading ("frame 1234 / 5678  (41.13 s)"),
        # otherwise the label is squeezed off the right edge as the clip grows.
        self.positionLabel.setMinimumWidth(200)

        transport = QHBoxLayout()
        transport.addWidget(self.previousButton)
        transport.addWidget(self.frameSlider, stretch=1)
        transport.addWidget(self.nextButton)
        transport.addWidget(self.frameSpin)
        transport.addWidget(self.positionLabel)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(header)
        layout.addWidget(self.videoDisplay, stretch=1)
        layout.addLayout(transport)

    # ------------------------------------------------------------ opening --

    def onFilesClicked(self) -> None:
        """Hand the folder to the system file manager.

        as_uri() rather than a path, so this and the About box are demonstrably
        opening the same thing. A frozen build's folder is seeded at first run,
        but a machine where that never happened would otherwise get a button
        that does nothing at all, which is worse than being told.
        """
        folder = appConfig.userDataDir
        if not folder.is_dir():
            self.statusMessage.emit(f"{folder} does not exist yet.")
            return
        if not self.opener(QUrl(folder.as_uri())):
            self.statusMessage.emit(f"Could not open {folder}.")
            return
        self.statusMessage.emit(f"Opened {folder}")

    def onOpenClicked(self) -> None:
        startDir = (
            self.recordingsDir if self.recordingsDir.exists() else appConfig.projectRoot
        )
        fileName, _ = QFileDialog.getOpenFileName(
            self, "Open Clip", str(startDir), clipFilter
        )
        if fileName:
            self.openClip(Path(fileName))

    def openClip(self, path: Path) -> None:
        try:
            clipInfo = self.reader.open(path)
        except ClipError as exc:
            logger.warning("Could not open clip: %s", exc)
            self.statusMessage.emit(str(exc))
            return

        self.clipInfo = clipInfo
        self.clipPath = path
        lastIndex = max(clipInfo.frameCount - 1, 0)
        self.frameSlider.setRange(0, lastIndex)
        self.frameSpin.setRange(0, lastIndex)
        self.clipLabel.setText(
            f"{path.name} - {clipInfo.frameWidth}x{clipInfo.frameHeight}, "
            f"{clipInfo.frameCount} frames @ {clipInfo.framesPerSecond:.1f} fps"
        )
        self.statusMessage.emit(f"Opened {path.name}")
        self.updateControls()
        self.clipOpened.emit(clipInfo)
        self.showFrame(0)

    # --------------------------------------------------------- navigation --

    def onSliderChanged(self, value: int) -> None:
        self.frameSpin.blockSignals(True)
        self.frameSpin.setValue(value)
        self.frameSpin.blockSignals(False)
        self.renderFrame(value)

    def onSpinChanged(self, value: int) -> None:
        self.frameSlider.setValue(value)

    def onPreviousClicked(self) -> None:
        self.frameSlider.setValue(
            max(self.frameSlider.value() - 1, self.frameSlider.minimum())
        )

    def onNextClicked(self) -> None:
        self.frameSlider.setValue(
            min(self.frameSlider.value() + 1, self.frameSlider.maximum())
        )

    def showFrame(self, frameIndex: int) -> None:
        """Move to a frame, keeping the transport controls in step.

        Going through the slider matters: rendering directly would leave the
        slider and spin box pointing somewhere else, and the position label
        would contradict them.
        """
        if self.clipInfo is None:
            return
        frameIndex = max(
            self.frameSlider.minimum(), min(frameIndex, self.frameSlider.maximum())
        )
        if self.frameSlider.value() != frameIndex:
            self.frameSlider.setValue(frameIndex)  # onSliderChanged renders it
            return
        self.renderFrame(frameIndex)

    def renderFrame(self, frameIndex: int) -> None:
        if self.clipInfo is None:
            return
        try:
            frame = self.reader.readFrameAt(frameIndex)
        except ClipError as exc:
            logger.warning("Could not read frame %d: %s", frameIndex, exc)
            self.statusMessage.emit(str(exc))
            return
        self.currentFrameIndex = frameIndex
        self.videoDisplay.showFrame(frame)
        self.updatePositionLabel(frameIndex)
        self.frameShown.emit(frameIndex)

    def updatePositionLabel(self, frameIndex: int) -> None:
        if self.clipInfo is None:
            self.positionLabel.setText("-")
            return
        seconds = self.clipInfo.timestampOf(frameIndex)
        lastIndex = max(self.clipInfo.frameCount - 1, 0)
        self.positionLabel.setText(f"frame {frameIndex} / {lastIndex}  ({seconds:.2f} s)")

    def updateControls(self) -> None:
        hasClip = self.clipInfo is not None
        for widget in (
            self.previousButton,
            self.nextButton,
            self.frameSlider,
            self.frameSpin,
        ):
            widget.setEnabled(hasClip)

    # ----------------------------------------------------------- shutdown --

    def shutdown(self) -> None:
        self.reader.close()
