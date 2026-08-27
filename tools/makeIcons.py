r"""Draw the application icon, one size at a time.

Following the approach pySPWB uses for its own: every size is *drawn* at that
size rather than shrunk from one large rendering. A 16 px icon made by
scaling a 256 px one is mush - the strokes fall below a pixel and the shape
stops reading - so the drawing thickens its lines and drops detail as it gets
smaller. Below 32 px the corridor loses its dashes and the grid loses lines,
until what is left is the one thing worth recognising at that size: a
distance line with a corridor narrowing away from it.

The artwork is what the driver actually sees: distance lines across the
picture, the nearest one heavier because it is the "about to touch something"
line, and the vehicle-width corridor converging into the distance. Amber on
near-black, which is the overlay on a reversing camera at dusk.

    .venv\Scripts\python.exe tools\makeIcons.py

Writes src\rvBackupHelper\resources\rvBackupHelper.ico and a 256 px preview
under docs\manual\images. Do not edit the .ico - edit the drawing and re-run.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

from PySide6.QtCore import QBuffer, QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication

projectRoot = Path(__file__).resolve().parents[1]
outputDir = projectRoot / "src" / "rvBackupHelper" / "resources"
previewPath = projectRoot / "docs" / "manual" / "images" / "icon.png"

# What a .ico carries. 16 is the taskbar and the title bar, 256 the file
# dialog's extra-large view; the sizes between are what Windows picks at
# various DPI settings.
iconSizes = (16, 24, 32, 48, 64, 128, 256)

# The picture behind the overlay: a camera image at dusk rather than a flat
# tile, so the grid reads as something drawn *on* video.
backgroundTop = QColor("#2A3546")
backgroundBottom = QColor("#0B0F16")
# The measured lines. White on the board, a little warm here so they hold up
# against the dark background at small sizes.
lineColour = QColor("#E8EDF2")
# The emphasised line, matching what emphasisedDistancesFeet does on the
# board - and the amber the sibling applications already use.
nearColour = QColor("#F0B232")
corridorColour = QColor("#B9CBE0")


def session() -> QApplication:
    return QApplication.instance() or QApplication([])


def strokeWidth(size: int, weight: float = 1.0) -> float:
    """A width that survives being small.

    Scaling a stroke linearly with the icon makes it vanish below about
    24 px, so the floor is a whole pixel and small sizes get a
    proportionally fatter line.
    """
    return max(1.0, size * 0.028 * weight)


def linePen(colour: QColor, size: int, weight: float = 1.0) -> QPen:
    pen = QPen(colour, strokeWidth(size, weight))
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    return pen


def distanceRows(size: int) -> list[float]:
    """Where the lines sit, as fractions of the height.

    Spaced the way perspective spaces them - close together far away, further
    apart as they near the bumper - and thinned out as the icon shrinks,
    because four lines inside 16 px is a grey smudge.
    """
    if size < 24:
        return [0.72, 0.44]
    if size < 48:
        return [0.73, 0.53, 0.37]
    return [0.74, 0.57, 0.43, 0.33]


def corridorAt(size: int, row: float) -> tuple[float, float]:
    """The left and right edges of the vehicle's path at a given row.

    They converge upward, which is the whole reason the corridor is drawn on
    the real overlay: it says where the vehicle will actually go.
    """
    nearHalf = 0.40
    farHalf = 0.07
    # row 0.24 is the horizon of this drawing, 0.80 the bumper.
    span = (row - 0.24) / (0.80 - 0.24)
    span = min(max(span, 0.0), 1.0)
    half = farHalf + (nearHalf - farHalf) * span
    return (0.5 - half) * size, (0.5 + half) * size


def drawGrid(painter: QPainter, size: int) -> None:
    rows = distanceRows(size)
    # Furthest first, so the nearest line is painted over the corridor rather
    # than under it - it is the one that has to read at 16 px.
    for index, row in enumerate(reversed(rows)):
        isNearest = index == len(rows) - 1
        left, right = corridorAt(size, row)
        # A little wider than the corridor, as they run on the board, but
        # only where there is room: past about 4% the taper stops reading and
        # the whole thing turns into a ladder.
        overhang = size * (0.04 if size >= 48 else 0.02)
        painter.setPen(
            linePen(
                nearColour if isNearest else lineColour,
                size,
                1.35 if isNearest else 0.8,
            )
        )
        y = row * size
        painter.drawLine(
            QPointF(max(left - overhang, size * 0.12), y),
            QPointF(min(right + overhang, size * 0.88), y),
        )


def drawCorridor(painter: QPainter, size: int) -> None:
    pen = linePen(corridorColour, size, 0.9)
    if size >= 48:
        # Dashes at the sizes that can hold them, matching the overlay, where
        # they keep the edges reading as a corridor rather than more lines.
        pen.setDashPattern([2.2, 1.6])
    painter.setPen(pen)
    # The corridor closes on the nearest line and stops just above the
    # furthest one, so the trapezoid frames the grid instead of running past
    # it - edges poking out below the bottom line read as legs, not distance.
    rows = distanceRows(size)
    topRow, bottomRow = rows[-1] - 0.03, rows[0]
    topLeft, topRight = corridorAt(size, topRow)
    bottomLeft, bottomRight = corridorAt(size, bottomRow)
    painter.drawLine(
        QPointF(bottomLeft, bottomRow * size), QPointF(topLeft, topRow * size)
    )
    painter.drawLine(
        QPointF(bottomRight, bottomRow * size), QPointF(topRight, topRow * size)
    )


def render(size: int) -> QPixmap:
    """One icon at one size, drawn rather than scaled."""
    session()
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setPen(Qt.PenStyle.NoPen)

    # Tighter corners when small, or the rounding eats the artwork.
    radius = size * (0.18 if size < 32 else 0.22)
    background = QLinearGradient(QPointF(0, 0), QPointF(0, size))
    background.setColorAt(0.0, backgroundTop)
    background.setColorAt(1.0, backgroundBottom)
    painter.setBrush(background)
    painter.drawRoundedRect(QRectF(0, 0, size, size), radius, radius)

    drawCorridor(painter, size)
    drawGrid(painter, size)
    painter.end()
    return pixmap


def pngBytes(pixmap: QPixmap) -> bytes:
    buffer = QBuffer()
    buffer.open(QBuffer.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    return bytes(buffer.data())


def packIco(images: list[tuple[int, bytes]]) -> bytes:
    """A multi-resolution .ico holding PNG-encoded entries.

    Written by hand rather than through Qt's writer so that every size in the
    file is the one that was drawn at that size. Vista and later accept PNG
    inside an ICO, which keeps the 256 px entry from being enormous.
    """
    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries: list[bytes] = []
    payload: list[bytes] = []
    for size, data in images:
        entries.append(
            struct.pack(
                "<BBBBHHII",
                0 if size >= 256 else size,  # 0 means 256 in an ICO
                0 if size >= 256 else size,
                0,
                0,
                1,
                32,
                len(data),
                offset,
            )
        )
        payload.append(data)
        offset += len(data)
    return header + b"".join(entries) + b"".join(payload)


def main() -> int:
    session()
    outputDir.mkdir(parents=True, exist_ok=True)
    previewPath.parent.mkdir(parents=True, exist_ok=True)

    images = [(size, pngBytes(render(size))) for size in iconSizes]
    icoPath = outputDir / "rvBackupHelper.ico"
    icoPath.write_bytes(packIco(images))
    render(256).save(str(previewPath), "PNG")

    sizes = "/".join(str(size) for size in iconSizes)
    print(f"{icoPath}  ({sizes} px, {icoPath.stat().st_size:,} bytes)")
    print(f"{previewPath}  (256 px preview, for looking at)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
