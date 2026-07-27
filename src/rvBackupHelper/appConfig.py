"""Application configuration — paths, defaults, and metadata."""

from __future__ import annotations

from pathlib import Path

appName = "RV Backup Helper"
appVersion = "0.1.0"
organizationName = "Charette AI Group"

# Help > About contents
editorName = "Francois Charette, PhD"
aiAgentName = "Claude - Fable 5"
copyrightHolder = "Charette AI Group, LLC"

projectRoot = Path(__file__).resolve().parents[2]
resourcesDir = Path(__file__).resolve().parent / "resources"
windowTitle = appName
defaultWindowWidth = 1000
defaultWindowHeight = 700

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

# Sensible bounds for a distance entered while calibrating, in feet.
minimumDistanceFeet = 0.5
maximumDistanceFeet = 200.0
defaultDistanceFeet = 3.0

# --- Arduino sketch ------------------------------------------------------

# The Arduino IDE requires a sketch to sit in a folder of the same name.
arduinoDir = projectRoot / "arduino"
sketchName = "rvbhGrid"
sketchExtension = ".ino"
