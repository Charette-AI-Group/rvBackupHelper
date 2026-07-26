"""Application entry point — wiring only."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from rvBackupHelper import appConfig
from rvBackupHelper.ui.mainWindow import MainWindow


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName(appConfig.appName)
    app.setApplicationVersion(appConfig.appVersion)
    app.setOrganizationName(appConfig.organizationName)

    mainWindow = MainWindow()
    mainWindow.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
