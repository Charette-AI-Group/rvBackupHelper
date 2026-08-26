"""Background thread for the hardware check.

Starting PowerShell and enumerating USB devices takes about a second, which is
a frozen window if it happens on the interface thread - and a frozen window
during a diagnostic reads as another fault to investigate.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from rvBackupHelper.services.board.hardwareService import (
    HardwareReport,
    HardwareService,
)

logger = logging.getLogger(__name__)


class HardwareWorker(QThread):
    """Runs one hardware check and hands back what it found."""

    # HardwareReport, passed as object: Signal cannot carry a dataclass type.
    checked = Signal(object)

    def __init__(
        self,
        hardwareService: HardwareService | None = None,
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)
        self.hardwareService = hardwareService or HardwareService()

    def run(self) -> None:
        report: HardwareReport = self.hardwareService.check()
        logger.info("Hardware check: %s", report.headline)
        self.checked.emit(report)
