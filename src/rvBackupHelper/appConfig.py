"""Application configuration — paths, defaults, and metadata."""

from __future__ import annotations

from pathlib import Path

appName = "RV Backup Helper"
appVersion = "0.1.0"
organizationName = "Charette AI Group"

# Help > About contents
editorName = "Francois Charette, PhD"
aiAgentName = "Claude - Opus 5"
copyrightHolder = "Charette AI Group, LLC"
repoUrl = "https://github.com/Charette-AI-Group/rvBackupHelper"
# The published manual is preferred: GitHub renders the markdown and its
# screenshots, which a local .md in a text editor does not. The copy in a
# checkout is the fallback for when there is no network.
manualUrl = f"{repoUrl}/blob/main/docs/manual/README.md"
# How long to wait for the published copy before giving up and going local.
manualTimeoutSeconds = 3.0

# Donate button, matching the sibling Charette AI Group applications so they
# look like they come from the same place.
donateUrl = "https://www.paypal.com/donate/?hosted_button_id=FEM4WLD7LHY36"
donateColour = "#f0b232"
donateTextColour = "#1f1e1b"
donatePressedColour = "#d9991f"

projectRoot = Path(__file__).resolve().parents[2]
manualPath = projectRoot / "docs" / "manual" / "README.md"
resourcesDir = Path(__file__).resolve().parent / "resources"
windowTitle = appName
defaultWindowWidth = 1000
defaultWindowHeight = 700

# --- Logging -------------------------------------------------------------

# runApp.cmd launches pythonw, which has no console, so anything written to
# stdout or stderr is discarded. Without a file the services' log calls go
# nowhere and a failure at the vehicle leaves no trace to read afterwards.
# Kept beside the app rather than under AppData so it can be found without
# knowing where Windows hides things; *.log is already git-ignored.
logsDir = projectRoot / "logs"
logPath = logsDir / "rvBackupHelper.log"
# Small enough to open in a text editor, with a couple of previous runs kept.
logMaxBytes = 1_000_000
logBackupCount = 3
logFormat = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"

# --- Video capture -------------------------------------------------------

recordingsDir = projectRoot / "recordings"

defaultDeviceIndex = 0
defaultFrameWidth = 640
defaultFrameHeight = 480
defaultFramesPerSecond = 30.0

# OpenCV exposes no device enumeration API. When friendly names are available
# they bound the probe; otherwise listDevices() falls back to probing indices
# 0..maxDeviceProbeIndex - 1.
maxDeviceProbeIndex = 8

# How long the capture loop waits for frames before declaring the signal dead.
# A capture dongle with nothing plugged in opens fine and simply sends nothing,
# and an RV camera powered only in reverse gear arrives late by design — so
# waiting is the normal case, not an error.
signalTimeoutSeconds = 30.0
# How long to pause between retries while waiting for a signal.
signalRetrySeconds = 0.1

# MJPG in an AVI container compresses each frame independently, so every frame
# decodes on its own and seeking during review is frame-exact. Calibration
# measures distances off individual frames, so exact seeking matters more than
# the smaller files an inter-frame codec would give.
recordingFourcc = "MJPG"
recordingExtension = ".avi"

# --- Calibration ---------------------------------------------------------

# Small JSON, and the one artefact that can only be produced at the RV, so it
# is version controlled rather than ignored the way recordings are.
calibrationDir = projectRoot / "calibration"
calibrationExtension = ".json"
defaultCalibrationName = f"rvbhCalibration{calibrationExtension}"

# The Video Experimenter shield draws into a fixed monochrome buffer. Measured
# scan lines are rescaled onto it to become rows in the Arduino sketch.
overlayCanvasWidth = 136
overlayCanvasHeight = 96

# Sensible bounds for a distance entered while calibrating, in feet. Zero is
# allowed on purpose: the first real calibration wanted a line on the bumper
# itself, and a 0.5 minimum forced that to be hand-edited into the saved file.
minimumDistanceFeet = 0.0
maximumDistanceFeet = 200.0
defaultDistanceFeet = 3.0

# --- Arduino sketch ------------------------------------------------------

# The Arduino IDE requires a sketch to sit in a folder of the same name.
arduinoDir = projectRoot / "arduino"
# arduino/ is also handed to arduino-cli as its sketchbook, which is what makes
# arduino/libraries the library path. The TVout-VE fork is committed there
# because the stock TVout builds this sketch happily and then leaves the board
# resetting on every sync pulse - a failure with no useful symptom, and one no
# check in the repo could catch while the library was a manual copy into
# Documents\Arduino\libraries.
arduinoUserDir = arduinoDir
arduinoLibrariesDir = arduinoUserDir / "libraries"
# The libraries the sketch cannot build without, used to tell a checkout that
# is missing them from a toolchain that is merely not installed.
requiredLibraries = ("TVout", "TVoutfonts", "pollserial")
sketchName = "rvbhGrid"
# The hand-written diagnostic sketch, used to check the toolchain before any
# calibration exists to generate from. It needs the same core and the same
# libraries, so compiling it proves the same things.
bringUpSketchName = "rvbhBringUp"
sketchExtension = ".ino"

# Distances drawn with a heavier line, in feet. The overlay is one bit per
# pixel with no colour available, so line weight is the only way to give the
# driver a hierarchy. 1 ft is the "about to touch something" line.
emphasisedDistancesFeet = (1.0,)
emphasisedThickness = 2
# Clear space either side of a label where its line is broken for it.
labelGapPixels = 2
# Dash on/off run for the vehicle-width edges, in canvas pixels. Dashes keep
# them reading as a corridor rather than as more distance lines.
dashLengthPixels = 3

# --- Talking to the board ------------------------------------------------

# The sketch listens for single-character commands so the overlay can be
# blanked while recording calibration footage; a burned-in grid hides the very
# markings you are trying to click.
commandBaud = 9600
gridOnCommand = "g"
gridOffCommand = "c"
gridQueryCommand = "?"
# Opening a serial port resets the Uno, so the wanted state lives in EEPROM and
# survives the reset the host cannot avoid causing.
gridStateAddress = 0
# The bootloader runs before the sketch starts listening.
boardResetSeconds = 2.0
serialTimeoutSeconds = 2.0
# USB vendor ids: Arduino LLC, and the CH340 most clones use.
boardVendorIds = (0x2341, 0x2A03, 0x1A86)

# Uploading sketches without the Arduino IDE. arduino-cli is looked up on PATH
# first; this is where winget puts it when it is not.
arduinoCliPath = r"C:\Program Files\Arduino CLI\arduino-cli.exe"
boardFqbn = "arduino:avr:uno"
# A cold compile pulls the whole core through; uploading adds a reset and a
# verify pass.
uploadTimeoutSeconds = 300.0
# Asking arduino-cli where it keeps its cores, to name that in a failure. It
# reads a config file and returns, so a short timeout is plenty - and this runs
# while an error is already being reported, where hanging would be worse than
# an incomplete answer.
configQueryTimeoutSeconds = 10.0
