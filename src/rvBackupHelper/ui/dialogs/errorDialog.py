r"""One place failures are shown, because the status bar is not that place.

The bar holds a single line and elides whatever will not fit. The part of a
failure that says *why* sits at the end - the data directory, the thing to
check next - so the bar drops exactly the half worth reading. That has now
hidden a diagnosis three times: the upload failure that cost a day on the
laptop, and the board-did-not-answer message that was cut at "the Video
Experimenter fc".

So a failure opens a dialog carrying the whole text, selectable so it can be
copied into a message to somebody else, and the bar gets a short honest
headline. The bar is for status; this is for failures.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox, QWidget

logger = logging.getLogger(__name__)

# Roughly what fits before the bar starts eliding at the default window width.
statusHeadlineLimit = 100


def headlineOf(message: str) -> str:
    """The most the status bar can hold without lying by omission.

    The first line if it is short enough, else its first sentence, else a
    plainly truncated version - anything rather than a line that stops
    mid-word and looks like the whole message.
    """
    first = next((line.strip() for line in message.splitlines() if line.strip()), "")
    if len(first) <= statusHeadlineLimit:
        return first
    sentence, separator, _ = first.partition(". ")
    if separator and len(sentence) < statusHeadlineLimit:
        return f"{sentence}."
    return f"{first[: statusHeadlineLimit - 1].rstrip()}…"


def detailOf(message: str, headline: str) -> str:
    """Everything the headline did not already say."""
    text = message.strip()
    if headline and text.startswith(headline):
        return text[len(headline) :].strip()
    # The headline was shortened rather than taken whole, so nothing has been
    # said yet and all of it still needs somewhere to go.
    return text


def showError(parent: QWidget | None, title: str, message: str) -> None:
    """A modal box with the whole failure in it, and one button to dismiss it."""
    logger.warning("%s: %s", title, message)
    headline = headlineOf(message)
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setWindowTitle(title)
    box.setText(headline)
    detail = detailOf(message, headline)
    if detail:
        box.setInformativeText(detail)
    box.setStandardButtons(QMessageBox.StandardButton.Ok)
    # Paths and compiler output: worth copying, not retyping.
    box.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
    box.exec()
