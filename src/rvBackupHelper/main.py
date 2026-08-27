"""Application entry point — wiring only."""

from __future__ import annotations

import logging
import sys

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from rvBackupHelper import appConfig
from rvBackupHelper.appLogging import configureLogging, installExceptionLogging
from rvBackupHelper.services.userDataService import ensureUserData
from rvBackupHelper.ui.mainWindow import MainWindow


def main() -> int:
    # Before anything else, so that whatever follows is recorded.
    logPath = configureLogging()
    installExceptionLogging()
    logging.getLogger(__name__).info(
        "%s %s starting; logging to %s",
        appConfig.appName,
        appConfig.appVersion,
        logPath or "nowhere - the log file could not be opened",
    )
    # After logging, so that what it does is recorded, and before the window,
    # so the folders exist by the time anything asks for them.
    for created in ensureUserData():
        logging.getLogger(__name__).info("Created %s", created)

    app = QApplication(sys.argv)
    app.setApplicationName(appConfig.appName)
    app.setApplicationVersion(appConfig.appVersion)
    app.setOrganizationName(appConfig.organizationName)
    # Checked rather than assumed: a missing icon is not worth refusing to
    # start over, and Qt would otherwise hand back an empty one silently.
    if appConfig.iconPath.exists():
        app.setWindowIcon(QIcon(str(appConfig.iconPath)))
    else:
        logging.getLogger(__name__).warning(
            "No application icon at %s; run tools/makeIcons.py", appConfig.iconPath
        )

    mainWindow = MainWindow()
    mainWindow.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
