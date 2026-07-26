"""Main application window."""

from __future__ import annotations

import datetime

from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rvBackupHelper import appConfig


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(appConfig.windowTitle)
        self.resize(appConfig.defaultWindowWidth, appConfig.defaultWindowHeight)

        self.buildMenuBar()
        self.statusBar().showMessage("Ready")

        self.greetButton = QPushButton("Say Hello")
        self.greetButton.clicked.connect(self.onGreetClicked)

        centralWidget = QWidget()
        layout = QVBoxLayout(centralWidget)
        layout.addWidget(self.greetButton)
        layout.addStretch()

        self.setCentralWidget(centralWidget)

    def buildMenuBar(self) -> None:
        # Menus are kept as attributes: features can extend them later, and it
        # prevents the Python wrappers from being garbage-collected.
        fileMenu = self.fileMenu = self.menuBar().addMenu("&File")

        self.newAction = QAction("&New", self)
        self.newAction.setShortcut(QKeySequence.StandardKey.New)
        self.newAction.triggered.connect(self.onFileNew)
        fileMenu.addAction(self.newAction)

        self.openAction = QAction("&Open...", self)
        self.openAction.setShortcut(QKeySequence.StandardKey.Open)
        self.openAction.triggered.connect(self.onFileOpen)
        fileMenu.addAction(self.openAction)

        self.saveAction = QAction("&Save", self)
        self.saveAction.setShortcut(QKeySequence.StandardKey.Save)
        self.saveAction.triggered.connect(self.onFileSave)
        fileMenu.addAction(self.saveAction)

        fileMenu.addSeparator()

        self.exitAction = QAction("E&xit", self)
        self.exitAction.setShortcut(QKeySequence("Ctrl+Q"))
        self.exitAction.triggered.connect(self.close)
        fileMenu.addAction(self.exitAction)

        helpMenu = self.helpMenu = self.menuBar().addMenu("&Help")

        self.aboutAction = QAction("&About", self)
        self.aboutAction.triggered.connect(self.onHelpAbout)
        helpMenu.addAction(self.aboutAction)

    # Placeholder slots — replace the bodies with your app's file handling.
    def onFileNew(self) -> None:
        self.statusBar().showMessage("File > New selected")

    def onFileOpen(self) -> None:
        self.statusBar().showMessage("File > Open selected")

    def onFileSave(self) -> None:
        self.statusBar().showMessage("File > Save selected")

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

    def onGreetClicked(self) -> None:
        self.statusBar().showMessage("Hello from RV Backup Helper")
