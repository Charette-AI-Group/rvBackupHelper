"""Background thread for the manual reachability check.

A network probe can hang until its timeout, which must not happen on the
interface thread for something as small as a menu click.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from rvBackupHelper.services.manual.manualService import ManualService

logger = logging.getLogger(__name__)


class ManualWorker(QThread):
    """Reports whether the published manual is reachable."""

    # True when the online copy answered; False to use the local one.
    resolved = Signal(bool)

    def __init__(
        self,
        manualService: ManualService | None = None,
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)
        self.manualService = manualService or ManualService()

    def run(self) -> None:
        self.resolved.emit(self.manualService.isOnlineCopyAvailable())
