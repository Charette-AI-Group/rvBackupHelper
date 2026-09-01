r"""Redraw the manual's screenshots that need nothing but the application.

The About box carries the version and the Calibrate tab carries its controls,
so both go stale on their own - the manual sat on 0.1.0 and on a Calibrate tab
that predated two changes without anybody noticing. Regenerating them is a
command rather than a memory of which windows to arrange.

    .venv\Scripts\python.exe tools\makeManualShots.py

Only the shots that need no footage. calibrate-clip-open, calibrate-complete
and the Capture ones show a real clip and a real grabber; those still have to
be taken at the RV, by hand.
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

projectRoot = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(projectRoot / "src"))

from rvBackupHelper import appConfig  # noqa: E402
from rvBackupHelper.ui.dialogs.aboutDialog import AboutDialog  # noqa: E402
from rvBackupHelper.ui.mainWindow import MainWindow  # noqa: E402

imagesDir = projectRoot / "docs" / "manual" / "images"
# What the committed window shot is, so a redraw drops in rather than
# reflowing the manual around a different shape. The dialog is left to its
# own sizeHint: forcing it wider only pads it with dead space.
windowSize = (1920, 1200)


def save(widget, path: Path, application: QApplication) -> None:
    application.processEvents()
    shot = widget.grab()
    shot.save(str(path), "PNG")
    print(f"  {path.relative_to(projectRoot)}  {shot.width()}x{shot.height()}")


def main() -> int:
    application = QApplication(sys.argv)

    print("Redrawing:")

    window = MainWindow()
    # grab() renders at the display's device ratio, so ask for the logical
    # size that lands on the committed one - sharp at whatever scaling the
    # machine taking the shot happens to use, rather than resampled to fit.
    ratio = application.primaryScreen().devicePixelRatio()
    window.resize(round(windowSize[0] / ratio), round(windowSize[1] / ratio))
    # The Calibrate tab, which is where the manual's tour starts.
    window.tabs.setCurrentWidget(window.calibrationView)
    window.show()
    save(window, imagesDir / "calibrate-tab-empty.png", application)

    about = AboutDialog()
    about.adjustSize()
    about.show()
    save(about, imagesDir / "about-dialog.png", application)

    print(f"\nVersion shown: {appConfig.appVersion}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
