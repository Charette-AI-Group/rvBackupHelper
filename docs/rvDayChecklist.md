# RV day checklist

Written for working at the vehicle, where looking things up is inconvenient.

## Go / no-go, before anything else

**Confirm the camera is composite (CVBS), not AHD.** This has been an open question since
the start and everything downstream depends on it. The shield only handles CVBS.

The test takes a minute: camera into the shield's video IN, shield OUT to the RV display or
the USB grabber. A stable picture with the overlay on it means CVBS. A rolling, torn or
black picture that the shield cannot lock to suggests AHD, and the whole analog-OSD approach
is off — say so early rather than spending the day fighting it.

## Traps that will cost you an hour each

- **The camera may only be powered in reverse gear.** Many RV cameras are wired that way. If
  nothing appears, check that before suspecting the shield. Ignition on, in reverse.
- **Only one application can hold the USB grabber.** Close OBS and any video-call app before
  running RVBH, or it opens the device and receives nothing while the video is plainly fine.
- **A torn or doubled overlay means the build and the jumpers disagree**, not broken hardware.
  `USE_OVERLAY 1` goes with SYNC SELECT on the two rightmost pins and OUTPUT SELECT on
  Overlay. `USE_OVERLAY 0` goes with pin-9 sync and Sync only.
- **The Arduino needs 5 V.** Laptop USB is fine; a USB car adapter also works.
- **A board that uploads cleanly and then answers nothing has the wrong TVout**, not a serial
  fault. The stock library leaves the input capture interrupt the overlay enables with no
  handler, so the board resets on every sync pulse and never reads a command, and nothing about
  the upload looks wrong. Uploading from the app can no longer hit this - it compiles against
  the copy committed in `arduino/libraries` - so suspect it only after running `arduino-cli` by
  hand without `ARDUINO_DIRECTORIES_USER` set. The generated sketch refuses to build against the
  stock library anyway (`'capture' is not a member of 'TVout'`).

## What is already flashed

`arduino/rvbhBringUp` built with `USE_OVERLAY 1`, static draw. It puts a border, three
labelled reference rows and the mode on screen — enough to judge stability and to see where
the overlay lands on the real rear view before trusting any measured line.

## Sequence for the day

1. **Prove the signal.** Camera → shield IN, shield OUT → display or grabber. Look for the
   bring-up pattern over the live rear view.
2. **Settle the jitter question.** Set R4 once and leave it. On a bench tape it had to be
   chased constantly; a crystal-locked camera should hold one setting. Measure rather than
   squint:

   ```powershell
   .venv\Scripts\python.exe tools\measureOverlayJitter.py "RV camera, R4 as set" --repeat 4
   ```

   Repeat runs matter: identical firmware measured 1.3 to 5.5 px on the bench, so a single
   reading proves nothing.
3. **Record the calibration run.** Lay a tape measure or cones straight back from the bumper
   at the distances you care about. Capture tab → Scan Devices → Start Capture → Start
   Recording. Get the markers clearly in frame; a few seconds is plenty.
4. **Mark the distances.** Calibrate tab → open that clip → step to the clearest frame →
   set each distance and click its marker. Maximise the window first; clicks resolve to about
   a scan line and the picture is scaled to fit.
5. **Save the calibration.** This is the only artefact that cannot be reproduced at a desk.
   Save it, then commit and push before leaving.
6. **Generate and flash the grid.** Generate Arduino Sketch…, then:

   ```powershell
   arduino-cli compile --fqbn arduino:avr:uno --upload --port COM3 --verify arduino/rvbhGrid
   ```

   Check the port with `arduino-cli board list` — it is unlikely to be COM3 on the laptop.

## Laptop prerequisites — do these before leaving

Nothing here downloads quickly on campground wifi.

**Install everything by following *One-time setup* in the README**, which is written for a
machine with nothing on it and is the only place that list is kept. Then, before leaving:

- Prove the toolchain **on the laptop itself**, and accept nothing less than this tool's own
  final line as proof:

  ```powershell
  .venv\Scripts\python.exe tools\setupToolchain.py --check
  ```

  A core reported present by a check run somewhere else is what cost two hours on 2026-08-25;
  see `docs/troubleshooting/2026-08-25-laptop-bring-up.md`.
- Run `pytest` once, from your own terminal, for the same reason. The sketch compile test must
  pass rather than skip — a skip means the AVR core is not there.
- **CH340 USB driver** if the Uno you are packing is a clone. The desktop's board is genuine
  and needed none, so this is easy to forget. Plug the board in and confirm it appears, rather
  than assuming.
- Confirm the **USB video grabber** works on the laptop, not only on the desktop.
- Claude Code needs internet. If the RV is parked without signal, plan on phone tethering.

## To pack

Uno, Video Experimenter shield, USB cable, USB video grabber, RCA leads (plus whatever
adapter reaches the camera and the display header), laptop and charger, tape measure or
cones, and something to write measurements on in case a reading has to be redone later.
