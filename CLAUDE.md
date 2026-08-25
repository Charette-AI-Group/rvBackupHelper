# RV Backup Helper — project context

Coding conventions, architecture rules and naming live in `AGENTS.md`. Read that first.
This file carries the **hardware and domain context** that cannot be derived from the code.

## The problem

A 2022 Newmar BayStar motorhome shows a rear camera image while backing, but the factory
display draws **no guide lines** — nothing tells the driver how far away anything is.
Goal: overlay a *calibrated horizontal distance grid* onto that live camera image.
Longer term, AI object recognition on the same feed.

## Signal chain

The camera feed is **analog composite video (CVBS, NTSC)**, intercepted at the header
connector behind the display. It has been captured successfully with a USB2 video grabber
on a PC, which is what confirms it is CVBS.

**Open verification item:** confirm the camera is CVBS and not AHD (analog high-def). Check
the camera body for Voyager/ASA or Furrion branding. If it turns out to be AHD, the MAX7456
route below is off the table and the project has to move to a capture-and-recompose design.

### The capture hardware on the office desktop

Two video devices are present, and they behave very differently:

| Device | Device Manager group | Notes |
|---|---|---|
| `USB Video` | Cameras | **This is the grabber.** MacroSilicon chip, `VID_534D&PID_0021`. |
| `HD Pro Webcam C920` | Imaging devices | Logitech webcam, not part of this project. |

Hard-won facts about reaching them from OpenCV on Windows — all measured, not assumed:

- **DirectShow cannot open the grabber at all** when it has no input signal. Media Foundation
  can, and simply delivers no frames until video arrives. So MSMF is required as a fallback or
  the grabber is invisible.
- **DirectShow is far faster to open** — under a second for the webcam against about eleven
  seconds for MSMF. So the probe tries DirectShow first and falls back to MSMF, preferring
  whichever actually delivers frames. A full scan takes roughly five seconds.
- **DirectShow *enumeration* sees every device including ones it cannot open**, which is where
  the friendly names come from (via `pygrabber`). Enumeration order matches the OpenCV index.
- **A grabber with no signal is a normal state, not an error.** It opens, reports 640x480, and
  sends nothing. The app lists it as "no signal" and the capture loop waits rather than failing —
  which also covers an RV camera wired to reverse gear that only powers up when you shift.
- `OBS Virtual Camera` also enumerates but cannot be opened unless OBS is running, so it is
  filtered out of the device list.
- **Only one application can hold the grabber at a time.** This cost real debugging time
  once: OBS was running and showing the feed, so the video was obviously fine, yet the app
  reported no frames. Media Foundation still *opened* the device — it just never received
  anything, because OBS owned the stream. Closing OBS fixed it instantly, and the grabber
  then opened on DirectShow with video, cutting the scan to 2.4 s. **Do not leave OBS or any
  video-call app running while using RVBH**, at the desk or in the RV.
- Confirmed working end to end with a live composite source: 640x480 @ 30 fps, sixty frames
  captured with zero empty reads and recorded to a readable clip.

## Chosen approach: analog OSD overlay, inline

Graphics are inserted into the analog signal in real time by dedicated OSD hardware, rather
than digitizing the video and re-encoding it. Two reasons this beats a Raspberry Pi in the
video path, and both are safety-driven — this is a live backing aid:

- **No added latency.** The analog signal is modified on the fly.
- **Fail-safe.** If the microcontroller stops, video passes through untouched. A Pi that
  hangs leaves the driver with a blank screen.

### Stage 1 — bench (current)

**Nootropic Design Video Experimenter** shield, ~$35. RCA video in and out on the board,
so no cable surgery. Overlays a free-form monochrome bitmap.

- **Requires a classic AVR Arduino Uno R3 or Duemilanove (ATmega328P).** It will *not*
  work on an Uno R4 (Renesas RA4M1), Leonardo, Mega, or Arduino Uno Q — the TVout library
  is AVR assembly driving ATmega timers directly.
- Library: <https://github.com/nootropicdesign/arduino-tvout-ve> — the **enhanced** TVout.
  Stock TVout will not work. Installs three folders: `TVout`, `TVoutfonts`, `pollserial`.
- **SYNC SELECT** header: jumper on the two rightmost pins takes sync from V INPUT (overlay
  mode). The other position generates sync from pin 9 for standalone use with no input.
- **OUTPUT SELECT** switch: "Overlay" blends graphics onto incoming video; "Sync only"
  shows graphics on black.
- Pots start fully counter-clockwise. The small 100K (R4) tunes the LM1881 sync separator —
  raise it slightly only if the picture is vertically jumpy.
