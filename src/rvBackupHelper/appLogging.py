"""Sending the application's log to a file.

The services log their decisions - which device was opened, which port a
command went to, why an upload failed - but `runApp.cmd` starts pythonw,
which has no console. Every one of those lines was being discarded, so a
failure at the vehicle left nothing to read afterwards and had to be
reproduced to be understood. A file turns that into a five-second look.

Configured here rather than in main() so tests can drive it directly, and so
the entry point stays wiring.
"""

from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType

from rvBackupHelper import appConfig

logger = logging.getLogger(__name__)


def configureLogging(logPath: Path | None = None) -> Path | None:
    """Send INFO and above to a rotating file. Returns the path, or None.

    Returns None rather than raising when the file cannot be opened. Losing
    the log is a nuisance; refusing to start the application because of it
    would be a far worse trade, and the case that matters - a read-only or
    missing folder - is exactly the sort of thing that happens in the field.
    """
    path = Path(logPath) if logPath is not None else appConfig.logPath
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Idempotent: called twice (tests, or a restart in-process) it must not
    # stack handlers and write every line several times over.
    for existing in root.handlers:
        if getattr(existing, "rvbhLogPath", None) == str(path):
            return path

    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            path,
            maxBytes=appConfig.logMaxBytes,
            backupCount=appConfig.logBackupCount,
            encoding="utf-8",
        )
    except OSError:
        # No file, but the console handler below may still be of use.
        addConsoleHandler(root)
        return None

    handler.setFormatter(logging.Formatter(appConfig.logFormat))
    handler.rvbhLogPath = str(path)
    root.addHandler(handler)
    addConsoleHandler(root)
    return path


def addConsoleHandler(root: logging.Logger) -> None:
    """Also log to stderr when there is one.

    Under pythonw sys.stderr is None, so this is skipped; run from a terminal
    and the same lines appear there as well.
    """
    if sys.stderr is None:
        return
    if any(getattr(h, "rvbhConsole", False) for h in root.handlers):
        return
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(appConfig.logFormat))
    handler.rvbhConsole = True
    root.addHandler(handler)


def installExceptionLogging() -> None:
    """Record unhandled exceptions instead of losing them.

    A GUI with no console swallows a traceback completely: the window simply
    goes, with nothing to show for it. Logging first keeps the default
    behaviour intact for anyone running from a terminal.
    """
    previous = sys.excepthook

    def handler(
        kind: type[BaseException],
        value: BaseException,
        traceback: TracebackType | None,
    ) -> None:
        # Ctrl-C is a deliberate stop, not a fault worth a traceback.
        if not issubclass(kind, KeyboardInterrupt):
            logging.getLogger("rvBackupHelper").critical(
                "Unhandled exception", exc_info=(kind, value, traceback)
            )
        previous(kind, value, traceback)

    sys.excepthook = handler
