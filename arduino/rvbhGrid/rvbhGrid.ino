/*
 * RV Backup Helper - calibrated distance grid
 *
 * GENERATED FILE - do not edit by hand. Regenerate from the Calibrate tab
 * whenever the calibration changes.
 *
 * Source clip    : rvbh-20260730-100335.avi (frame 3998)
 * Measured on    : 640 x 480 capture
 * Overlay canvas : 136 x 96
 * Generated      : 2026-07-30 17:54
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
  {  92, 1,   1,  89,  16, "0 ft"  },  // scan line 461 of 480
  {  85, 2,   1,  82,  16, "1 ft"  },  // scan line 427 of 480  <- emphasised
  {  78, 1,   1,  75,  16, "2 ft"  },  // scan line 388 of 480
  {  63, 1,   1,  60,  16, "4 ft"  },  // scan line 316 of 480
  {  39, 1,   1,  36,  16, "8 ft"  },  // scan line 193 of 480
  {  12, 1,   1,   9,  20, "16 ft" },  // scan line 58 of 480
  {   5, 1,   1,   2,  20, "20 ft" },  // scan line 23 of 480
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

void loop() {
  // The grid is static: draw once, then idle so the overlay stays put.
  tv.delay_frame(30);
}
