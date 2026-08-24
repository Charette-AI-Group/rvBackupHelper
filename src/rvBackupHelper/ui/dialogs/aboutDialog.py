"""The About dialog, with the Donate button the sibling apps carry.

Modelled on the About dialog in pySPWB so the Charette AI Group applications
look like they come from the same place: the same credits block, the same
yellow Donate button, the same PayPal link.

A plain QDialog rather than QMessageBox.about, for the reason pySPWB found: a
message box places its buttons by *role*, and which side a non-standard button
lands on then varies with the platform style. Donate belongs on the left, away
from Close, on every platform.
"""

from __future__ import annotations

import datetime

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rvBackupHelper import appConfig

donateStyle = f"""
    QPushButton {{
        background-color: {appConfig.donateColour};
        color: {appConfig.donateTextColour};
        border: none;
        border-radius: 6px;
        padding: 6px 18px;
        font-weight: 600;
    }}
    QPushButton:hover, QPushButton:pressed {{
        background-color: {appConfig.donatePressedColour};
    }}
"""


def aboutHtml(year: int | None = None) -> str:
    """The dialog's contents, as rich text."""
    year = datetime.date.today().year if year is None else year
    return (
        f"<h3>{appConfig.appName}</h3>"
        f"<p>Version {appConfig.appVersion}</p>"
        f"<p>Editor: {appConfig.editorName}<br>"
        f"AI Agent: {appConfig.aiAgentName}</p>"
        f'<p>Source at <a href="{appConfig.repoUrl}">rvBackupHelper</a>.</p>'
        f"<p>&copy; {year} {appConfig.copyrightHolder}</p>"
    )


class AboutDialog(QDialog):
    """About, with Donate on the left and Close on the right."""

    def __init__(self, text: str | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"About {appConfig.appName}")
        # Read back by the caller after exec rather than connected to the
        # click, so the browser opens once this dialog has closed instead of
        # behind it.
        self.donateRequested = False

        layout = QVBoxLayout(self)

        self.aboutLabel = QLabel(aboutHtml() if text is None else text)
        self.aboutLabel.setTextFormat(Qt.TextFormat.RichText)
        self.aboutLabel.setMinimumWidth(420)
        self.aboutLabel.setWordWrap(True)
        self.aboutLabel.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextBrowserInteraction
        )
        self.aboutLabel.setOpenExternalLinks(True)
        layout.addWidget(self.aboutLabel)
        layout.addSpacing(8)

        self.donateButton = QPushButton("Donate")
        self.donateButton.setStyleSheet(donateStyle)
        self.donateButton.setCursor(Qt.CursorShape.PointingHandCursor)
        self.donateButton.clicked.connect(self.onDonateClicked)

        self.closeButton = QPushButton("Close")
        self.closeButton.clicked.connect(self.reject)
        # Enter closes the dialog. It must never be the thing that opens a
        # payment page, which is why Donate gives up its auto-default.
        self.closeButton.setDefault(True)
        self.closeButton.setAutoDefault(True)
        self.donateButton.setAutoDefault(False)

        buttons = QHBoxLayout()
        buttons.addWidget(self.donateButton)
        buttons.addStretch(1)
        buttons.addWidget(self.closeButton)
        layout.addLayout(buttons)

    def onDonateClicked(self) -> None:
        self.donateRequested = True
        self.accept()


def showAbout(parent: QWidget | None = None) -> bool:
    """Show the dialog; open the donation page if it was asked for.

    Returns whether the donation page was opened, so the caller can say so in
    its status bar.
    """
    dialog = AboutDialog(parent=parent)
    dialog.exec()
    if dialog.donateRequested:
        QDesktopServices.openUrl(QUrl(appConfig.donateUrl))
        return True
    return False
