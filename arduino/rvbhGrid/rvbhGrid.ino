/*
 * RV Backup Helper - calibrated distance grid
 *
 * GENERATED FILE - do not edit by hand. Regenerate from the Calibrate tab
 * whenever the calibration changes.
 *
 * Source clip    : rvbh-20260730-100335.avi (frame 4124)
 * Measured on    : 640 x 480 capture
 * Overlay canvas : 136 x 96
 * Generated      : 2026-07-30 19:01
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
 *   TVout mallocs the frame buffer inside begin(): (136 / 8) x 96
 *   = 1632 bytes taken at runtime from the Uno's 2048. The compiler's
 *   "global variables" figure does NOT include it, so ignore how roomy that
 *   looks - only around 300 bytes are left for the stack. Move the labels
 *   into PROGMEM before adding many more lines.
 */

#include <TVout.h>
#include <fontALL.h>

#define W 136
#define H 96

TVout tv;

#define LABEL_GAP 2

struct GridLine {
  uint8_t row;         // row in the overlay canvas, 0 = top
  uint8_t thickness;   // rows of line; more than one marks a distance to watch
  uint8_t labelX;      // placed by the generator; the line breaks around it
  uint8_t labelY;
  uint8_t labelWidth;  // pixels, so the break is the right size
  const char *label;   // distance as shown to the driver
};

// Measured behind the RV, nearest first.
const GridLine GRID[] = {
  {  92, 1,   1,  89,  16, "0 ft"  },  // scan line 461 of 480, frame 4124
  {  85, 2,   1,  82,  16, "1 ft"  },  // scan line 427 of 480, frame 3400  <- emphasised
  {  78, 1,   1,  75,  16, "2 ft"  },  // scan line 388 of 480, frame 3085
  {  63, 1,   1,  60,  16, "4 ft"  },  // scan line 317 of 480, frame 2581
  {  39, 1,   1,  36,  16, "8 ft"  },  // scan line 194 of 480, frame 2078
  {  12, 1,   1,   9,  20, "16 ft" },  // scan line 59 of 480, frame 1322
  {   5, 1,   1,   2,  20, "20 ft" },  // scan line 24 of 480, frame 0
};
const uint8_t GRID_COUNT = sizeof(GRID) / sizeof(GRID[0]);

// Vehicle width where it was measured, top of the canvas first so
// consecutive entries join downward.
struct WidthPoint {
  uint8_t row;
  uint8_t leftX;
  uint8_t rightX;
};
const WidthPoint WIDTH[] = {
  {   5,  82,  49 },  // 20 ft
  {  12,  85,  46 },  // 16 ft
  {  39,  91,  36 },  // 8 ft
  {  63,  95,  31 },  // 4 ft
  {  78,  96,  28 },  // 2 ft
  {  85,  97,  27 },  // 1 ft
  {  92,  97,  27 },  // 0 ft
};
const uint8_t WIDTH_COUNT = sizeof(WIDTH) / sizeof(WIDTH[0]);

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
  drawWidthLines();
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
    drawBrokenLine(GRID[i]);
    tv.print(GRID[i].labelX, GRID[i].labelY, GRID[i].label);
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

#define DASH_LENGTH 3

// Drawn as a polyline through the measured points rather than as a straight
// taper. The camera is wide-angle, so the true edges of the vehicle's path
// curve across the picture and a straight line would lie about where they run.
void drawWidthLines() {
  for (uint8_t i = 0; i + 1 < WIDTH_COUNT; i++) {
    drawDashedEdge(WIDTH[i].leftX, WIDTH[i].row, WIDTH[i + 1].leftX, WIDTH[i + 1].row);
    drawDashedEdge(WIDTH[i].rightX, WIDTH[i].row, WIDTH[i + 1].rightX, WIDTH[i + 1].row);
  }
}

// These run close to vertical, so stepping down the rows and interpolating the
// column keeps the dashes evenly spaced.
void drawDashedEdge(uint8_t x0, uint8_t y0, uint8_t x1, uint8_t y1) {
  if (y1 <= y0) {
    return;
  }
  int16_t run = (int16_t)y1 - (int16_t)y0;
  int16_t rise = (int16_t)x1 - (int16_t)x0;
  for (uint8_t y = y0; y <= y1; y++) {
    if (((y / DASH_LENGTH) & 1) != 0) {
      continue;
    }
    int16_t x = (int16_t)x0 + rise * (int16_t)(y - y0) / run;
    if (x >= 0 && x < W) {
      tv.set_pixel((uint8_t)x, y, 1);
    }
  }
}

void loop() {
  // The grid is static: draw once, then idle so the overlay stays put.
  tv.delay_frame(30);
}
