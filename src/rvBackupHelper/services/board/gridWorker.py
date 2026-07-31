"""Background thread for board commands.

Each command opens the port, waits out the board's reset and reads a reply,
which takes a couple of seconds. That cannot happen on the GUI thread.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from rvBackupHelper.services.board.gridService import BoardError, GridService

logger = logging.getLogger(__name__)


class GridWorker(QThread):
    """Asks the board to show or hide its grid, once."""

    # The board's own reply, so the UI reports what happened rather than what
    # it assumed would happen.
    finishedWithReply = Signal(bool, str)
    errorOccurred = Signal(str)

    def __init__(
        self,
        visible: bool,
        gridService: GridService | None = None,
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)
        self.visible = visible
        self.gridService = gridService or GridService()

    def run(self) -> None:
        try:
            reply = self.gridService.setGridVisible(self.visible)
        except BoardError as exc:
            logger.warning("Grid command failed: %s", exc)
            self.errorOccurred.emit(str(exc))
            return
        self.finishedWithReply.emit(self.visible, reply)
