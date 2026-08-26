r"""Tests for splitting a failure between the status bar and a dialog."""

from __future__ import annotations

from rvBackupHelper.ui.dialogs.errorDialog import (
    detailOf,
    headlineOf,
    statusHeadlineLimit,
)

# The message that actually got cut, mid-word, in the status bar.
boardSilent = (
    "The board did not answer. The usual cause is a sketch built against the stock "
    "TVout instead of the Video Experimenter fork: nothing handles the input capture "
    "interrupt the overlay needs."
)


def testAShortMessageIsItsOwnHeadline() -> None:
    assert headlineOf("No Arduino found.") == "No Arduino found."


def testTheFirstLineIsTheHeadlineWhenThereAreSeveral() -> None:
    message = "arduino-cli failed:\nPlatform not installed\nData directory: C:\\X"

    assert headlineOf(message) == "arduino-cli failed:"


def testALongSingleLineIsCutAtASentenceNotMidWord() -> None:
    """Cut mid-word, a headline reads as the whole message and misleads."""
    headline = headlineOf(boardSilent)

    assert headline == "The board did not answer."
    assert len(headline) <= statusHeadlineLimit


def testAHeadlineThatCannotBeCutCleanlyIsMarkedAsTruncated() -> None:
    message = "x" * (statusHeadlineLimit * 2)

    headline = headlineOf(message)

    assert len(headline) <= statusHeadlineLimit
    assert headline.endswith("…")


def testTheDetailIsWhateverTheHeadlineDidNotSay() -> None:
    message = "arduino-cli failed:\nPlatform not installed\nData directory: C:\\X"

    detail = detailOf(message, headlineOf(message))

    assert detail.startswith("Platform not installed")
    assert "Data directory" in detail


def testNothingIsLostWhenTheHeadlineIsCutAtASentence() -> None:
    """Headline plus detail is the message, with no word dropped between them."""
    headline = headlineOf(boardSilent)
    detail = detailOf(boardSilent, headline)

    assert f"{headline} {detail}" == boardSilent


def testAnEllipsisedHeadlineLeavesTheWholeMessageInTheDialog() -> None:
    """It said only part of a word, so all of it still needs saying."""
    message = "x" * (statusHeadlineLimit * 2)

    assert detailOf(message, headlineOf(message)) == message


def testAMessageWithNoDetailLeavesTheDialogWithNothingExtra() -> None:
    assert detailOf("No Arduino found.", "No Arduino found.") == ""


def testBlankLinesDoNotBecomeTheHeadline() -> None:
    assert headlineOf("\n\nUpload failed\nbecause of a thing") == "Upload failed"
