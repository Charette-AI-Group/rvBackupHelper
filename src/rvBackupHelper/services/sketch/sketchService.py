"""Generates the Arduino sketch that draws the calibrated grid.

Only vertical mapping is measured, so the sketch draws each distance as a line
right across the picture. Tapering the lines to suggest perspective would imply
a width nobody measured, so it is left out rather than invented.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from string import Template

from rvBackupHelper import appConfig
from rvBackupHelper.models.calibrationModels import Calibration, CalibrationPoint

logger = logging.getLogger(__name__)


class SketchError(RuntimeError):
    """A sketch could not be generated from the calibration."""


def defaultSketchPath() -> Path:
    folder = appConfig.arduinoDir / appConfig.sketchName
    return folder / f"{appConfig.sketchName}{appConfig.sketchExtension}"


# $-placeholders, so the C braces below need no escaping.
sketchTemplate = Template(
    """/*
 * RV Backup Helper - calibrated distance grid
 *
 * GENERATED FILE - do not edit by hand. Regenerate from the Calibrate tab
 * whenever the calibration changes.
 *
 * Source clip    : $sourceClip (frame $frameIndex)
 * Measured on    : $frameWidth x $frameHeight capture
 * Overlay canvas : $canvasWidth x $canvasHeight
 * Generated      : $generatedAt
 *
 * HARDWARE
 *   Arduino Uno R3 / Duemilanove (ATmega328P) + Nootropic Design Video
 *   Experimenter shield. This will NOT run on an Uno R4, Leonardo, Mega or
 *   Uno Q: TVout is hand-written AVR assembly driving ATmega timers.
 *
 * LIBRARY
 *   Needs the enhanced TVout, not the stock one:
 *   https://github.com/nootropicdesign/arduino-tvout-ve
 *
 * SHIELD SETTINGS
 *   SYNC SELECT  : jumper on the two rightmost pins (sync from V INPUT)
 *   OUTPUT SELECT: Overlay
 *   R4 pot       : fully counter-clockwise; raise slightly only if the
 *                  picture is vertically jumpy
 *
 * NOTE ON MEMORY
 *   TVout mallocs the frame buffer inside begin(): ($canvasWidth / 8) x $canvasHeight
 *   = $bufferBytes bytes taken at runtime from the Uno's 2048. The compiler's
 *   "global variables" figure does NOT include it, so ignore how roomy that
 *   looks - only around 300 bytes are left for the stack. Move the labels
 *   into PROGMEM before adding many more lines.
 */

#include <TVout.h>
#include <fontALL.h>

#define W $canvasWidth
#define H $canvasHeight

TVout tv;

struct GridLine {
  uint8_t row;         // row in the overlay canvas, 0 = top
  const char *label;   // distance as shown to the driver
};

// Measured behind the RV, nearest first.
const GridLine GRID[] = {
$gridRows
};
const uint8_t GRID_COUNT = sizeof(GRID) / sizeof(GRID[0]);

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  // begin() returns non-zero when the frame buffer will not fit. Without it
  // nothing can be drawn, and the failure is otherwise silent: the shield
  // still passes the camera through, so the driver just sees no grid.
  if (tv.begin(NTSC, W, H) != 0) {
    blinkForever();
  }
  initOverlay();
  tv.select_font(font4x6);
  tv.fill(0);
  drawGrid();
}

// Visible distress signal on the on-board LED, which the shield leaves free.
void blinkForever() {
  for (;;) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(200);
    digitalWrite(LED_BUILTIN, LOW);
    delay(200);
  }
}

// Hand the timer and INT0 to the shield so the buffer rides on the incoming
// video rather than generating its own picture.
void initOverlay() {
  TCCR1A = 0;
  TCCR1B = _BV(CS10);
  TIMSK1 |= _BV(ICIE1);
  EIMSK = _BV(INT0);
  EICRA = _BV(ISC01);
}

// Vertical sync: restart the buffer at the top of the incoming field.
ISR(INT0_vect) {
  display.scanLine = 0;
}

void drawGrid() {
  for (uint8_t i = 0; i < GRID_COUNT; i++) {
    uint8_t row = GRID[i].row;
    tv.draw_line(0, row, W - 1, row, 1);
    // Label above the line, or just below it when the line is at the very top.
    uint8_t labelY = (row >= $labelHeight) ? (row - $labelHeight) : (row + 2);
    tv.print(1, labelY, GRID[i].label);
  }
}

void loop() {
  // The grid is static: draw once, then idle so the overlay stays put.
  tv.delay_frame(30);
}
"""
)

# font4x6 glyphs are 6 rows tall; one more keeps the label off the line.
labelHeightPixels = 7


class SketchService:
    """Renders a Calibration into a compilable .ino sketch."""

    def collidingRows(self, calibration: Calibration) -> dict[int, list[CalibrationPoint]]:
        """Distances that land on the same overlay row.

        The capture is several times taller than the shield canvas, so nearby
        distances can rescale onto one row. The sketch would then draw two
        labels on one line, which is worth warning about rather than shipping.
        """
        byRow: dict[int, list[CalibrationPoint]] = defaultdict(list)
        for point in calibration.sortedPoints:
            byRow[calibration.overlayRow(point.scanLine)].append(point)
        return {row: points for row, points in byRow.items() if len(points) > 1}

    def generate(
        self, calibration: Calibration, generatedAt: datetime | None = None
    ) -> str:
        if calibration.isEmpty:
            raise SketchError("The calibration has no points, so there is no grid to draw.")
        if calibration.frameHeight <= 0:
            raise SketchError("The calibration has no frame height, so rows cannot be scaled.")

        stamp = (generatedAt or datetime.now()).strftime("%Y-%m-%d %H:%M")
        canvasWidth = appConfig.overlayCanvasWidth
        canvasHeight = appConfig.overlayCanvasHeight
        return sketchTemplate.substitute(
            sourceClip=calibration.sourceClip or "(unknown clip)",
            frameIndex=calibration.frameIndex,
            frameWidth=calibration.frameWidth,
            frameHeight=calibration.frameHeight,
            canvasWidth=canvasWidth,
            canvasHeight=canvasHeight,
            bufferBytes=canvasWidth * canvasHeight // 8,
            generatedAt=stamp,
            labelHeight=labelHeightPixels,
            gridRows=self.renderRows(calibration),
        )

    def renderRows(self, calibration: Calibration) -> str:
        points = calibration.sortedPoints
        # Pad to the longest label so the trailing comments line up; this file
        # gets read by a human deciding whether the grid looks right.
        labelWidth = max(len(point.label) for point in points) + 2
        lines = []
        for point in points:
            row = calibration.overlayRow(point.scanLine)
            quoted = f'"{point.label}"'
            lines.append(
                f"  {{ {row:3d}, {quoted:<{labelWidth}} }},"
                f"  // scan line {point.scanLine} of {calibration.frameHeight}"
            )
        return "\n".join(lines)

    def save(
        self,
        calibration: Calibration,
        path: Path,
        generatedAt: datetime | None = None,
    ) -> Path:
        sketch = self.generate(calibration, generatedAt)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(sketch, encoding="utf-8")
        logger.info("Wrote sketch with %d grid line(s) to %s", len(calibration.points), path)
        return path