- Shield uses pins **D2, D6, D7, D8, optionally D9, and A2**. Everything else is free.
- Overlay canvas is **136 x 96**, and **white pixels only — no black outline**, so lines can
  wash out against bright concrete. This is a known limitation of the bench rig.
- Required boilerplate: `initOverlay()` sets the timer registers, and `ISR(INT0_vect)` resets
  `display.scanLine` on vertical sync to keep the buffer locked to the incoming video.

Bring-up order that isolates faults: first "Sync only" with sync from pin 9 and no video
source at all (proves Arduino + library + shield), then real overlay with a live source.

### Stage 2 — in-vehicle (later)

**Holybro Micro OSD V2**, ~$20 — ATmega328P + MAX7456 on one 17.5x35mm board. Crisper output
and its character set has **black-outlined glyphs**, which stay readable on any background.
Notes when we get there: flash it over its serial pads with an FTDI adapter; it has JST-GH
pigtails that need splicing to RCA (composite is just signal + ground); power it 5V from a
12V buck converter and do **not** feed raw RV 12V to BAT+; leave the PAL solder jumper alone.
Availability is thin — several retailers list it out of stock or special-order only, though it
does not look discontinued. Any MAX7456 board is equivalent for our purposes.

What it buys, read off the datasheet rather than the product page:

| | Video Experimenter (TVout-VE) | MAX7456 |
|---|---|---|
| Canvas | 136 x 96 = 13k px | 30 x 13 cells of 12x18 px = **360 x 234 = 84k px** (NTSC) |
| Pixel states | white or nothing | **black, white or transparent** — 2 bits/px, 54 bytes/glyph |
| Framebuffer lives in | AVR SRAM, 1632 of 2048 bytes | the chip — 480 character addresses on-die |
| Extras | none | per-row brightness (RB0-RB15), blink, inverse, gray background, LOS output, auto NTSC/PAL |

Two limitations recorded above actually go away. Black is a real per-pixel attribute, so an
outlined white line is one glyph rather than a hack — that is the fix for lines washing out
against bright concrete. And the vertical collapse improves from 5 scan lines per overlay row
(480/96) to about 2 (480/234), so distances a few scan lines apart stop merging. The SRAM
constraint disappears as well: the display memory lives on the MAX7456 and the AVR only pushes
character codes over SPI.

> **Blocker — the MAX7456 has no fail-safe passthrough, and that contradicts the whole
> rationale for choosing an analog OSD.** VM0 bit 0 is *"Video Buffer Enable: 0 = Enable,
> 1 = Disable (**VOUT is high impedance**)"*. That is a tri-state, not a bypass to VIN, and
> there is no analog path from input to output anywhere in the part. Unpowered or hung, the
> driver gets no picture at all — which is exactly the Raspberry Pi failure mode this design
> rejected. The Video Experimenter has the property; the MAX7456 does not. Restoring it needs
> a normally-closed SPDT relay or an analog video mux routing camera straight to display
> unless the OSD holds it energised: an extra part in the signal path, an extra failure mode,
> and extra space in the enclosure. **Budget for it in the Stage 2 design, not after.**

**It is a character generator, not a framebuffer, so the renderer has to be rewritten.** NTSC
needs 390 cells and the NVM holds only 256 glyphs, so no screen can have every cell unique.
The picture has to be assembled from a reusable tile set — roughly 18 glyphs to place a
horizontal line at any sub-row, a few dozen slope-and-offset tiles for the curved corridor
edges, digits from the stock font, call it 100 of the 256. Workable, but it replaces the
bitmap rasteriser with a tile quantiser and adds a one-time font upload to the NVM.

**Where this leaves Stage 2:** install the Video Experimenter, get a calibrated grid working
in the vehicle, and treat the MAX7456 as v2 once we know what the grid needs to look like on
the road. The renderer rewrite plus the bypass relay is not a drop-in upgrade.

## Calibration — the artifact that only exists at the RV

Lay a tape measure (or cones every 2 ft) straight back from the bumper, record the feed, then
use the **Calibrate tab**: step to the frame where the markers are readable, set a distance,
and click that marker in the image. Each click records the scan line it landed on.

**Vehicle width** is marked the same way: a pole laid across each distance with the RV width
marked on it, clicked as Left edge and Right edge. Both edges at two or more distances give
the dashed corridor. It is drawn as a polyline through the measured points, not a straight
taper, because the camera is wide-angle enough that the true edges curve — more distances
therefore give a truer corridor. Note the first calibration's "left" values are larger in x
than its "right" ones, which is what a mirrored camera view gives; it makes no difference to
the drawing.

