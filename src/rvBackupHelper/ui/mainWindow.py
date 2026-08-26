"""Main application window."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDesktopServices,
    QFontMetrics,
    QKeySequence,
)
from PySide6.QtWidgets import (
    QFileDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QTabWidget,
)

from rvBackupHelper import appConfig
from rvBackupHelper.services.board.toolchainService import ToolchainReport
from rvBackupHelper.services.board.toolchainWorker import ToolchainWorker
from rvBackupHelper.services.manual.manualWorker import ManualWorker
from rvBackupHelper.services.settingsService import SettingsService
from rvBackupHelper.ui.calibration.calibrationView import CalibrationView
from rvBackupHelper.ui.capture.captureView import CaptureView
from rvBackupHelper.ui.dialogs.aboutDialog import showAbout

# Pixel budget for the status-bar path before it is elided in the middle.
recordingsLabelWidth = 420


class MainWindow(QMainWindow):
    def __init__(self, settingsService: SettingsService | None = None) -> None:
        super().__init__()
        self.setWindowTitle(appConfig.windowTitle)
        self.resize(appConfig.defaultWindowWidth, appConfig.defaultWindowHeight)
        self.settingsService = settingsService or SettingsService()
        self.manualWorker: ManualWorker | None = None
        self.toolchainWorker: ToolchainWorker | None = None

        self.captureView = CaptureView()
        # Calibrate embeds the same clip browser a separate Review tab would
        # have been, so a second copy earned nothing.
        self.calibrationView = CalibrationView(settingsService=self.settingsService)

        self.tabs = QTabWidget()
        self.tabs.addTab(self.captureView, "Capture")
        self.tabs.addTab(self.calibrationView, "Calibrate")
        self.setCentralWidget(self.tabs)

        self.captureView.statusMessage.connect(self.showStatus)
        self.calibrationView.statusMessage.connect(self.showStatus)
        self.captureView.clipRecorded.connect(self.onClipRecorded)

        self.buildMenuBar()

        # A permanent widget sits to the right and survives transient messages,
        # so the save location stays visible while status text comes and goes.
        self.recordingsLabel = QLabel()
        # Keep clear of the size grip in the corner.
        self.recordingsLabel.setContentsMargins(0, 0, 8, 0)
        self.statusBar().addPermanentWidget(self.recordingsLabel)
        self.applyRecordingsDir(self.settingsService.recordingsDir())

        self.statusBar().showMessage("Ready")

    def buildMenuBar(self) -> None:
        # Menus are kept as attributes: features can extend them later, and it
        # prevents the Python wrappers from being garbage-collected.
        fileMenu = self.fileMenu = self.menuBar().addMenu("&File")

        self.openClipAction = QAction("&Open Clip...", self)
        self.openClipAction.setShortcut(QKeySequence.StandardKey.Open)
        self.openClipAction.triggered.connect(self.onOpenClip)
        fileMenu.addAction(self.openClipAction)

        self.recordingsDirAction = QAction("&Recordings Folder...", self)
        self.recordingsDirAction.triggered.connect(self.onChooseRecordingsDir)
        fileMenu.addAction(self.recordingsDirAction)

        fileMenu.addSeparator()

        self.exitAction = QAction("E&xit", self)
        self.exitAction.setShortcut(QKeySequence("Ctrl+Q"))
        self.exitAction.triggered.connect(self.close)
        fileMenu.addAction(self.exitAction)

        helpMenu = self.helpMenu = self.menuBar().addMenu("&Help")

        # First in the menu because it is what you reach for when something is
        # wrong, and everything else here is reading rather than diagnosing.
        self.toolchainAction = QAction("Check &Toolchain...", self)
        self.toolchainAction.triggered.connect(self.onCheckToolchain)
        helpMenu.addAction(self.toolchainAction)

        helpMenu.addSeparator()

        self.manualAction = QAction("User &Manual...", self)
        self.manualAction.setShortcut(QKeySequence.StandardKey.HelpContents)  # F1
        self.manualAction.triggered.connect(self.onHelpManual)
        helpMenu.addAction(self.manualAction)

        self.aboutAction = QAction("&About", self)
        self.aboutAction.triggered.connect(self.onHelpAbout)
        helpMenu.addAction(self.aboutAction)

    def showStatus(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def onOpenClip(self) -> None:
        self.tabs.setCurrentWidget(self.calibrationView)
        self.calibrationView.onOpenClipClicked()

    def onChooseRecordingsDir(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, "Choose Recordings Folder", str(self.recordingsDir)
        )
        if not chosen:
            return
        path = Path(chosen)
        self.settingsService.setRecordingsDir(path)
        self.applyRecordingsDir(path)
        self.showStatus(f"Recordings folder set to {path}")

    def applyRecordingsDir(self, path: Path) -> None:
        """Point both tabs and the status bar at the chosen folder."""
        self.recordingsDir = path
        self.captureView.setRecordingsDir(path)
        self.calibrationView.setRecordingsDir(path)
        self.updateRecordingsLabel()

    def updateRecordingsLabel(self) -> None:
        # Elide in the middle: a deep path keeps its drive and its final folder,
        # which is what identifies it at a glance.
        metrics = QFontMetrics(self.recordingsLabel.font())
        self.recordingsLabel.setText(
            metrics.elidedText(
                f"Recordings: {self.recordingsDir}",
                Qt.TextElideMode.ElideMiddle,
                recordingsLabelWidth,
            )
        )
        self.recordingsLabel.setToolTip(str(self.recordingsDir))

    def onClipRecorded(self, path: Path) -> None:
        """Load a just-finished recording so Calibrate is ready on switch."""
        self.calibrationView.openClip(path)

    def onHelpManual(self) -> None:
        """Open the manual, preferring the published copy.

        GitHub renders the markdown and its screenshots; a local .md opens in
        whatever editor claims the extension and shows the screenshots as link
        text. So the published copy wins when it is reachable - but openUrl
        only reports that a browser launched, not that the page loaded, so
        whether it is reachable has to be asked separately, off this thread.
        """
        if self.manualWorker is not None:
            return
        self.manualAction.setEnabled(False)
        self.showStatus("Looking for the manual...")
        worker = ManualWorker(parent=self)
        worker.resolved.connect(self.openManual)
        worker.finished.connect(self.onManualCheckFinished)
        self.manualWorker = worker
        worker.start()

    def openManual(self, publishedIsReachable: bool) -> None:
        if publishedIsReachable and QDesktopServices.openUrl(
            QUrl(appConfig.manualUrl)
        ):
            self.showStatus("The manual is opening in your browser.")
            return
        local = appConfig.manualPath
        if local.exists() and QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(local))
        ):
            self.showStatus(f"No connection - opening the local copy, {local}")
            return
        # Leaving the user with nothing is worse than making them copy a URL.
        QMessageBox.information(
            self,
            "User Manual",
            "Could not open the manual. It is at:\n\n"
            f"{appConfig.manualUrl}\n\n{local}",
        )

    def onManualCheckFinished(self) -> None:
        if self.manualWorker is not None:
            self.manualWorker.deleteLater()
            self.manualWorker = None
        self.manualAction.setEnabled(True)

    def onCheckToolchain(self) -> None:
        """Compile something, and report what the compiler used.

        Answers the question before an upload does, and answers it with a build
        rather than with a directory listing - which is the distinction that
        cost a working day when a missing core was reported as present by
        everything that was not the compiler.
        """
        if self.toolchainWorker is not None:
            return
        self.toolchainAction.setEnabled(False)
        self.showStatus("Checking the toolchain - compiling a sketch...")
        worker = ToolchainWorker(parent=self)
        worker.checked.connect(self.onToolchainChecked)
        worker.finished.connect(self.onToolchainCheckFinished)
        self.toolchainWorker = worker
        worker.start()

    def onToolchainChecked(self, report: ToolchainReport) -> None:
        self.showStatus(report.headline)
        self.showToolchainReport(report)

    def showToolchainReport(self, report: ToolchainReport) -> None:
        """Kept separate so tests can watch for it without a dialog opening."""
        box = QMessageBox(self)
        box.setIcon(
            QMessageBox.Icon.Information if report.ok else QMessageBox.Icon.Warning
        )
        box.setWindowTitle("Toolchain")
        box.setText(report.headline)
        # Paths and a compiler's own words: worth reading in full, and worth
        # being able to copy into a message to somebody else.
        box.setInformativeText(report.details)
        box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        box.exec()

    def onToolchainCheckFinished(self) -> None:
        if self.toolchainWorker is not None:
            self.toolchainWorker.deleteLater()
            self.toolchainWorker = None
        self.toolchainAction.setEnabled(True)

    def onHelpAbout(self) -> None:
        if showAbout(self):
            self.showStatus("Thank you - the donation page is opening in your browser.")

    def closeEvent(self, event: QCloseEvent) -> None:
        if self.manualWorker is not None:
            self.manualWorker.wait(int(appConfig.manualTimeoutSeconds * 1000) + 1000)
        if self.toolchainWorker is not None:
            # A compile in flight; it is short, and leaving the thread running
            # into interpreter shutdown is how a clean exit turns into a crash.
            self.toolchainWorker.wait(int(appConfig.uploadTimeoutSeconds * 1000))
        self.captureView.shutdown()
        self.calibrationView.shutdown()
        super().closeEvent(event)
