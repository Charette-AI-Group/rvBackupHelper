"""Calibrate tab: mark real-world distances against camera scan lines.

Workflow: open a clip, step to the frame where the markers laid out behind the
RV are readable, set a distance, then click that marker in the image. Each
click records the scan line it landed on and draws a guide there.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDoubleSpinBox,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rvBackupHelper import appConfig
from rvBackupHelper.models.calibrationModels import Calibration, CalibrationPoint
from rvBackupHelper.models.captureModels import ClipInfo
from rvBackupHelper.services.calibration.calibrationService import (
    CalibrationError,
    CalibrationService,
    defaultCalibrationPath,
)
from rvBackupHelper.ui.widgets.clipBrowser import ClipBrowser

logger = logging.getLogger(__name__)

calibrationFilter = "Calibration files (*.json);;All files (*)"
panelWidth = 320
instructions = (
    "Open the clip you recorded behind the RV and step to the frame where your "
    "distance markers are readable. Set the distance below, then click that "
    "marker in the image."
)


class CalibrationView(QWidget):
    """A clip browser with a panel for recording measured distances."""

    statusMessage = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = CalibrationService()
        self.calibration = Calibration()
        self.calibrationPath: Path | None = None
        self.buildUi()
        self.refresh()

    def setRecordingsDir(self, path: Path) -> None:
        self.clipBrowser.setRecordingsDir(path)

    def buildUi(self) -> None:
        self.clipBrowser = ClipBrowser()
        self.clipBrowser.statusMessage.connect(self.statusMessage)
        self.clipBrowser.clipOpened.connect(self.onClipOpened)
        self.clipBrowser.videoDisplay.framePointClicked.connect(self.onFramePointClicked)
        # A crosshair says "click the picture" better than any label can.
        self.clipBrowser.videoDisplay.setCursor(Qt.CursorShape.CrossCursor)

        layout = QHBoxLayout(self)
        layout.addWidget(self.clipBrowser, stretch=1)
        layout.addWidget(self.buildPanel())

    def buildPanel(self) -> QWidget:
        panel = QWidget()
        panel.setFixedWidth(panelWidth)

        instructionLabel = QLabel(instructions)
        instructionLabel.setWordWrap(True)

        self.distanceSpin = QDoubleSpinBox()
        self.distanceSpin.setRange(
            appConfig.minimumDistanceFeet, appConfig.maximumDistanceFeet
        )
        self.distanceSpin.setValue(appConfig.defaultDistanceFeet)
        self.distanceSpin.setDecimals(1)
        self.distanceSpin.setSingleStep(0.5)
        self.distanceSpin.setSuffix(" ft")

        distanceRow = QHBoxLayout()
        distanceRow.addWidget(QLabel("Distance:"))
        distanceRow.addWidget(self.distanceSpin, stretch=1)

        self.pointsTable = QTableWidget(0, 3)
        self.pointsTable.setHorizontalHeaderLabels(["Distance", "Scan line", "OSD row"])
        self.pointsTable.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.pointsTable.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.pointsTable.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.pointsTable.verticalHeader().setVisible(False)
        self.pointsTable.itemSelectionChanged.connect(self.updateControls)

        self.removeButton = QPushButton("Remove Selected")
        self.removeButton.clicked.connect(self.onRemoveClicked)
        self.clearButton = QPushButton("Clear All")
        self.clearButton.clicked.connect(self.onClearClicked)
        self.loadButton = QPushButton("Load...")
        self.loadButton.clicked.connect(self.onLoadClicked)
        self.saveButton = QPushButton("Save...")
        self.saveButton.clicked.connect(self.onSaveClicked)

        buttons = QGridLayout()
        buttons.addWidget(self.removeButton, 0, 0)
        buttons.addWidget(self.clearButton, 0, 1)
        buttons.addWidget(self.loadButton, 1, 0)
        buttons.addWidget(self.saveButton, 1, 1)

        self.summaryLabel = QLabel()
        self.summaryLabel.setWordWrap(True)

        layout = QVBoxLayout(panel)
        layout.addWidget(instructionLabel)
        layout.addLayout(distanceRow)
        layout.addWidget(self.pointsTable, stretch=1)
        layout.addLayout(buttons)
        layout.addWidget(self.summaryLabel)
        return panel

    # ------------------------------------------------------------ editing --

    def onClipOpened(self, clipInfo: ClipInfo) -> None:
        """Adopt the new clip's geometry, discarding points measured elsewhere.

        Scan lines from a differently sized frame would silently mean different
        distances, so they cannot be carried across.
        """
        sizeChanged = (clipInfo.frameWidth, clipInfo.frameHeight) != (
            self.calibration.frameWidth,
            self.calibration.frameHeight,
        )
        if sizeChanged and not self.calibration.isEmpty:
            self.calibration.clear()
            self.statusMessage.emit(
                "Cleared existing points: the new clip has a different frame size."
            )
        self.calibration.frameWidth = clipInfo.frameWidth
        self.calibration.frameHeight = clipInfo.frameHeight
        self.calibration.sourceClip = clipInfo.path.name
        self.refresh()

    def onFramePointClicked(self, x: int, y: int) -> None:
        if self.clipBrowser.clipInfo is None:
            self.statusMessage.emit("Open a clip before marking distances.")
            return
        point = CalibrationPoint(distanceFeet=self.distanceSpin.value(), scanLine=y)
        self.calibration.addPoint(point)
        self.calibration.frameIndex = self.clipBrowser.currentFrameIndex
        self.refresh()
        self.statusMessage.emit(f"Marked {point.label} at scan line {y}.")

    def selectedDistance(self) -> float | None:
        row = self.pointsTable.currentRow()
        points = self.calibration.sortedPoints
        if row < 0 or row >= len(points):
            return None
        return points[row].distanceFeet

    def onRemoveClicked(self) -> None:
        distance = self.selectedDistance()
        if distance is None:
            return
        if self.calibration.removeDistance(distance):
            self.statusMessage.emit(f"Removed the {distance:g} ft point.")
        self.refresh()

    def onClearClicked(self) -> None:
        if self.calibration.isEmpty:
            return
        count = len(self.calibration.points)
        self.calibration.clear()
        self.refresh()
        self.statusMessage.emit(f"Cleared {count} point(s).")

    # ---------------------------------------------------------- files -----

    def onSaveClicked(self) -> None:
        if self.calibration.isEmpty:
            self.statusMessage.emit("Nothing to save yet - mark a distance first.")
            return
        suggested = self.calibrationPath or defaultCalibrationPath()
        suggested.parent.mkdir(parents=True, exist_ok=True)
        fileName, _ = QFileDialog.getSaveFileName(
            self, "Save Calibration", str(suggested), calibrationFilter
        )
        if not fileName:
            return
        path = Path(fileName)
        try:
            self.service.save(self.calibration, path)
        except OSError as exc:
            logger.warning("Could not save calibration: %s", exc)
            self.statusMessage.emit(f"Could not save calibration: {exc}")
            return
        self.calibrationPath = path
        self.statusMessage.emit(
            f"Saved {len(self.calibration.points)} point(s) to {path.name}"
        )
        self.refresh()

    def onLoadClicked(self) -> None:
        startDir = self.calibrationPath or defaultCalibrationPath()
        fileName, _ = QFileDialog.getOpenFileName(
            self, "Load Calibration", str(startDir), calibrationFilter
        )
        if not fileName:
            return
        self.loadCalibration(Path(fileName))

    def loadCalibration(self, path: Path) -> None:
        try:
            calibration = self.service.load(path)
        except CalibrationError as exc:
            logger.warning("Could not load calibration: %s", exc)
            self.statusMessage.emit(str(exc))
            return
        self.calibration = calibration
        self.calibrationPath = path
        self.refresh()
        self.statusMessage.emit(f"Loaded {len(calibration.points)} point(s) from {path.name}")

    # ------------------------------------------------------------ display --

    def refresh(self) -> None:
        self.refreshTable()
        self.clipBrowser.videoDisplay.setMarkers(self.calibration.markers())
        self.updateSummary()
        self.updateControls()

    def refreshTable(self) -> None:
        points = self.calibration.sortedPoints
        self.pointsTable.setRowCount(len(points))
        for row, point in enumerate(points):
            values = (
                point.label,
                str(point.scanLine),
                str(self.calibration.overlayRow(point.scanLine)),
            )
            for column, value in enumerate(values):
                self.pointsTable.setItem(row, column, QTableWidgetItem(value))
        self.pointsTable.resizeColumnsToContents()

    def updateSummary(self) -> None:
        if self.calibration.isEmpty:
            self.summaryLabel.setText("No points yet.")
            return
        frame = f"{self.calibration.frameWidth}x{self.calibration.frameHeight}"
        overlay = f"{appConfig.overlayCanvasWidth}x{appConfig.overlayCanvasHeight}"
        self.summaryLabel.setText(
            f"{len(self.calibration.points)} point(s) measured on a {frame} frame. "
            f"OSD rows are for the {overlay} shield canvas."
        )

    def updateControls(self) -> None:
        hasPoints = not self.calibration.isEmpty
        self.removeButton.setEnabled(self.selectedDistance() is not None)
        self.clearButton.setEnabled(hasPoints)
        self.saveButton.setEnabled(hasPoints)

    # ----------------------------------------------------------- shutdown --

    def shutdown(self) -> None:
        self.clipBrowser.shutdown()
