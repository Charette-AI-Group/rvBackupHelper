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

## Calibration — the artifact that only exists at the RV

Lay a tape measure (or cones every 2 ft) straight back from the bumper, record the feed, then
use the **Calibrate tab**: step to the frame where the markers are readable, set a distance,
and click that marker in the image. Each click records the scan line it landed on.

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

## Repo layout beyond the template

- `src/rvBackupHelper/` — the PySide6 app (capture, review, calibration UI). Standard template layout.
- `arduino/` — Arduino sketches. Not a Python package; lives beside `src/`.
- `calibration/` — measured scanline-to-distance data.

## Workflow

Development is proven on the **office desktop** first, then the repo is cloned onto a
**laptop** and taken into the RV to work against the real camera feed.

The desktop phase is done when a live composite source shows the grid burned into the picture,
recorded through the USB grabber. Testing only in "Sync only" mode proves the Arduino works but
not that the overlay survives a real signal. An HDMI-to-composite converter (~$12) turns existing
recordings into a real composite source, so calibration can be rehearsed at the desk.

**Before leaving the office**, the laptop needs: Python 3.14+, the Arduino IDE, the TVout-VE
library, and the **CH340 USB driver** (most clone Unos need it). Claude Code needs internet —
if the RV is parked without signal, plan on phone tethering.

## Predecessor

<https://github.com/Charette-AI-Group/RVBH> — archive only, do not build on it. It holds the
original custom video recorder (Python 3.9 + PyQt6, pinned low because `pyqt6-tools` broke above
3.9) inside a web of shared submodules. This repo is a clean restart on Python 3.14 + PySide6.
The old recorder is still worth reading for reference: `aimlApp/aimlGUI.py` in that repo.
