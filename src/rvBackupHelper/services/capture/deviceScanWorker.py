"""Background thread for device discovery.

Probing eight indices means opening and closing eight devices, which takes
seconds on Windows. That cannot happen on the GUI thread.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QThread, Signal

from rvBackupHelper.services.capture.cameraService import CameraService

logger = logging.getLogger(__name__)


class DeviceScanWorker(QThread):
    """Probes capture device indices and reports what answered."""

    # Payload is a list[CameraDevice].
    devicesFound = Signal(object)
    errorOccurred = Signal(str)

    def __init__(
        self,
        cameraService: CameraService | None = None,
        parent: object | None = None,
    ) -> None:
        super().__init__(parent)
        self.cameraService = cameraService or CameraService()

    def run(self) -> None:
        try:
            devices = self.cameraService.listDevices()
        except Exception as exc:  # a bad backend must not take the app down
            logger.exception("Device scan failed")
            self.errorOccurred.emit(str(exc))
            return
        self.devicesFound.emit(devices)
