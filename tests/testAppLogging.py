"""Tests for sending the application's log to a file.

The point of the file is that a failure at the vehicle leaves a trace, so
these check what actually lands on disk rather than that a call was made.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pytest

from rvBackupHelper.appLogging import (
    configureLogging,
    installExceptionLogging,
)


@pytest.fixture(autouse=True)
def cleanRootLogger():
    """Leave the root logger exactly as it was found.

    Logging is global; a handler left behind writes into another test's file
    and the failure surfaces somewhere unrelated.
    """
    root = logging.getLogger()
    handlers = list(root.handlers)
    level = root.level
    hook = sys.excepthook
    yield
    for handler in list(root.handlers):
        if handler not in handlers:
            handler.close()
            root.removeHandler(handler)
    root.setLevel(level)
    sys.excepthook = hook


def testLogLinesReachTheFile(tmp_path: Path) -> None:
    path = configureLogging(tmp_path / "logs" / "app.log")

    logging.getLogger("rvBackupHelper.test").info("device %d opened", 3)

    assert path is not None
    assert "device 3 opened" in path.read_text(encoding="utf-8")


def testTheFolderIsCreatedIfMissing(tmp_path: Path) -> None:
    target = tmp_path / "not" / "there" / "app.log"

    path = configureLogging(target)

    assert path == target
    assert target.parent.is_dir()


def testConfiguringTwiceDoesNotDoubleEveryLine(tmp_path: Path) -> None:
    target = tmp_path / "app.log"
    configureLogging(target)
    configureLogging(target)

    logging.getLogger("rvBackupHelper.test").info("once please")

    written = target.read_text(encoding="utf-8")
    assert written.count("once please") == 1


def testAnUnopenableLogDoesNotStopTheApplication(tmp_path: Path) -> None:
    # A file where a directory needs to be: mkdir fails, and starting the
    # application anyway matters more than having somewhere to log.
    blocker = tmp_path / "blocked"
    blocker.write_text("not a directory", encoding="utf-8")

    assert configureLogging(blocker / "app.log") is None


def testUnhandledExceptionsAreRecorded(tmp_path: Path) -> None:
    target = tmp_path / "app.log"
    configureLogging(target)
    seen: list[str] = []
    sys.excepthook = lambda *args: seen.append(args[0].__name__)
    installExceptionLogging()

    try:
        raise ValueError("something went wrong in the field")
    except ValueError as exc:
        sys.excepthook(type(exc), exc, exc.__traceback__)

    written = target.read_text(encoding="utf-8")
    assert "Unhandled exception" in written
    assert "something went wrong in the field" in written
    # The previous hook still runs, so a terminal still shows the traceback.
    assert seen == ["ValueError"]


def testKeyboardInterruptIsNotLoggedAsAFault(tmp_path: Path) -> None:
    target = tmp_path / "app.log"
    configureLogging(target)
    sys.excepthook = lambda *args: None
    installExceptionLogging()

    exc = KeyboardInterrupt()
    sys.excepthook(KeyboardInterrupt, exc, None)

    assert "Unhandled exception" not in target.read_text(encoding="utf-8")
