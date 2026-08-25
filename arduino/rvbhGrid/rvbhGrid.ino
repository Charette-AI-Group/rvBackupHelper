/*
 * RV Backup Helper - calibrated distance grid
 *
 * GENERATED FILE - do not edit by hand. Regenerate from the Calibrate tab
 * whenever the calibration changes.
 *
 * Source clip    : 2026-08-19_09-39-59.mkv (frame 441)
 * Measured on    : 640 x 360 capture
 * Overlay canvas : 136 x 96
 * Generated      : 2026-08-25 16:24
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
#include <pollserial.h>
#include <EEPROM.h>
#include <avr/pgmspace.h>

#define W 136
#define H 96

// Single-character commands from the host, so calibration footage can be
// recorded without the grid burned into it hiding the very markings you are
// trying to click. 'g' draws, 'c' clears, '?' reports.
#define COMMAND_BAUD 9600
#define GRID_STATE_ADDRESS 0

TVout tv;
// pollserial, not the built-in Serial. HardwareSerial's 64-byte receive and
// transmit buffers are static, and with the frame buffer taking 1632 of the
// Uno's 2048 they left about 60 bytes of stack - not enough to run. This one
// is polled from TVout's blanking hook instead of from an interrupt, so it
// also stays out of the way of video generation.
pollserial pserial;
bool gridVisible = true;

#define LABEL_GAP 2

struct GridLine {
  uint8_t row;         // row in the overlay canvas, 0 = top
  uint8_t thickness;   // rows of line; more than one marks a distance to watch
  uint8_t labelX;      // placed by the generator; the line breaks around it
  uint8_t labelY;
  uint8_t labelWidth;  // pixels, so the break is the right size
  const char *label;   // distance as shown to the driver
};

// Labels and tables live in flash, not RAM. The frame buffer takes 1632 of
// the Uno's 2048 at runtime, so what is left has to stay clear for the stack.
const char gridLabel0[] PROGMEM = "0 ft";
const char gridLabel1[] PROGMEM = "1 ft";
const char gridLabel2[] PROGMEM = "2 ft";
const char gridLabel3[] PROGMEM = "4 ft";
const char gridLabel4[] PROGMEM = "8 ft";
const char gridLabel5[] PROGMEM = "12 ft";
const char gridLabel6[] PROGMEM = "16 ft";
const char gridLabel7[] PROGMEM = "20 ft";
const char gridLabel8[] PROGMEM = "24 ft";

// Measured behind the RV, nearest first.
const GridLine GRID[] PROGMEM = {
  {  92, 1,   1,  89,  16, gridLabel0 },  // 0 ft, scan line 346 of 360, frame 441
  {  86, 2,   1,  83,  16, gridLabel1 },  // 1 ft, scan line 324 of 360, frame 1001  <- emphasised
  {  78, 1,   1,  75,  16, gridLabel2 },  // 2 ft, scan line 294 of 360, frame 1642
  {  64, 1,   1,  61,  16, gridLabel3 },  // 4 ft, scan line 241 of 360, frame 2123
  {  40, 1,   1,  37,  16, gridLabel4 },  // 8 ft, scan line 151 of 360, frame 2884
  {  24, 1,   1,  21,  20, gridLabel5 },  // 12 ft, scan line 90 of 360, frame 3685
  {  14, 1,   1,  11,  20, gridLabel6 },  // 16 ft, scan line 51 of 360, frame 4326
  {   6, 1,   1,   3,  20, gridLabel7 },  // 20 ft, scan line 23 of 360, frame 5047
  {   1, 1, 114,   0,  20, gridLabel8 },  // 24 ft, scan line 4 of 360, frame 5808
};
const uint8_t GRID_COUNT = sizeof(GRID) / sizeof(GRID[0]);

// Vehicle width where it was measured, top of the canvas first so
// consecutive entries join downward.
struct WidthPoint {
  uint8_t row;
  uint8_t leftX;
  uint8_t rightX;
};
const WidthPoint WIDTH[] PROGMEM = {
  {   1,  77,  49 },  // 24 ft
  {   6,  79,  47 },  // 20 ft
  {  14,  82,  44 },  // 16 ft
  {  24,  85,  40 },  // 12 ft
  {  40,  88,  34 },  // 8 ft
  {  64,  93,  29 },  // 4 ft
  {  78,  95,  28 },  // 2 ft
  {  86,  95,  27 },  // 1 ft
  {  92,  95,  26 },  // 0 ft
};
const uint8_t WIDTH_COUNT = sizeof(WIDTH) / sizeof(WIDTH[0]);

void setup() {
  // Build-time proof that the enhanced TVout is installed: the stock library
  // has no capture(), so this line fails to compile against it. Without the
  // check the stock library builds happily and then leaves no handler for the
  // input capture interrupt initOverlay() enables, so the board resets on
  // every sync pulse and answers nothing - a silence that looks like a serial
  // problem and is not one.
  (void)&TVout::capture;
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
    if (command == 'g') {
      setGridVisible(true);
    } else if (command == 'c') {
      setGridVisible(false);
    } else if (command == '?') {
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

#define DASH_LENGTH 3

// Drawn as a polyline through the measured points rather than as a straight
// taper. The camera is wide-angle, so the true edges of the vehicle's path
// curve across the picture and a straight line would lie about where they run.
void drawWidthLines() {
  WidthPoint near, far;
  for (uint8_t i = 0; i + 1 < WIDTH_COUNT; i++) {
    memcpy_P(&near, &WIDTH[i], sizeof(near));
    memcpy_P(&far, &WIDTH[i + 1], sizeof(far));
    drawDashedEdge(near.leftX, near.row, far.leftX, far.row);
    drawDashedEdge(near.rightX, near.row, far.rightX, far.row);
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
  handleCommands();
  // Nothing is redrawn between commands. Writing to the buffer while the video
  // generator is scanning it out is what makes the overlay jump, and delay_frame
  // rather than delay() keeps the wait cooperative with video generation.
  tv.delay_frame(2);
}
