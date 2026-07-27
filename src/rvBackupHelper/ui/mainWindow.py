"""Main application window."""

from __future__ import annotations

import datetime
from pathlib import Path

from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import QMainWindow, QMessageBox, QTabWidget

from rvBackupHelper import appConfig
from rvBackupHelper.ui.capture.captureView import CaptureView
from rvBackupHelper.ui.review.reviewView import ReviewView


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(appConfig.windowTitle)
        self.resize(appConfig.defaultWindowWidth, appConfig.defaultWindowHeight)

        self.captureView = CaptureView()
        self.reviewView = ReviewView()

        self.tabs = QTabWidget()
        self.tabs.addTab(self.captureView, "Capture")
        self.tabs.addTab(self.reviewView, "Review")
        self.setCentralWidget(self.tabs)

        self.captureView.statusMessage.connect(self.showStatus)
        self.reviewView.statusMessage.connect(self.showStatus)
        self.captureView.clipRecorded.connect(self.onClipRecorded)

        self.buildMenuBar()
        self.statusBar().showMessage("Ready")

    def buildMenuBar(self) -> None:
        # Menus are kept as attributes: features can extend them later, and it
        # prevents the Python wrappers from being garbage-collected.
        fileMenu = self.fileMenu = self.menuBar().addMenu("&File")

        self.openClipAction = QAction("&Open Clip...", self)
        self.openClipAction.setShortcut(QKeySequence.StandardKey.Open)
        self.openClipAction.triggered.connect(self.onOpenClip)
        fileMenu.addAction(self.openClipAction)

        fileMenu.addSeparator()

        self.exitAction = QAction("E&xit", self)
        self.exitAction.setShortcut(QKeySequence("Ctrl+Q"))
        self.exitAction.triggered.connect(self.close)
        fileMenu.addAction(self.exitAction)

        helpMenu = self.helpMenu = self.menuBar().addMenu("&Help")

        self.aboutAction = QAction("&About", self)
        self.aboutAction.triggered.connect(self.onHelpAbout)
        helpMenu.addAction(self.aboutAction)

    def showStatus(self, message: str) -> None:
        self.statusBar().showMessage(message)

    def onOpenClip(self) -> None:
        self.tabs.setCurrentWidget(self.reviewView)
        self.reviewView.onOpenClicked()

    def onClipRecorded(self, path: Path) -> None:
        """Load a just-finished recording so the Review tab is ready on switch."""
        self.reviewView.openClip(path)

    def buildAboutText(self) -> str:
        year = datetime.date.today().year
        return (
            f"<h3>{appConfig.appName}</h3>"
            f"<p>Version {appConfig.appVersion}</p>"
            f"<p>Editor: {appConfig.editorName}<br>"
            f"AI Agent: {appConfig.aiAgentName}</p>"
            f"<p>&copy; {year} {appConfig.copyrightHolder}</p>"
        )

    def onHelpAbout(self) -> None:
        aboutBox = QMessageBox(self)
        aboutBox.setWindowTitle(f"About {appConfig.appName}")
        aboutBox.setText(self.buildAboutText())
        # QMessageBox ignores resize/setMinimumWidth; widening its label works.
        aboutBox.setStyleSheet("QLabel { min-width: 420px; }")
        aboutBox.exec()

    def closeEvent(self, event: QCloseEvent) -> None:
        self.captureView.shutdown()
        self.reviewView.shutdown()
        super().closeEvent(event)
