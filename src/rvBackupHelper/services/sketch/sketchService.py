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
#include <pollserial.h>
#include <EEPROM.h>
#include <avr/pgmspace.h>

#define W $canvasWidth
#define H $canvasHeight

// Single-character commands from the host, so calibration footage can be
// recorded without the grid burned into it hiding the very markings you are
// trying to click. '$gridOn' draws, '$gridOff' clears, '$gridQuery' reports.
#define COMMAND_BAUD $commandBaud
#define GRID_STATE_ADDRESS $gridStateAddress

TVout tv;
// pollserial, not the built-in Serial. HardwareSerial's 64-byte receive and
// transmit buffers are static, and with the frame buffer taking 1632 of the
// Uno's 2048 they left about 60 bytes of stack - not enough to run. This one
// is polled from TVout's blanking hook instead of from an interrupt, so it
// also stays out of the way of video generation.
pollserial pserial;
bool gridVisible = true;

#define LABEL_GAP $labelGap

struct GridLine {
  uint8_t row;         // row in the overlay canvas, 0 = top
  uint8_t thickness;   // rows of line; more than one marks a distance to watch
  uint8_t labelX;      // placed by the generator; the line breaks around it
  uint8_t labelY;
  uint8_t labelWidth;  // pixels, so the break is the right size
  const char *label;   // distance as shown to the driver
};

// Labels and tables live in flash, not RAM. The frame buffer takes $bufferBytes of
// the Uno's 2048 at runtime, so what is left has to stay clear for the stack.
$gridLabels

// Measured behind the RV, nearest first.
const GridLine GRID[] PROGMEM = {
$gridRows
};
const uint8_t GRID_COUNT = sizeof(GRID) / sizeof(GRID[0]);

$widthSection

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
  // begin() hands back the polling routine; TVout calls it during blanking.
  tv.set_hbi_hook(pserial.begin(COMMAND_BAUD));
  // Unwritten EEPROM reads 0xFF, so a board that has never been told otherwise
  // starts with the grid showing.
  gridVisible = EEPROM.read(GRID_STATE_ADDRESS) != 0;
  applyGrid();
}

// Opening the serial port resets the board, which no host can avoid, so the
// wanted state is kept in EEPROM and re-applied on every start.
void handleCommands() {
  while (pserial.available() > 0) {
    char command = (char)pserial.read();
    if (command == '$gridOn') {
      setGridVisible(true);
    } else if (command == '$gridOff') {
      setGridVisible(false);
    } else if (command == '$gridQuery') {
      reportState();
    }
  }
}

void setGridVisible(bool visible) {
  gridVisible = visible;
  EEPROM.update(GRID_STATE_ADDRESS, visible ? 1 : 0);
  applyGrid();
  reportState();
}

void applyGrid() {
  tv.fill(0);
  if (gridVisible) {
    drawGrid();
    drawWidthLines();
  }
}

void reportState() {
  pserial.println(gridVisible ? "grid on" : "grid off");
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
  GridLine line;
  for (uint8_t i = 0; i < GRID_COUNT; i++) {
    // Copy the row out of flash before using it.
    memcpy_P(&line, &GRID[i], sizeof(line));
    drawBrokenLine(line);
    tv.printPGM(line.labelX, line.labelY, line.label);
  }
}

// The label sits in a gap in its own line rather than floating above it. With
// no colour to pair them, being physically part of the line is what makes it
// unambiguous which distance a label belongs to.
void drawBrokenLine(const GridLine &line) {
  uint8_t gapStart = (line.labelX > LABEL_GAP) ? (line.labelX - LABEL_GAP) : 0;
  uint16_t gapEnd = line.labelX + line.labelWidth + LABEL_GAP;
  for (uint8_t step = 0; step < line.thickness; step++) {
    // Thickness grows downward, so the far edge stays on the measured line.
    uint16_t y = line.row + step;
    if (y > H - 1) {
      break;
    }
    if (gapStart > 0) {
      tv.draw_line(0, y, gapStart, y, 1);
    }
    if (gapEnd < W - 1) {
      tv.draw_line(gapEnd, y, W - 1, y, 1);
    }
  }
}

$widthDrawing

