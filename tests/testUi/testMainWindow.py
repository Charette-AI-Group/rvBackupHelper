"""Smoke tests for the main window."""

from __future__ import annotations

from rvBackupHelper.ui.mainWindow import MainWindow


def testMainWindowOpens(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    mainWindow.show()

    assert mainWindow.isVisible()
    assert mainWindow.windowTitle() == "RV Backup Helper"
    assert mainWindow.statusBar().currentMessage() == "Ready"


def testCaptureAndReviewTabsArePresent(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    tabTitles = [mainWindow.tabs.tabText(i) for i in range(mainWindow.tabs.count())]
    assert tabTitles == ["Capture", "Review"]


def testMenuBarStructure(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    menuTitles = [action.text() for action in mainWindow.menuBar().actions()]
    assert menuTitles == ["&File", "&Help"]

    fileItems = [a.text() for a in mainWindow.fileMenu.actions() if not a.isSeparator()]
    assert fileItems == ["&Open Clip...", "E&xit"]
    assert any(a.isSeparator() for a in mainWindow.fileMenu.actions())

    assert [a.text() for a in mainWindow.helpMenu.actions()] == ["&About"]


def testViewStatusMessagesReachTheStatusBar(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    mainWindow.captureView.statusMessage.emit("Capturing.")
    assert mainWindow.statusBar().currentMessage() == "Capturing."

    mainWindow.reviewView.statusMessage.emit("Opened clip.avi")
    assert mainWindow.statusBar().currentMessage() == "Opened clip.avi"


def testAboutTextContents(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    aboutText = mainWindow.buildAboutText()
    assert "RV Backup Helper" in aboutText
    assert "Editor: Francois Charette" in aboutText
    assert "AI Agent: Claude - Fable 5" in aboutText
    assert "Charette AI Group, LLC" in aboutText
