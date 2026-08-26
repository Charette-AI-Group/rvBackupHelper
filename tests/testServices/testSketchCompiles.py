"""Compiles the generated sketch with the real Arduino toolchain.

The sketch is the artefact that gets flashed to hardware, so "it looks right"
is not enough. Skipped when arduino-cli or the AVR core is absent, so the
suite still runs on a machine without the toolchain.

The libraries are not a reason to skip any more: they are committed in
arduino/libraries and compiled against through ARDUINO_DIRECTORIES_USER, the
same way the app compiles. That also makes this file test the arrangement it
relies on - a vendored copy that was wrong or missing fails here instead of
quietly skipping.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from rvBackupHelper import appConfig
from rvBackupHelper.models.calibrationModels import Calibration, CalibrationPoint
from rvBackupHelper.services.board.uploadService import toolchainEnvironment
from rvBackupHelper.services.sketch.sketchService import SketchService

fqbn = "arduino:avr:uno"
installedCliPath = Path(r"C:\Program Files\Arduino CLI\arduino-cli.exe")

unoSram = 2048
# Both of these are malloc'd at runtime, so the compiler's "global variables"
# figure excludes them and a clean build looks far roomier than it is. Adding
# HardwareSerial once left about 60 bytes of stack, which is not enough to run;
# this is the guard against that recurring as more calibration points are added.
frameBufferBytes = 136 // 8 * 96
pollserialBufferBytes = 64
heapBytes = frameBufferBytes + pollserialBufferBytes
minimumStackBytes = 200

globalsReported = re.compile(r"Global variables use (\d+) bytes")


def freeStackBytes(compilerOutput: str) -> int:
    match = globalsReported.search(compilerOutput)
    assert match, f"could not read RAM use from:\n{compilerOutput}"
    return unoSram - int(match.group(1)) - heapBytes


def findArduinoCli() -> str | None:
    onPath = shutil.which("arduino-cli")
    if onPath:
        return onPath
    return str(installedCliPath) if installedCliPath.exists() else None


def avrCoreInstalled(cli: str) -> bool:
    """The 295 MB half of the toolchain, the half that cannot be committed.

    Checked here rather than left to the compiler, because "platform not
    installed" in the middle of a failed compile reads as a broken sketch.
    """
    result = subprocess.run(
        [cli, "core", "list"],
        capture_output=True,
        text=True,
        timeout=120,
        env=toolchainEnvironment(),
    )
    return "arduino:avr" in result.stdout


arduinoCli = findArduinoCli()
needsToolchain = pytest.mark.skipif(
    arduinoCli is None or not avrCoreInstalled(arduinoCli),
    reason="the Arduino toolchain is not installed - run tools/setupToolchain.py",
)


def compileSketch(calibration: Calibration, tmp_path: Path) -> subprocess.CompletedProcess:
    assert arduinoCli is not None
    # The Arduino IDE requires the .ino to sit in a folder of the same name.
    sketchDir = tmp_path / "rvbhGrid"
    SketchService().save(calibration, sketchDir / "rvbhGrid.ino")
    return subprocess.run(
        [arduinoCli, "compile", "--fqbn", fqbn, str(sketchDir)],
        capture_output=True,
        text=True,
        timeout=600,
        # The libraries in the repo, not whatever the machine happens to have.
        env=toolchainEnvironment(),
    )


@needsToolchain
def testTheCompileUsesTheVendoredLibraries() -> None:
    """Guards the arrangement the rest of this file depends on."""
    assert os.environ.get("ARDUINO_DIRECTORIES_USER") != str(appConfig.arduinoUserDir), (
        "already set outside the process, so this would pass without proving anything"
    )
    assert toolchainEnvironment()["ARDUINO_DIRECTORIES_USER"] == str(
        appConfig.arduinoUserDir
    )
    for name in appConfig.requiredLibraries:
        assert (appConfig.arduinoLibrariesDir / name).is_dir(), f"{name} is not vendored"


@needsToolchain
def testGeneratedSketchCompilesForAnUno(tmp_path: Path) -> None:
    calibration = Calibration(
        frameWidth=640,
        frameHeight=480,
        points=[
            CalibrationPoint(3.0, 430),
            CalibrationPoint(6.0, 372),
            CalibrationPoint(10.0, 330),
            CalibrationPoint(15.0, 300),
        ],
        sourceClip="rvbh-20260727-101154.avi",
        frameIndex=137,
    )

    result = compileSketch(calibration, tmp_path)

    assert result.returncode == 0, (
        f"sketch did not compile:\n{result.stdout}\n{result.stderr}"
    )
    assert "Sketch uses" in result.stdout


@needsToolchain
def testSketchWithVehicleWidthCompiles(tmp_path: Path) -> None:
    """The dashed-corridor path is a whole extra body of generated C."""
    calibration = Calibration(
        frameWidth=640,
        frameHeight=480,
        points=[
            CalibrationPoint(0.0, 461, leftEdge=40, rightEdge=600, frameIndex=1853),
            CalibrationPoint(4.0, 316, leftEdge=120, rightEdge=520, frameIndex=2265),
            CalibrationPoint(8.0, 193, leftEdge=180, rightEdge=460, frameIndex=3089),
            CalibrationPoint(20.0, 23, leftEdge=250, rightEdge=390, frameIndex=3913),
        ],
        sourceClip="rvbh-20260730-100335.avi",
    )

    result = compileSketch(calibration, tmp_path)

    assert result.returncode == 0, (
        f"width sketch did not compile:\n{result.stdout}\n{result.stderr}"
    )
    assert "Sketch uses" in result.stdout

    # The fullest sketch is the one most likely to run the Uno out of memory.
    free = freeStackBytes(result.stdout)
    assert free >= minimumStackBytes, (
        f"only {free} bytes left for the stack once the {heapBytes} bytes of "
        f"runtime allocations are taken; needs at least {minimumStackBytes}"
    )
