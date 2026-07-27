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

Lay a tape measure (or cones every 2 ft) straight back from the bumper, record the feed, and
map real-world distances to scan lines. Store the result as a **data file under `calibration/`**
that both the sketch generator and the Qt app read — never as magic numbers typed into a sketch.
This cannot be reproduced at a desk and cannot be recovered from memory.

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
