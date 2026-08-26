"""Background thread for the toolchain check.

The check compiles a sketch, which takes seconds rather than milliseconds. On
the interface thread that is a frozen window, and a frozen window during a
diagnostic reads as another fault to investigate.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from rvBackupHelper.services.board.toolchainService import (
    ToolchainReport,
    ToolchainService,
)

logger = logging.getLogger(__name__)


class ToolchainWorker(QThread):
    """Runs one toolchain check and hands back what it found."""

    # ToolchainReport, passed as object: Signal cannot carry a dataclass type.
    checked = Signal(object)

    def __init__(
        self,
        toolchainService: ToolchainService | None = None,
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)
        self.toolchainService = toolchainService or ToolchainService()

    def run(self) -> None:
        report: ToolchainReport = self.toolchainService.check()
        logger.info("Toolchain check: %s", report.headline)
        self.checked.emit(report)
