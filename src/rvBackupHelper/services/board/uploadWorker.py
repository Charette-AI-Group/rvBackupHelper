"""Background thread for uploading a sketch.

A cold compile plus the upload and verify takes tens of seconds, which cannot
happen on the GUI thread.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from rvBackupHelper.services.board.uploadService import UploadError, UploadService

logger = logging.getLogger(__name__)


class UploadWorker(QThread):
    """Compiles and flashes one sketch, once."""

    # arduino-cli's own size summary, so the UI reports what actually happened.
    finishedWithSummary = Signal(str)
    errorOccurred = Signal(str)

    def __init__(
        self,
        sketchPath: Path,
        uploadService: UploadService | None = None,
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)
        self.sketchPath = sketchPath
        self.uploadService = uploadService or UploadService()

    def run(self) -> None:
        try:
            summary = self.uploadService.upload(self.sketchPath)
        except UploadError as exc:
            logger.warning("Upload failed: %s", exc)
            self.errorOccurred.emit(str(exc))
            return
        self.finishedWithSummary.emit(summary)
