"""User preferences that outlive a session, backed by QSettings."""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QSettings

from rvBackupHelper import appConfig

logger = logging.getLogger(__name__)

recordingsDirKey = "paths/recordingsDir"
lastSketchKey = "paths/lastSketch"


class SettingsService:
    """Reads and writes stored preferences.

    A default QSettings resolves through the organization and application
    names set in main.py. Tests inject their own file-backed instance so they
    never touch the real user settings.
    """

    def __init__(self, settings: QSettings | None = None) -> None:
        self.settings = settings if settings is not None else QSettings()

    def recordingsDir(self) -> Path:
        """Where clips are written; the bundled default until changed."""
        stored = self.settings.value(recordingsDirKey, "", type=str)
        return Path(stored) if stored else appConfig.recordingsDir

    def setRecordingsDir(self, path: Path) -> None:
        self.settings.setValue(recordingsDirKey, str(path))
        self.settings.sync()
        logger.info("Recordings folder set to %s", path)

    def lastSketchPath(self) -> Path | None:
        """The sketch generated most recently, so Upload can offer it again.

        None when nothing has been generated yet. Whether the file still
        exists is the caller's business: it may have been renamed or deleted
        since.
        """
        stored = self.settings.value(lastSketchKey, "", type=str)
        return Path(stored) if stored else None

    def setLastSketchPath(self, path: Path) -> None:
        self.settings.setValue(lastSketchKey, str(path))
        self.settings.sync()
        logger.info("Last generated sketch is %s", path)