**Frame index is per point, not per calibration.** The pole is carried to a new distance for
every shot, so each measurement comes from its own frame. Files predating this fall back to
the calibration-wide value.

Saved as JSON under `calibration/` (default `rvbhCalibration.json`), and deliberately **not**
git-ignored the way `recordings/` is — this cannot be reproduced at a desk or recovered from
memory, so it belongs in version control. Each point stores `distanceFeet`, `scanLine`, and
`overlayRow`; the file also records `frameWidth`/`frameHeight`, because a scan line means
nothing without the frame height it was measured against. `scanLine` plus `frameHeight`
remains the source of truth — `overlayRow` is a convenience for readers that do not want to
redo the arithmetic.

Two things that bit during implementation and are pinned by tests:

- **Round, do not truncate, when mapping a click back to a scan line.** The picture is
  normally scaled down, so flooring picks the top of each band and biased every measurement a
  pixel low — a systematic error in the exact number the feature exists to produce.
- **`ClipBrowser.showFrame()` goes through the slider**, otherwise the transport controls end
  up contradicting the position label.

## Where the project stands (2026-08-24)

The whole chain works end to end and is documented: RV camera to recorded clip, distance and
width calibration, JSON, generated sketch, flashed Arduino, grid and dashed corridor on the
display. All of it is driven from the app - **the Arduino IDE is not needed**, uploading goes
through arduino-cli.

**Before diagnosing an "arduino-cli failed" upload**, read
`docs/troubleshooting/2026-08-25-laptop-bring-up.md`. Two hours went into one of those on the
laptop; the cause was simply that `arduino:avr` had never been installed, and the reason it
took so long is that checks run through the assistant reported a toolchain the machine did not
have. Confirm the environment from a process *you* start, and note that the app now names the
binary, the data directory and the cores it can actually see, and keeps a log in
`logs/rvBackupHelper.log`.

**The camera wiring fault is fixed.** The July footage clipped 3.1% of its pixels at white;
the August footage clips 0.00%. Judge this by *clipping*, not by the black floor - a sunlit
asphalt driveway genuinely contains no black, and `tools/measureVideoLevels.py` was itself
corrected on that point.

**Open item: the August calibration was measured on 640x360 footage.** That was an accident -
OBS was used instead of the app's own Capture tab, and it fits a 4:3 composite source onto a
16:9 canvas. It matters because the shield overlays the *full* frame, so a mapping measured on
a cropped capture will not line up on the vehicle. A re-recording at 640x480 was planned; use
the app's Capture tab and this cannot happen.

Calibration files carry a date prefix: `calibration/260730rvbhCalibration.json` (7 points,
640x480, correct geometry, washed-out footage) and `260819rvbhCalibration.json` (9 points out
to 24 ft, 640x360, clean footage, wrong geometry). Sketches match: `arduino/rvbhGridV1/` and
`arduino/rvbhGridV2/`.

**Not yet done:** nothing has been flashed and driven in the vehicle with the grid live, and
the overlay figure in the manual is a rendering rather than a photograph because no hardware
was connected when it was written.

## What the app does now

Two tabs. A separate Review tab was removed as redundant - Calibrate embeds the same
`ClipBrowser`.

- **Capture** - device scan by Windows name, live preview, recording, and **Arduino Grid:
  On/Off**, which blanks the shield's overlay over serial so calibration footage is clean.
- **Calibrate** - clip browser plus a measurement panel: distance lines, left/right width
  edges, a points table, Save/Load JSON, **Generate Arduino Sketch...** and **Upload to
  Arduino**. Upload remembers the last sketch generated, across restarts.
- **Help** - **User Manual...** (F1) and **About** with a Donate button matching pySPWB.

Roughly 223 tests. Two of them touch real hardware paths and skip cleanly without it: the
sketch compile test needs arduino-cli, and it also asserts at least 200 bytes of stack remain.

## The manual

`docs/manual/` - index plus four pages (hardware setup, capturing footage, calibrating, sketch
and upload) with screenshots in `images/`. Modelled on the pySPWB manuals.

Screenshots are produced by driving the app against the real calibration and its source clip,
not mocked. If the UI changes, regenerate them rather than letting them drift.

**Help > User Manual** prefers the published copy on GitHub - the repo is public now, and
GitHub draws the screenshots inline where a local `.md` opens in a text editor. It checks
reachability with a HEAD request on a worker thread first, because `openUrl` reports that a
browser launched, not that the page loaded. With no network it opens `appConfig.manualPath`,
which is derived at import from where the package sits and so follows any checkout.

