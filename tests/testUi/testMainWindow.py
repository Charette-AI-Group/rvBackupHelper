"""Smoke tests for the main window."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QFileDialog

from rvBackupHelper import appConfig
from rvBackupHelper.services.settingsService import SettingsService
from rvBackupHelper.ui.mainWindow import MainWindow


@pytest.fixture
def settingsService(tmp_path: Path) -> SettingsService:
    """Isolated settings so tests never read or write real preferences."""
    return SettingsService(
        QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    )


def testMainWindowOpens(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    mainWindow.show()

    assert mainWindow.isVisible()
    assert mainWindow.windowTitle() == "RV Backup Helper"
    assert mainWindow.statusBar().currentMessage() == "Ready"


def testBothTabsArePresent(qtbot) -> None:
    """Calibrate embeds the clip browser, so a separate Review tab is redundant."""
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    tabTitles = [mainWindow.tabs.tabText(i) for i in range(mainWindow.tabs.count())]
    assert tabTitles == ["Capture", "Calibrate"]


def testMenuBarStructure(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    menuTitles = [action.text() for action in mainWindow.menuBar().actions()]
    assert menuTitles == ["&File", "&Help"]

    fileItems = [a.text() for a in mainWindow.fileMenu.actions() if not a.isSeparator()]
    assert fileItems == ["&Open Clip...", "&Recordings Folder...", "E&xit"]
    assert any(a.isSeparator() for a in mainWindow.fileMenu.actions())

    helpItems = [a.text() for a in mainWindow.helpMenu.actions()]
    assert helpItems == ["User &Manual...", "&About"]


def testViewStatusMessagesReachTheStatusBar(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    mainWindow.captureView.statusMessage.emit("Capturing.")
    assert mainWindow.statusBar().currentMessage() == "Capturing."

    mainWindow.calibrationView.statusMessage.emit("Marked 3 ft at scan line 412.")
    assert mainWindow.statusBar().currentMessage() == "Marked 3 ft at scan line 412."


def testRecordingsFolderIsShownPermanentlyInTheStatusBar(
    qtbot, settingsService, tmp_path: Path
) -> None:
    chosen = tmp_path / "clips"
    settingsService.setRecordingsDir(chosen)

    mainWindow = MainWindow(settingsService=settingsService)
    qtbot.addWidget(mainWindow)

    assert "Recordings:" in mainWindow.recordingsLabel.text()
    assert mainWindow.recordingsLabel.toolTip() == str(chosen)

    # A transient status message must not wipe the location out.
    mainWindow.showStatus("Capturing.")
    assert mainWindow.statusBar().currentMessage() == "Capturing."
    assert "Recordings:" in mainWindow.recordingsLabel.text()


def testStoredRecordingsFolderReachesEveryTabOnStartup(
    qtbot, settingsService, tmp_path: Path
) -> None:
    chosen = tmp_path / "storedClips"
    settingsService.setRecordingsDir(chosen)

    mainWindow = MainWindow(settingsService=settingsService)
    qtbot.addWidget(mainWindow)

    assert mainWindow.captureView.recordingsDir == chosen
    assert mainWindow.calibrationView.clipBrowser.recordingsDir == chosen


def testChoosingAFolderPersistsItAndUpdatesEverything(
    qtbot, settingsService, tmp_path: Path, monkeypatch
) -> None:
    mainWindow = MainWindow(settingsService=settingsService)
    qtbot.addWidget(mainWindow)
    chosen = tmp_path / "newClips"
    chosen.mkdir()
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", staticmethod(lambda *args: str(chosen))
    )

    mainWindow.onChooseRecordingsDir()

    assert mainWindow.recordingsDir == chosen
    assert mainWindow.captureView.recordingsDir == chosen
    assert mainWindow.calibrationView.clipBrowser.recordingsDir == chosen
    assert mainWindow.recordingsLabel.toolTip() == str(chosen)
    assert str(chosen) in mainWindow.statusBar().currentMessage()
    # Persisted, not just held in memory.
    assert settingsService.recordingsDir() == chosen


def testCancellingTheFolderDialogChangesNothing(
    qtbot, settingsService, tmp_path: Path, monkeypatch
) -> None:
    mainWindow = MainWindow(settingsService=settingsService)
    qtbot.addWidget(mainWindow)
    before = mainWindow.recordingsDir
    monkeypatch.setattr(
        QFileDialog, "getExistingDirectory", staticmethod(lambda *args: "")
    )

    mainWindow.onChooseRecordingsDir()

    assert mainWindow.recordingsDir == before
    assert mainWindow.captureView.recordingsDir == before
    assert mainWindow.calibrationView.clipBrowser.recordingsDir == before


def testLongFolderPathIsElidedButFullyAvailableOnHover(
    qtbot, settingsService, tmp_path: Path
) -> None:
    deep = tmp_path.joinpath(*[f"averyLongFolderNameNumber{n}" for n in range(12)])
    settingsService.setRecordingsDir(deep)

    mainWindow = MainWindow(settingsService=settingsService)
    qtbot.addWidget(mainWindow)

    assert "…" in mainWindow.recordingsLabel.text()
    assert mainWindow.recordingsLabel.toolTip() == str(deep)


def openedUrls(monkeypatch) -> list[str]:
    """Collect what the app asked the desktop to open, and say it worked."""
    opened: list[str] = []
    monkeypatch.setattr(
        "rvBackupHelper.ui.mainWindow.QDesktopServices.openUrl",
        lambda url: opened.append(url.toString()) or True,
    )
    return opened


def testManualPrefersTheCopyInTheCheckout(qtbot, monkeypatch, tmp_path) -> None:
    """No network and no GitHub login needed, which matters: the repo is private."""
    local = tmp_path / "README.md"
    local.write_text("# manual", encoding="utf-8")
    monkeypatch.setattr(appConfig, "manualPath", local)
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    opened = openedUrls(monkeypatch)

    mainWindow.manualAction.trigger()

    assert len(opened) == 1
    assert opened[0].startswith("file:")
    assert opened[0].endswith("README.md")
    assert str(local) in mainWindow.statusBar().currentMessage()


def testManualFallsBackOnlineWhenThereIsNoCheckout(
    qtbot, monkeypatch, tmp_path
) -> None:
    monkeypatch.setattr(appConfig, "manualPath", tmp_path / "absent" / "README.md")
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    opened = openedUrls(monkeypatch)

    mainWindow.manualAction.trigger()

    assert opened == [appConfig.manualUrl]
    assert "manual is opening" in mainWindow.statusBar().currentMessage()


def testManualFallsBackOnlineWhenNothingOpensMarkdown(
    qtbot, monkeypatch, tmp_path
) -> None:
    """A .md with no file association fails to open; the web copy still works."""
    local = tmp_path / "README.md"
    local.write_text("# manual", encoding="utf-8")
    monkeypatch.setattr(appConfig, "manualPath", local)
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    attempted: list[str] = []

    def openUrl(url):
        attempted.append(url.toString())
        return not url.isLocalFile()

    monkeypatch.setattr(
        "rvBackupHelper.ui.mainWindow.QDesktopServices.openUrl", openUrl
    )

    mainWindow.manualAction.trigger()

    assert len(attempted) == 2
    assert attempted[0].startswith("file:")
    assert attempted[1] == appConfig.manualUrl
    assert "manual is opening" in mainWindow.statusBar().currentMessage()


def testManualShowsBothAddressesWhenNothingOpens(qtbot, monkeypatch) -> None:
    """Leaving the user with nothing is worse than making them copy a URL."""
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    monkeypatch.setattr(
        "rvBackupHelper.ui.mainWindow.QDesktopServices.openUrl", lambda url: False
    )
    shown: list[str] = []
    monkeypatch.setattr(
        "rvBackupHelper.ui.mainWindow.QMessageBox.information",
        lambda parent, title, text: shown.append(text),
    )

    mainWindow.onHelpManual()

    assert str(appConfig.manualPath) in shown[0]
    assert appConfig.manualUrl in shown[0]


def testManualHasTheStandardHelpShortcut(qtbot) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    assert mainWindow.manualAction.shortcut() == QKeySequence.StandardKey.HelpContents


def testAboutOpensTheDialogAndReportsADonation(qtbot, monkeypatch) -> None:
    """The About text itself is covered in testAboutDialog."""
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    monkeypatch.setattr(
        "rvBackupHelper.ui.mainWindow.showAbout", lambda parent: True
    )

    mainWindow.onHelpAbout()

    assert "donation page" in mainWindow.statusBar().currentMessage()
