"""Smoke tests for the main window."""

from __future__ import annotations

from PySide6.QtCore import Qt

from rvBackupHelper.ui.mainWindow import MainWindow


def testMainWindowOpens(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    mainWindow.show()

    assert mainWindow.isVisible()
    assert mainWindow.windowTitle() == "RV Backup Helper"
    assert mainWindow.statusBar().currentMessage() == "Ready"


def testGreetButtonUpdatesLabel(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    mainWindow.show()

    qtbot.mouseClick(mainWindow.greetButton, Qt.MouseButton.LeftButton)

    assert mainWindow.statusBar().currentMessage() == "Hello from RV Backup Helper"


def testMenuBarStructure(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    menuTitles = [action.text() for action in mainWindow.menuBar().actions()]
    assert menuTitles == ["&File", "&Help"]

    fileItems = [a.text() for a in mainWindow.fileMenu.actions() if not a.isSeparator()]
    assert fileItems == ["&New", "&Open...", "&Save", "E&xit"]
    assert any(a.isSeparator() for a in mainWindow.fileMenu.actions())

    assert [a.text() for a in mainWindow.helpMenu.actions()] == ["&About"]


def testFileMenuPlaceholdersUpdateStatus(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    mainWindow.newAction.trigger()
    assert mainWindow.statusBar().currentMessage() == "File > New selected"

    mainWindow.openAction.trigger()
    assert mainWindow.statusBar().currentMessage() == "File > Open selected"

    mainWindow.saveAction.trigger()
    assert mainWindow.statusBar().currentMessage() == "File > Save selected"


def testAboutTextContents(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    aboutText = mainWindow.buildAboutText()
    assert "RV Backup Helper" in aboutText
    assert "Editor: Francois Charette" in aboutText
    assert "AI Agent: Claude - Fable 5" in aboutText
    assert "Charette AI Group, LLC" in aboutText