## The Uno is out of RAM, and the compiler hides it

This is the constraint that will bite any future change to the sketch.

`TVout::begin()` mallocs `(136/8) * 96 = 1632` bytes at runtime and pollserial mallocs 64
more, so **1696 of the Uno's 2048 bytes are gone before anything else runs** — and none of it
appears in the compiler's "global variables" figure. A build reporting "4% of dynamic memory"
is not roomy.

Two things keep it viable, and both were needed:

- **pollserial, never HardwareSerial.** Its static 64-byte receive and transmit buffers took
  globals to 354, leaving about 60 bytes of stack, which will not run. pollserial ships with
  TVout-VE for exactly this, and polls from `set_hbi_hook` during blanking rather than from an
  interrupt, so it also stays clear of video generation.
- **Grid tables and labels in PROGMEM**, read back with `memcpy_P` and drawn with
  `tv.printPGM`. That took globals from 201 to 99, leaving roughly 250 bytes of stack.

`testSketchCompiles.py` asserts at least 200 bytes of stack remain after both allocations, so
this cannot creep back silently as more calibration points are added.

## Turning the overlay off from the app

Capture tab, beside Start Recording. Calibration footage must be recorded with the grid off:
a burned-in grid sits on top of the very markings you need to click afterwards, which is what
spoiled the first calibration.

The sketch takes single-character commands (`g`, `c`, `?`) over serial and answers with its
state. **The wanted state lives in EEPROM** because opening a serial port resets the Uno and
no host can avoid that; without it, closing the port would bring the grid straight back. The
port is opened and closed per command rather than held, so `arduino-cli` can still upload.

The bring-up sketch does not accept commands — the toggle reports that rather than hanging.

## Sketch generation

**Generate Arduino Sketch…** renders the calibration into `arduino/rvbhGrid/rvbhGrid.ino`
(the `.ino` must sit in a folder of the same name — an Arduino IDE requirement). Committed,
not ignored. The header repeats the board, library and jumper requirements so the sketch is
self-contained once it leaves this repo.

- **Lines are drawn full width, deliberately.** The calibration measures vertical mapping
  only, so tapering them for perspective would imply a width nobody measured. Vehicle-width
  guides would need horizontal calibration — marking the left and right edges of a known
  width at each distance — which the tool does not collect yet. That is the obvious next
  feature if the plain lines prove insufficient in use.
- **Watch for OSD row collisions.** Capture is 480 tall against the shield's 96, so distances
  within about 5 scan lines rescale onto the same row and cannot be drawn apart. The panel
  warns before generating.
- **SRAM is the real constraint, and the compiler hides it.** `TVout::begin()` *mallocs* the
  frame buffer at runtime — `(136/8) x 96 = 1632` bytes — so it never appears in the "global
  variables" figure. A clean build reports 89 bytes used and 1959 free, which looks roomy and
  is not: about 300 bytes remain for the stack once `begin()` runs. Move the labels into
  PROGMEM before adding many more lines.
- **`begin()` returns non-zero if that malloc fails**, and the failure is otherwise silent —
  the shield passes video through regardless, so the driver just sees no grid. The generated
  sketch checks it and blinks the on-board LED forever instead, which the shield leaves free.

### Verified by a real compile

`arduino-cli` 1.5.1 is installed on the office desktop (winget `ArduinoSA.CLI`), with the
`arduino:avr` core and the three TVout-VE libraries in `Documents\Arduino\libraries`. The
generated sketch builds clean for `arduino:avr:uno`: 6552 bytes of flash (20%).

`tests/testServices/testSketchCompiles.py` runs that compile as part of the suite and skips
itself when the toolchain is absent, so it does not break a machine without it. **The laptop
will need the same three installs before the RV trip.**

## Hardware bring-up — done, and it works

Validated on the office desktop on 2026-07-27 with `arduino/rvbhBringUp/`, a hand-written
diagnostic that draws a border, three labelled reference rows and a block sweeping along the
bottom as proof the loop is running.

- Board is a **genuine Arduino Uno on COM3**, auto-detected as `arduino:avr:uno`. No CH340
  driver needed — that concern applies only to clones, so it stays on the laptop checklist.
- Upload with `arduino-cli upload --port COM3 --fqbn arduino:avr:uno --verify`. Success is
  quiet: it prints only `New upload port: COM3 (serial)` and exits 0. avrdude's progress
  output needs `-v`; its absence is not a failure.
- **The full chain is proven**: composite in → shield overlays the Arduino buffer → composite
  out → USB grabber → the app. Confirmed by capturing the shield's own output through
  `CameraService` and reading the overlay text off the frame.
