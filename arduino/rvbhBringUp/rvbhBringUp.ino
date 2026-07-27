/*
 * RV Backup Helper - shield bring-up test
 *
 * Hand-written diagnostic, NOT generated. Flash this before the calibrated
 * grid to prove the Arduino, the TVout-VE library and the shield all work,
 * so that a later problem is known to be in the calibration and not the rig.
 *
 * Run it in two stages. Stage A needs no video at all, which is the point:
 * it removes the camera, the cabling and the sync source from the picture.
 *
 * STAGE A - USE_OVERLAY 0, no video source required
 *   SYNC SELECT  : jumper on the two LEFTMOST pins (sync generated on pin 9)
 *   OUTPUT SELECT: Sync only
 *   Feed the shield's video OUT to a monitor or the USB capture dongle.
 *   Expect: white test pattern on black.
 *
 * STAGE B - USE_OVERLAY 1, needs live composite video into the shield's IN
 *   SYNC SELECT  : jumper on the two RIGHTMOST pins (sync from V INPUT)
 *   OUTPUT SELECT: Overlay
 *   Expect: the same pattern drawn on top of the live picture.
 *
 * WHAT TO LOOK FOR
 *   - All four border edges: a missing side means the buffer is not the size
 *     this sketch thinks it is.
 *   - The block sweeping along the bottom: a frozen pattern means the sketch
 *     stalled, which is a different fault from the shield misbehaving.
 *   - The on-board LED blinking steadily: begin() could not allocate the
 *     frame buffer, so nothing will ever be drawn.
 *
 * IF THE PATTERN TEARS, DUPLICATES OR ROLLS
 *   The build and the shield wiring disagree. USE_OVERLAY 0 free-runs its own
 *   sync, so with OUTPUT SELECT on Overlay it drifts against the incoming
 *   video instead of locking to it - readable, but torn and doubled. Set
 *   USE_OVERLAY 1 to match Overlay wiring. Confirmed on real hardware: the
 *   same pattern went from torn to rock steady with no wiring change at all.
 *
 * HARDWARE: Arduino Uno R3 / Duemilanove (ATmega328P) + Nootropic Design
 * Video Experimenter. Needs the enhanced TVout, not the stock library:
 * https://github.com/nootropicdesign/arduino-tvout-ve
 */

#define USE_OVERLAY 0

#include <TVout.h>
#include <fontALL.h>

#define W 136
#define H 96

TVout tv;
uint8_t sweepX = 0;

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  // Non-zero means the frame buffer would not fit; nothing can be drawn and
  // the shield still passes video through, so the failure is otherwise silent.
  if (tv.begin(NTSC, W, H) != 0) {
    blinkForever();
  }
#if USE_OVERLAY
  initOverlay();
#endif
  tv.select_font(font4x6);
}

void loop() {
  tv.fill(0);
  drawPattern();
  sweepX += 3;
  if (sweepX > W - 12) {
    sweepX = 0;
  }
  tv.delay_frame(3);
}

void drawPattern() {
  tv.draw_rect(0, 0, W - 1, H - 1, 1);

  tv.print(4, 4, "RVBH BRING-UP");
#if USE_OVERLAY
  tv.print(4, 12, "OVERLAY");
#else
  tv.print(4, 12, "STANDALONE");
#endif

  // Reference rows for checking vertical alignment against the live picture.
  drawRow(30);
  drawRow(50);
  drawRow(70);

  // Proof of life.
  tv.draw_rect(sweepX + 2, H - 8, 8, 5, 1, 1);
}

void drawRow(uint8_t row) {
  tv.draw_line(2, row, W - 3, row, 1);
  tv.print(4, row - 7, "ROW");
  // Cast so this picks the decimal overload rather than printing a character.
  tv.print(24, row - 7, (int)row, DEC);
}

// Hand the timer and INT0 to the shield so the buffer rides on the incoming
// video rather than generating its own picture.
#if USE_OVERLAY
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
#endif

// Visible distress signal on the on-board LED, which the shield leaves free.
void blinkForever() {
  for (;;) {
    digitalWrite(LED_BUILTIN, HIGH);
    delay(200);
    digitalWrite(LED_BUILTIN, LOW);
    delay(200);
  }
}
