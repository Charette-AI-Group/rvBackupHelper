"""Smoke tests for the main window."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QFileDialog

from rvBackupHelper import appConfig
from rvBackupHelper.services.board.hardwareService import (
    HardwareReport,
    HardwareService,
)
from rvBackupHelper.services.board.toolchainService import (
    ToolchainReport,
    ToolchainService,
)
from rvBackupHelper.services.settingsService import SettingsService
from rvBackupHelper.ui.capture.captureView import CaptureView
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

    helpItems = [a.text() for a in mainWindow.helpMenu.actions() if not a.isSeparator()]
    # Diagnostics first, hardware before toolchain: the cheaper, earlier question.
    assert helpItems == [
        "Check &Hardware...",
        "Check &Toolchain...",
        "User &Manual...",
        "&About",
    ]
    assert any(a.isSeparator() for a in mainWindow.helpMenu.actions())


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


def testPublishedManualIsPreferredWhenReachable(qtbot, monkeypatch) -> None:
    """GitHub renders the screenshots; a local .md in an editor does not."""
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    opened = openedUrls(monkeypatch)

    mainWindow.openManual(publishedIsReachable=True)

    assert opened == [appConfig.manualUrl]
    assert "opening in your browser" in mainWindow.statusBar().currentMessage()


def testTheLocalCopyIsUsedWhenThereIsNoConnection(qtbot, monkeypatch) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    opened = openedUrls(monkeypatch)

    mainWindow.openManual(publishedIsReachable=False)

    assert len(opened) == 1
    assert opened[0].startswith("file:")
    assert opened[0].endswith("README.md")
    assert "No connection" in mainWindow.statusBar().currentMessage()


def testAnUnreachableSiteFallsThroughToTheLocalCopy(
    qtbot, monkeypatch, tmp_path
) -> None:
    """Reported reachable, but the browser still refused to launch."""
    local = tmp_path / "README.md"
    local.write_text("# manual", encoding="utf-8")
    monkeypatch.setattr(appConfig, "manualPath", local)
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    attempted: list[str] = []

    def openUrl(url):
        attempted.append(url.toString())
        return url.isLocalFile()

    monkeypatch.setattr(
        "rvBackupHelper.ui.mainWindow.QDesktopServices.openUrl", openUrl
    )

    mainWindow.openManual(publishedIsReachable=True)

    assert len(attempted) == 2
    assert attempted[0] == appConfig.manualUrl
    assert attempted[1].startswith("file:")


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

    mainWindow.openManual(publishedIsReachable=False)

    assert appConfig.manualUrl in shown[0]
    assert str(appConfig.manualPath) in shown[0]


def testTheCheckRunsOffTheInterfaceThread(qtbot, monkeypatch) -> None:
    """A network probe can hang until its timeout; the window must not."""
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    openedUrls(monkeypatch)

    with qtbot.waitSignal(mainWindow.manualAction.changed, timeout=5000):
        mainWindow.onHelpManual()
    # Disabled while the probe is in flight, so it cannot be started twice.
    assert not mainWindow.manualAction.isEnabled()

    assert mainWindow.manualWorker is not None
    mainWindow.manualWorker.wait(5000)
    qtbot.waitUntil(lambda: mainWindow.manualWorker is None, timeout=5000)
    assert mainWindow.manualAction.isEnabled()


def testAViewFailureOpensADialogAndKeepsTheBarShort(qtbot, monkeypatch) -> None:
    """The bar is for status. A failure that only fits half-way into it reads

    as the whole failure, which is how a diagnosis got lost twice.
    """
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        MainWindow, "showError", lambda self, title, message: shown.append((title, message))
    )
    message = (
        "The board did not answer. Something long enough that the status bar "
        "would otherwise cut it off part of the way through a word, hiding the "
        "part that says what to do about it."
    )

    mainWindow.captureView.reportError("Arduino", message)

    assert shown == [("Arduino", message)]
    assert mainWindow.statusBar().currentMessage() == "The board did not answer."


def testBothTabsReportFailuresTheSameWay(qtbot, monkeypatch) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    shown: list[tuple[str, str]] = []
    monkeypatch.setattr(
        MainWindow, "showError", lambda self, title, message: shown.append((title, message))
    )

    mainWindow.captureView.reportError("Capture failed", "the device went away")
    mainWindow.calibrationView.reportError("Upload failed", "the board went away")

    assert shown == [
        ("Capture failed", "the device went away"),
        ("Upload failed", "the board went away"),
    ]


def testCheckingTheToolchainRunsOffTheInterfaceThread(qtbot, monkeypatch) -> None:
    """It compiles a sketch, which is seconds of frozen window otherwise."""
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    report = ToolchainReport(ok=True, headline="Ready.", details="arduino-cli: somewhere")
    monkeypatch.setattr(ToolchainService, "check", lambda self: report)
    monkeypatch.setattr(MainWindow, "showToolchainReport", lambda self, report: None)

    with qtbot.waitSignal(mainWindow.toolchainAction.changed, timeout=5000):
        mainWindow.onCheckToolchain()
    # Disabled while the compile is in flight, so it cannot be started twice.
    assert not mainWindow.toolchainAction.isEnabled()

    assert mainWindow.toolchainWorker is not None
    mainWindow.toolchainWorker.wait(5000)
    qtbot.waitUntil(lambda: mainWindow.toolchainWorker is None, timeout=5000)
    assert mainWindow.toolchainAction.isEnabled()


def testTheVerdictReachesBothTheStatusBarAndADialog(qtbot, monkeypatch) -> None:
    """The status bar shows one line and truncates it; the detail has to have

    somewhere else to go, because the part that identifies the wrong directory
    is exactly the part a one-line bar drops.
    """
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    report = ToolchainReport(
        ok=False,
        headline="The toolchain is not ready.",
        details=r"data dir: C:\elsewhere",
    )
    shown: list[ToolchainReport] = []
    monkeypatch.setattr(
        MainWindow, "showToolchainReport", lambda self, report: shown.append(report)
    )

    mainWindow.onToolchainChecked(report)

    assert mainWindow.statusBar().currentMessage() == "The toolchain is not ready."
    assert shown == [report]


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


def testCheckingHardwareRunsOffTheInterfaceThread(qtbot, monkeypatch) -> None:
    """Starting PowerShell and walking the USB tree takes about a second."""
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    report = HardwareReport(ok=True, headline="Ready.", details="Arduino Uno R3 on COM3.")
    monkeypatch.setattr(HardwareService, "check", lambda self: report)
    monkeypatch.setattr(MainWindow, "showHardwareReport", lambda self, report: None)

    with qtbot.waitSignal(mainWindow.hardwareAction.changed, timeout=5000):
        mainWindow.onCheckHardware()
    assert not mainWindow.hardwareAction.isEnabled()

    assert mainWindow.hardwareWorker is not None
    mainWindow.hardwareWorker.wait(5000)
    qtbot.waitUntil(lambda: mainWindow.hardwareWorker is None, timeout=5000)
    assert mainWindow.hardwareAction.isEnabled()


def testTheHardwareVerdictReachesTheBarAndADialog(qtbot, monkeypatch) -> None:
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)
    report = HardwareReport(
        ok=False,
        headline="No Arduino found.",
        details="Plug the board in by USB.",
    )
    shown: list[HardwareReport] = []
    monkeypatch.setattr(
        MainWindow, "showHardwareReport", lambda self, report: shown.append(report)
    )

    mainWindow.onHardwareChecked(report)

    assert mainWindow.statusBar().currentMessage() == "No Arduino found."
    assert shown == [report]


def testAnUploadHandsTheGridBackToTheCaptureTab(qtbot, monkeypatch) -> None:
    """The tabs are wired for it, because the board keeps a blanked grid in
    EEPROM and would otherwise come up with no lines in the vehicle."""
    called: list[bool] = []
    # Patched before the window is built, so the connection binds to this.
    monkeypatch.setattr(
        CaptureView, "onSketchUploaded", lambda self: called.append(True)
    )
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    mainWindow.calibrationView.onUploadFinished("Sketch uses 12000 bytes")

    assert called == [True]