- The bring-up build is 7930 bytes of flash (24%) with the overlay path enabled.

**The one trap worth remembering.** `USE_OVERLAY 0` free-runs its own sync. Flashed onto a rig
wired for Overlay (SYNC SELECT on V INPUT, OUTPUT SELECT on Overlay) the pattern still appears
but drifts against the incoming video — torn, doubled, with a wavy vertical tear. It reads as
broken hardware and is not: setting `USE_OVERLAY 1` made it rock steady with no wiring change.
Tearing means the build and the jumpers disagree.

Still ahead: the calibrated grid sketch has been compiled but never flashed, and no real RV
camera has been through the shield.

## Overlay jitter — what is and is not known

The overlay wanders vertically by a few pixels. `tools/measureOverlayJitter.py` turns that
into a number by tracking each horizontal line through a search window across ~150 captured
frames. Lower is better.

**The measurement is noisier than the things being measured.** Repeat runs of *identical*
firmware on the bench source came out at 1.32, 2.72, 3.24, 3.37 and 5.51 px. So:

- Any firmware comparison from a single pair of runs is worthless. Always repeat three or
  four times, which is why the tool defaults to `--repeat 3`.
- Static draw versus animated redraw, and `tv.delay_frame()` versus Arduino `delay()`, all
  looked different in one-shot comparisons but none of those gaps survives the spread. The
  static default is kept because it does no worse and matches the generated sketch, **not**
  because it was shown to be better.
- The whole overlay also sits a few pixels lower or higher from run to run, which points at
  the incoming sync rather than at anything running on the Arduino.

**Field observation (2026-07-27):** adjusting R4 improves it briefly and then it drifts back,
repeatedly; left alone it cycles slowly between very good and mediocre. That fits a source
whose sync *amplitude* is wandering — R4 sets the LM1881 slicing threshold, so a moving sync
level means a moving ideal threshold and you chase it forever. The slow cycling also fits a
beat between the wobbling field rate and TVout's internal timing.

**Resolved — it was the bench source.** The prediction was that a crystal-locked camera would
hold one R4 setting instead of needing to be chased. Confirmed in the vehicle: "the jitter is
totally gone while using a real camera signal in the RV." The test footage is VHS-grade and
VHS timebase error is exactly this symptom.

So **do not chase jitter on the bench**, and do not let a bench measurement drive a firmware
change. If it ever reappears against the RV camera, the analysis above is wrong and the cause
is on the shield; the first physical lever is still to turn R4 up slightly, which the nootropic
build notes name as the fix for vertical jumpiness.

## Repo layout beyond the template

- `src/rvBackupHelper/` — the PySide6 app (capture and calibration UI). Standard template layout.
- `arduino/` — Arduino sketches, one folder per sketch as the Arduino tools require:
  `rvbhBringUp/` (hardware proving, takes no commands), `rvbhGridV1/`, `rvbhGridV2/`.
- `calibration/` — measured scanline-to-distance data, date-prefixed.
- `docs/manual/` — the user manual, markdown plus `images/`. Reachable from Help > User Manual.
- `tools/` — measurement scripts that answer questions the app cannot: `measureOverlayJitter.py`
  and `measureVideoLevels.py`. Judge footage by its clipping percentage, not its black floor.
- `recordings/` — git-ignored; video must never reach GitHub.

## Workflow

Development is proven on the **office desktop** first, then the repo is cloned onto a
**laptop** and taken into the RV to work against the real camera feed.

The desktop phase is done when a live composite source shows the grid burned into the picture,
recorded through the USB grabber. Testing only in "Sync only" mode proves the Arduino works but
not that the overlay survives a real signal. An HDMI-to-composite converter (~$12) turns existing
recordings into a real composite source, so calibration can be rehearsed at the desk.

**Before leaving the office**, the laptop needs: Python 3.14+, **arduino-cli** with the
`arduino:avr` core, the TVout-VE library, and the **CH340 USB driver** (most clone Unos need
it). The Arduino IDE is optional now — the app compiles and flashes through arduino-cli, so
the IDE is only for editing a sketch by hand. Claude Code needs internet — if the RV is parked
without signal, plan on phone tethering.

## Predecessor

<https://github.com/Charette-AI-Group/RVBH> — archive only, do not build on it. It holds the
original custom video recorder (Python 3.9 + PyQt6, pinned low because `pyqt6-tools` broke above
3.9) inside a web of shared submodules. This repo is a clean restart on Python 3.14 + PySide6.
The old recorder is still worth reading for reference: `aimlApp/aimlGUI.py` in that repo.
