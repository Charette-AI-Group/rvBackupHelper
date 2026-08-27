r"""Tests for the application icon.

Every size in the .ico is meant to be drawn at that size rather than scaled
down from the largest, so the thing worth checking is that they are all really
in there - a file carrying only 256 px looks perfect in a file dialog and turns
to mush on the taskbar, which is the one place an icon is always seen.
"""

from __future__ import annotations

import struct

from PySide6.QtGui import QIcon

from rvBackupHelper import appConfig
from rvBackupHelper.ui.mainWindow import MainWindow

# What tools/makeIcons.py writes, and what Windows picks between.
expectedSizes = {16, 24, 32, 48, 64, 128, 256}


def sizesInIco(data: bytes) -> set[int]:
    """The widths an .ico advertises, reading its directory rather than Qt's."""
    reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    assert reserved == 0 and kind == 1, "not an .ico"
    sizes = set()
    for index in range(count):
        width = data[6 + index * 16]
        # 0 means 256 in an ICO directory: the field is a single byte.
        sizes.add(width or 256)
    return sizes


def testTheIconShipsWithTheApplication() -> None:
    assert appConfig.iconPath.is_file(), "run tools/makeIcons.py"
    assert appConfig.iconPath.stat().st_size > 0


def testEverySizeIsPresent() -> None:
    """A missing 16 px is the one nobody notices until it is on a taskbar."""
    assert sizesInIco(appConfig.iconPath.read_bytes()) == expectedSizes


def testEachSizeIsItsOwnDrawing() -> None:
    """Scaled-from-one-rendering would leave identical payloads at each size."""
    data = appConfig.iconPath.read_bytes()
    count = struct.unpack_from("<HHH", data, 0)[2]
    payloads = set()
    for index in range(count):
        length, offset = struct.unpack_from("<II", data, 6 + index * 16 + 8)
        payloads.add(data[offset : offset + length])
    assert len(payloads) == count, "two sizes share an image"


def testQtReadsEverySizeBackOut(qapp) -> None:
    """The file is packed by hand, so a real reader gets the last word.

    Needs a QApplication: QIcon aborts the process without one, which is a
    crash rather than a failure and reports as neither.
    """
    icon = QIcon(str(appConfig.iconPath))

    assert not icon.isNull()
    assert {size.width() for size in icon.availableSizes()} == expectedSizes


def testTheWindowWearsWhatTheApplicationSets(qtbot, qapp) -> None:
    """main() sets it on the application; windows inherit from there."""
    qapp.setWindowIcon(QIcon(str(appConfig.iconPath)))
    mainWindow = MainWindow()
    qtbot.addWidget(mainWindow)

    assert not mainWindow.windowIcon().isNull()
