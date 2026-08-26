# RV Backup Helper

RV backup camera video capture, grid calibration and OSD overlay tooling

## One-time setup

```powershell
cd W:\projects\26rvBackupHelper
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Daily workflow

```powershell
cd W:\projects\26rvBackupHelper
.\.venv\Scripts\Activate.ps1
rv-backup-helper
```

Or without the script entry point:

```powershell
python -m rvBackupHelper.main
```

Or just double-click **`runApp.cmd`** in the project folder (needs the one-time setup done first).

## User manual

A step-by-step walkthrough with screenshots lives in
[`docs/manual/`](docs/manual/README.md): the hardware rig, recording behind the
RV, calibrating, and generating and flashing the sketch. The notes below are the
quick reference.

## Using the app

> **Close OBS first.** Only one application can hold a capture device at a time. If OBS (or
> a video-call app) is running with the grabber as a source, RVBH opens the device but
> receives no frames — even though the video is plainly visible in OBS.

**Capture tab** — press **Scan Devices** to find capture hardware. Devices are listed by
their Windows name, so the grabber (`USB Video`) is easy to tell from a webcam. A device
that opens but is not receiving video is listed as **no video** rather than hidden; hover it
for the reason, which is either nothing connected or another app holding the device. The
scan opens and closes each device in turn and takes a few seconds; it runs off the GUI
thread.

Pick the device, press **Start Capture** for a live preview, and **Start Recording** to
write a clip.

**Arduino Grid: On / Off** beside the recording controls turns the shield's overlay off, so
the camera passes through clean. **Record calibration footage with it off** — a grid burned
into the clip sits right on top of the markings you need to click afterwards. It needs the
generated grid sketch flashed (the bring-up sketch takes no commands) and takes a couple of
seconds, because opening a serial port resets the board. The state is kept in the Arduino's
EEPROM, so it survives that reset, an unplug, and closing the app.

Starting capture on a device with no signal is fine: the preview shows "Waiting for video
signal" and starts as soon as video arrives, which is what an RV camera powered only in
reverse gear needs.

Clips are timestamped `.avi` files, MJPG encoded. MJPG compresses each frame on its own,
so every frame decodes independently and seeking is frame-exact — which is what calibration
measurements need.

They are written to `recordings/` inside the project by default, which is **git-ignored** so
video never reaches GitHub. Change the destination with **File → Recordings Folder…**; the
choice persists between sessions and the current location is always shown at the right-hand
end of the status bar. Pointing it outside the project is the safer habit — no reliance on
the ignore rule — and it is what you want on the laptop, where clips can go straight to an
external drive.

**Calibrate tab** — a clip browser and a measurement panel side by side. Open a clip and
step through it with the slider, the frame spin box, or Previous/Next; a clip you just
recorded is loaded here automatically. Step to the frame where your distance markers are
readable, set a distance, then **click that marker in the image**. Each click records the scan line it landed
on and draws an amber guide there, so you can see immediately whether it sits on the mark.

The table shows the distance, the **scan line** in the captured frame, the **OSD row** — the
same line rescaled onto the shield's 136x96 canvas, which is what the sketch needs — and the
**Left** and **Right** width edges. Re-marking replaces the earlier value rather than stacking
two guides, so correcting a misplaced click is just clicking again.

**Vehicle width.** If you laid a marked pole across each distance, switch the radio button to
*Left edge* or *Right edge* and click those markings. A green tick shows where each landed.
Mark the distance line first — an edge with no line has nothing to attach to. Two distances
with both edges are enough to draw a corridor; the sketch joins them as **dashed converging
lines**, which is how the driver sees whether the RV will fit.

The corridor is a polyline through the measured points rather than a straight taper, because
the camera is wide-angle enough that the true edges curve across the picture. More measured
distances therefore mean a truer corridor.

Each point records the frame it was measured on, since a pole gets moved between distances
and every measurement comes from its own frame.

**Save…** writes a small JSON file (default `calibration/rvbhCalibration.json`). That file is
**not** git-ignored — it is the one artefact that can only be produced at the RV, so it
belongs in version control. Opening a clip with a different frame size clears the points,
because a scan line only means a distance relative to the height it was measured against.

Precision note: clicks are accurate to about a scan line, and the picture is normally scaled
down to fit the window — maximise the window before marking if you want the tightest reading.

**Generate Arduino Sketch…** turns the calibration into a ready-to-flash `.ino`
(default `arduino/rvbhGrid/rvbhGrid.ino`), with each measured distance as a `GRID[]` row and
the scan line it came from in a trailing comment. The header carries the provenance — source
clip, frame, capture size, timestamp — plus the board, library and shield-jumper requirements,
so the sketch stands on its own away from this repo.

The panel warns before generating if two distances land on the same OSD row: the capture is
five times taller than the shield's canvas, so distances a few scan lines apart can collapse
onto one row that the hardware cannot draw apart.

Sketches are written into a folder of their own name, because the Arduino tools require that
and a second `.ino` sitting beside an existing one is treated as another tab of the same
sketch, which then fails to build. Naming a sketch something other than its folder gets it
its own folder automatically.

**Upload to Arduino** compiles and flashes it with `arduino-cli`, which is exactly what the
IDE's upload button does — **the Arduino IDE is only needed if you want to edit a sketch by
hand.** It takes a few seconds and reports the board's own size summary when it finishes. It
needs `arduino-cli` installed (see below); without it the button says so and points you at
the IDE. It offers the last sketch you generated, remembered between sessions, so a sketch
saved under its own name is still what Upload flashes after a restart.

See **Arduino Grid** on the Capture tab for turning the overlay off before recording.

Each line runs the full width of the picture, **breaking around its own label** so the label
sits in the line rather than floating above it. The overlay is one bit per pixel with no
colour available, so being physically part of the line is what pairs a distance with its
guide. Distances listed in `appConfig.emphasisedDistancesFeet` — 1 ft by default, the "about
to touch something" line — are drawn double thickness, which is the only hierarchy monochrome
allows. Thickness grows downward so the far edge stays on the measured line.

The distance lines are not tapered to suggest perspective: that would imply a width nobody
measured. The vehicle-width corridor is drawn separately, from edges you actually marked.

## Tests and lint

```powershell
pytest
ruff check src tests
```

## Arduino toolchain (optional, for checking generated sketches)

With these installed, the test suite compiles the generated sketch for a real Uno; without
them that one test skips itself. One command does the lot:

```powershell
.venv\Scripts\python.exe tools\setupToolchain.py
```

It installs `arduino-cli` through winget if it is missing, fetches the AVR core (a 295 MB
download, the reason this section exists at all) if that is missing, and then **compiles the
real sketch** and prints which binary, data directory and libraries it used. That last part is
the point: a pass is evidence about this machine, not about a folder somebody looked at once.

`--check` reports without installing anything. `--data-dir arduino\.toolchain` keeps the cores
inside the checkout rather than the machine-wide `Arduino15` folder, which isolates this repo
completely at the cost of that 295 MB per checkout.

By hand, if you would rather:

```powershell
winget install --id ArduinoSA.CLI --exact
arduino-cli core install arduino:avr
```

**The TVout library the shield needs is already here**, in `arduino/libraries` — the Video
Experimenter fork, committed rather than installed because the stock TVout compiles this sketch
perfectly and then leaves the board resetting on every sync pulse. There is nothing to install
and nothing to get wrong, and whatever sits in `Documents\Arduino\libraries` no longer affects
the build. See `arduino/libraries/README.md`.

To compile a sketch by hand the way the app does:

```powershell
$env:ARDUINO_DIRECTORIES_USER = "$PWD\arduino"
arduino-cli compile --fqbn arduino:avr:uno arduino/rvbhGrid
```

## Structure

| Layer | Folder | Purpose |
|-------|--------|---------|
| Entry | `src/rvBackupHelper/main.py` | Start `QApplication`, show main window |
| Config | `src/rvBackupHelper/appConfig.py` | Paths, defaults, app metadata |
| UI | `src/rvBackupHelper/ui/` | Widgets and dialogs only |
| Services | `src/rvBackupHelper/services/` | Business logic (no Qt widgets) |
| Models | `src/rvBackupHelper/models/` | Plain Python data types |

See `AGENTS.md` for architecture and naming conventions (for you and AI agents).

---
*Created from the Qt App Template.*
