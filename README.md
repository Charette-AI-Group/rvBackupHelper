# RV Backup Helper

RV backup camera video capture, grid calibration and OSD overlay tooling

[**RV Backup Helper on the web**](https://charette-ai-group.github.io/rvBackupHelper/) — what it
does and why, and the whole job walked through in ten steps with screenshots: a pole laid in the
driveway at one end, distance lines on the RV's own screen at the other. Start there if you are
deciding whether to build one; start here if you have decided.

## Install

[**Download the latest release**](https://github.com/Charette-AI-Group/rvBackupHelper/releases/latest)
and run `rvBackupHelperSetup-1.0.0.exe`. Python is not required — the interpreter is bundled —
and the install is per-user, so there is no UAC prompt and nothing lands in Program Files.

It is unsigned, so SmartScreen warns the first time: **More info**, then **Run anyway**. What the
wizard asks, and why it asks in that order, is under [Making an installer](#making-an-installer).

Everything below is the from-source path, which is what you want if you intend to change the code.

## One-time setup

Written for a machine with nothing on it. Three things get installed; the repository and the
setup tool bring the rest.

```powershell
winget install --id Git.Git --exact
winget install --id Python.Python.3.14 --exact
```

**Python must be 3.14 or newer** — `pyproject.toml` requires it, and pip refuses an older one
rather than half-working. Then, in a **new** shell, because winget only puts things on the PATH
of processes started after it:

```powershell
git clone https://github.com/Charette-AI-Group/rvBackupHelper.git
cd rvBackupHelper
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe tools\setupToolchain.py
```

That last line is the third install: it fetches `arduino-cli` and the AVR core if they are
missing, then compiles the sketch to prove it. Confirm the machine with `pytest`, and in the app
with **Help > Check Hardware** and **Help > Check Toolchain**.

Check Hardware needs none of the above and can be run first, on a machine with nothing on it:

```powershell
powershell -ExecutionPolicy Bypass -File tools\checkHardware.ps1
```

It uses only `Get-PnpDevice`, names the board by USB id — so an Uno R4, Leonardo or Mega is
caught before anything is downloaded — and says whether a capture device is present. It cannot
see the Video Experimenter shield, which is passive, and it cannot tell composite from AHD.

| Where it comes from | What you get |
|---|---|
| `pip install -e ".[dev]"` | PySide6, numpy, opencv-python, pygrabber, pyserial, and pytest / pytest-qt / ruff |
| The clone itself | The TVout-VE libraries, in `arduino/libraries` — nothing to install and no wrong version to install |
| `tools\setupToolchain.py` | `arduino-cli`, and the `arduino:avr` core (a 295 MB download) |

Internet is needed for the clone, for pip and for that core. Nothing afterwards: the only call
the app makes is Help > User Manual checking whether the published copy is reachable, and it
falls back to the copy in `docs/manual/`. The Arduino IDE is never needed.

### Drivers, which are the part this repository cannot handle for you

- **A genuine Uno R3 needs no driver** — Windows has the ATmega16U2 serial driver in the box.
  **A clone with a CH340 does**, from the chip vendor. That case is why `boardVendorIds` in
  `appConfig.py` carries `0x1A86` alongside Arduino's own ids.
- **A UVC USB video grabber needs no driver either.** Some cheap EasyCap-style ones want a
  vendor driver; find that out before the day you need the grabber, not on it.

## Daily workflow

```powershell
cd W:\projects\26rvBackupHelper   # wherever you cloned it
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

The two screenshots that need nothing but the application — the About box, which
carries the version, and the empty Calibrate tab — are redrawn rather than
retaken:

```powershell
.venv\Scripts\python.exe tools\makeManualShots.py
```

The rest show real footage and a real grabber, so they are still taken by hand.

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
EEPROM, so it survives that reset, an unplug, closing the app, and a reflash — which is why a
successful **Upload to Arduino** asks for the grid back, so a board blanked for a recording
does not reach the vehicle still blank.

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

## Building a standalone application

Not needed to use the app from a checkout. This is for handing it to somebody who has no
Python.

```powershell
.venv\Scripts\python.exe -m pip install -e ".[build]"
.venv\Scripts\python.exe tools\buildExe.py --smoke
```

That produces `dist\rvBackupHelper\` — about **257 MB**, of which the executable itself is 5 MB
and the rest is PySide6 and OpenCV. A one-folder build rather than one-file, so it starts
immediately instead of unpacking itself on every launch, and so the sketches stay browsable
where they land.

`buildExe.py` then takes an inventory of the bundle, because PyInstaller will happily succeed
while leaving a data file out and the symptom only appears later as a missing manual or a
compile that cannot find `TVout.h`. It fails the build if anything expected is absent, or if
anything that belongs to a user — `arduino/rvbhGrid`, `recordings/`, `calibration/` — has
crept in. `--smoke` also launches the result and confirms it logged a startup, which for a
windowed build with no console is the only proof available.

An installed build reads its manual, libraries and bring-up sketch from the bundle, and writes
everything else under `%LOCALAPPDATA%\RV Backup Helper` — created and seeded on first run, and
named as a link in Help > About.

### Making an installer

`installer\rvBackupHelper.iss` builds a single setup executable with
[Inno Setup 6](https://jrsoftware.org/isinfo.php) (`winget install --id JRSoftware.InnoSetup`):

```powershell
ISCC.exe installer\rvBackupHelper.iss
```

The wizard is ordered so everything cheap happens before anything expensive:

1. **Hardware check**, on the page after Welcome, before a single file is written. It extracts
   `checkHardware.ps1` to a temporary folder and runs it, so somebody with no grabber finds out
   in five seconds rather than after a 295 MB download. There is a **Check again** button for
   plugging things in without restarting the wizard.
2. **The application**, per-user, so no UAC prompt and no Program Files.
3. **`arduino-cli`**, via winget, only if it is not already there.
4. **The package index and arduino-cli's own tools**, always. ctags and the port
   discoveries are not part of the core and are not the 295 MB; arduino-cli fetches them
   itself, but only for an index that describes them. A machine carrying an `Arduino15`
   folder from an older Arduino install has one that does not, and reports them missing
   instead of downloading them — so the index is refreshed first, whatever else is ticked.
5. **The AVR core**, last, as a **tick box** — 295 MB, and only uploading needs it.

Missing hardware warns and asks; it does not block. Calibrating footage and generating a sketch
need no board and no grabber, so refusing to install would turn a warning into a lie. If winget
is absent — Windows Sandbox has none, nor do LTSC and many managed builds — the arduino-cli
step is skipped and setup says so at the end rather than failing mid-install.

The built `dist\rvBackupHelperSetup-<version>.exe` is what gets attached to a
[GitHub release](https://github.com/Charette-AI-Group/rvBackupHelper/releases), which is how it
reaches a machine that is not this one. Keep `AppVersion` in the `.iss` and `version` in
`pyproject.toml` in step with the tag.

### Trying it as somebody who has nothing

`installer\testSandbox.wsb` opens the built installer inside **Windows Sandbox**: a disposable
copy of Windows, clean on every launch and discarded on close. Enable the feature once, in an
administrator PowerShell, then reboot:

```powershell
Enable-WindowsOptionalFeature -Online -FeatureName "Containers-DisposableClientVM" -All
```

Then double-click the `.wsb`. It maps `dist\` in read-only and opens it on the sandbox desktop.
Edit the `HostFolder` line if this clone lives somewhere other than `W:\projects\26rvBackupHelper`.

It has networking, so the 295 MB download is real, and the wizard, the per-user install, the
first-run seeding and the uninstaller all behave as they would on a stranger's machine. It has
**no USB passthrough**, so the hardware page will find nothing — which is worth watching on
purpose, since that is the path a new user with an unopened box will meet.

For the hardware half, a second Windows user account is the cheaper honest test: the install,
the data folder and `%LOCALAPPDATA%\Arduino15` are all clean there, and USB works normally.

## Arduino toolchain

Installed by `tools\setupToolchain.py` in the one-time setup above; this is what it does and
how to interrogate it. Without the toolchain the app cannot upload and the sketch compile test
skips itself; everything else still runs.

The tool ends by **compiling the real sketch** and printing which binary, data directory and
libraries it used. That is the whole point of it: a pass is evidence about this machine, not
about a folder somebody looked at once. A missing core once cost a working day because every
check short of building something insisted it was installed.

```powershell
.venv\Scripts\python.exe tools\setupToolchain.py --check
```

`--check` reports without installing anything. `--data-dir arduino\.toolchain` keeps the cores
inside the checkout rather than the machine-wide `Arduino15` folder, which isolates this repo
completely at the cost of that 295 MB per checkout. **Help > Check Toolchain** in the app runs
the same check and needs no terminal.

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

## Licence

MIT — see [`LICENSE`](LICENSE). That covers this repository's own code, the generated sketches
and the documentation.

The vendored Video Experimenter fork of TVout in `arduino/libraries` is somebody else's work and
carries **its own** MIT licence file, kept beside the code as that licence requires. Nothing here
relicenses it.

---
*Created from the Qt App Template.*
