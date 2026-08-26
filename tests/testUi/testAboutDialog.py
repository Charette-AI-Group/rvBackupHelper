"""Tests for the About dialog and its Donate button."""

from __future__ import annotations

from PySide6.QtWidgets import QDialog

from rvBackupHelper import appConfig
from rvBackupHelper.ui.dialogs.aboutDialog import AboutDialog, aboutHtml, showAbout


def testAboutTextCarriesTheCredits() -> None:
    text = aboutHtml(year=2026)

    assert "RV Backup Helper" in text
    assert "Editor: Francois Charette, PhD" in text
    assert "AI Agent: Claude - Opus 5" in text
    assert "2026 Charette AI Group, LLC" in text
    assert appConfig.repoUrl in text


def testAboutTextSaysWhereTheUsersFilesAre() -> None:
    """Obvious in a checkout; unguessable once installed under AppData."""
    text = aboutHtml(year=2026)

    assert str(appConfig.userDataDir) in text
    assert appConfig.userDataDir.as_uri() in text


def testDialogStartsWithNoDonationRequested(qtbot) -> None:
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    assert not dialog.donateRequested
    assert dialog.donateButton.text() == "Donate"


def testDonateRecordsTheRequestAndClosesTheDialog(qtbot) -> None:
    """The page opens after the dialog closes, not behind it."""
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    dialog.donateButton.click()

    assert dialog.donateRequested
    assert dialog.result() == QDialog.DialogCode.Accepted


def testCloseLeavesNoDonationRequested(qtbot) -> None:
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    dialog.closeButton.click()

    assert not dialog.donateRequested


def testEnterCannotOpenThePaymentPage(qtbot) -> None:
    """Close takes the default so Return never triggers Donate."""
    dialog = AboutDialog()
    qtbot.addWidget(dialog)

    assert dialog.closeButton.isDefault()
    assert dialog.closeButton.autoDefault()
    assert not dialog.donateButton.autoDefault()


def testShowAboutReportsWhetherItOpenedTheDonationPage(qtbot, monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        "rvBackupHelper.ui.dialogs.aboutDialog.QDesktopServices.openUrl",
        lambda url: opened.append(url.toString()) or True,
    )

    # Donate pressed.
    monkeypatch.setattr(AboutDialog, "exec", lambda self: self.onDonateClicked())
    assert showAbout() is True
    assert opened == [appConfig.donateUrl]

    # Closed without donating.
    opened.clear()
    monkeypatch.setattr(AboutDialog, "exec", lambda self: None)
    assert showAbout() is False
    assert opened == []