void loop() {
  handleCommands();
  // Nothing is redrawn between commands. Writing to the buffer while the video
  // generator is scanning it out is what makes the overlay jump, and delay_frame
  // rather than delay() keeps the wait cooperative with video generation.
  tv.delay_frame(2);
}
"""
)

# font4x6: glyphs are 4 px wide and 6 tall.
glyphWidth = 4
glyphHeight = 6
leftMargin = 1
rightMargin = 2


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
            labelGap=appConfig.labelGapPixels,
            commandBaud=appConfig.commandBaud,
            gridStateAddress=appConfig.gridStateAddress,
            gridOn=appConfig.gridOnCommand,
            gridOff=appConfig.gridOffCommand,
            gridQuery=appConfig.gridQueryCommand,
            gridLabels=self.renderLabels(calibration),
            gridRows=self.renderRows(calibration),
            widthSection=self.renderWidthSection(calibration),
            widthDrawing=self.renderWidthDrawing(calibration),
        )

    def labelPosition(
        self, row: int, label: str, placed: list[tuple[int, int, int]]
    ) -> tuple[int, int]:
        """Where to print a label so it sits in its own line, clear of others.

        The label is centred on its line and the line is broken around it, so
        a label can never be mistaken for the neighbouring line the way it
        could when labels floated above. Two lines closer together than a
        glyph is tall would still collide, so the right-hand slot remains as
        a fallback.
        """
        labelY = max(0, min(row - glyphHeight // 2, appConfig.overlayCanvasHeight - glyphHeight))
        width = glyphWidth * len(label)
        left = leftMargin
        right = max(leftMargin, appConfig.overlayCanvasWidth - rightMargin - width)
        for x in (left, right):
            if not any(
                abs(labelY - otherY) < glyphHeight
                and x < otherX + otherWidth
                and otherX < x + width
                for otherX, otherY, otherWidth in placed
            ):
                return x, labelY
        # Both slots taken: keep it on the right rather than over the left label.
        return right, labelY

    def renderWidthSection(self, calibration: Calibration) -> str:
        """The WIDTH array, or a stub when no width was measured."""
        points = calibration.widthPoints
        if not points:
            return (
                "// No vehicle-width points yet. Mark both edges at a distance in\n"
                "// the Calibrate tab to get the corridor lines.\n"
                "const uint8_t WIDTH_COUNT = 0;"
            )

        lines = [
            "// Vehicle width where it was measured, top of the canvas first so",
            "// consecutive entries join downward.",
            "struct WidthPoint {",
            "  uint8_t row;",
            "  uint8_t leftX;",
            "  uint8_t rightX;",
            "};",
            "const WidthPoint WIDTH[] PROGMEM = {",
        ]
        # widthPoints runs near to far; reversed gives ascending rows.
        for point in reversed(points):
            assert point.leftEdge is not None and point.rightEdge is not None
            lines.append(
                f"  {{ {calibration.overlayRow(point.scanLine):3d},"
                f" {calibration.overlayColumn(point.leftEdge):3d},"
                f" {calibration.overlayColumn(point.rightEdge):3d} }},"
                f"  // {point.label}"
            )
        lines.append("};")
        lines.append("const uint8_t WIDTH_COUNT = sizeof(WIDTH) / sizeof(WIDTH[0]);")
        return "\n".join(lines)

    def renderWidthDrawing(self, calibration: Calibration) -> str:
        if not calibration.widthPoints:
            return (
                "void drawWidthLines() {\n"
                "  // Nothing measured, so there is no corridor to draw.\n"
                "}"
            )
        return f"""#define DASH_LENGTH {appConfig.dashLengthPixels}

// Drawn as a polyline through the measured points rather than as a straight
// taper. The camera is wide-angle, so the true edges of the vehicle's path
// curve across the picture and a straight line would lie about where they run.
void drawWidthLines() {{
  WidthPoint near, far;
  for (uint8_t i = 0; i + 1 < WIDTH_COUNT; i++) {{
    memcpy_P(&near, &WIDTH[i], sizeof(near));
    memcpy_P(&far, &WIDTH[i + 1], sizeof(far));
    drawDashedEdge(near.leftX, near.row, far.leftX, far.row);
    drawDashedEdge(near.rightX, near.row, far.rightX, far.row);
  }}
}}

// These run close to vertical, so stepping down the rows and interpolating the
// column keeps the dashes evenly spaced.
void drawDashedEdge(uint8_t x0, uint8_t y0, uint8_t x1, uint8_t y1) {{
  if (y1 <= y0) {{
    return;
  }}
  int16_t run = (int16_t)y1 - (int16_t)y0;
  int16_t rise = (int16_t)x1 - (int16_t)x0;
  for (uint8_t y = y0; y <= y1; y++) {{
    if (((y / DASH_LENGTH) & 1) != 0) {{
      continue;
    }}
    int16_t x = (int16_t)x0 + rise * (int16_t)(y - y0) / run;
    if (x >= 0 && x < W) {{
      tv.set_pixel((uint8_t)x, y, 1);
    }}
  }}
}}"""

    def thicknessFor(self, distanceFeet: float) -> int:
        """Heavier line for the distances worth noticing at a glance."""
        emphasised = {round(value, 1) for value in appConfig.emphasisedDistancesFeet}
        if round(distanceFeet, 1) in emphasised:
            return appConfig.emphasisedThickness
        return 1

    def labelSymbol(self, index: int) -> str:
        return f"gridLabel{index}"

    def renderLabels(self, calibration: Calibration) -> str:
        return "\n".join(
            f'const char {self.labelSymbol(index)}[] PROGMEM = "{point.label}";'
            for index, point in enumerate(calibration.sortedPoints)
        )

    def renderRows(self, calibration: Calibration) -> str:
        points = calibration.sortedPoints
        # Pad to the longest symbol so the trailing comments line up; this file
        # gets read by a human deciding whether the grid looks right.
        symbolWidth = max(len(self.labelSymbol(i)) for i in range(len(points)))
        placed: list[tuple[int, int, int]] = []
        lines = []
        for index, point in enumerate(points):
            row = calibration.overlayRow(point.scanLine)
            width = glyphWidth * len(point.label)
            labelX, labelY = self.labelPosition(row, point.label, placed)
            placed.append((labelX, labelY, width))
            thickness = self.thicknessFor(point.distanceFeet)
            emphasis = "  <- emphasised" if thickness > 1 else ""
            symbol = self.labelSymbol(index)
            lines.append(
                f"  {{ {row:3d}, {thickness}, {labelX:3d}, {labelY:3d}, {width:3d}, "
                f"{symbol:<{symbolWidth}} }},"
                f"  // {point.label}, scan line {point.scanLine}"
                f" of {calibration.frameHeight}, frame {point.frameIndex}{emphasis}"
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
