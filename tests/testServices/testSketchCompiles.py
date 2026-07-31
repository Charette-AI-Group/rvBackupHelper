"""Compiles the generated sketch with the real Arduino toolchain.

The sketch is the artefact that gets flashed to hardware, so "it looks right"
is not enough. Skipped when arduino-cli or the TVout-VE library is absent, so
the suite still runs on a machine without the toolchain.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from rvBackupHelper.models.calibrationModels import Calibration, CalibrationPoint
from rvBackupHelper.services.sketch.sketchService import SketchService

fqbn = "arduino:avr:uno"
installedCliPath = Path(r"C:\Program Files\Arduino CLI\arduino-cli.exe")
requiredLibraries = ("TVout", "TVoutfonts")


def findArduinoCli() -> str | None:
    onPath = shutil.which("arduino-cli")
    if onPath:
        return onPath
    return str(installedCliPath) if installedCliPath.exists() else None


def librariesInstalled(cli: str) -> bool:
    result = subprocess.run(
        [cli, "lib", "list"], capture_output=True, text=True, timeout=120
    )
    return all(name in result.stdout for name in requiredLibraries)


arduinoCli = findArduinoCli()
needsToolchain = pytest.mark.skipif(
    arduinoCli is None, reason="arduino-cli is not installed"
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
    )


def skipWithoutLibraries() -> None:
    assert arduinoCli is not None
    if not librariesInstalled(arduinoCli):
        pytest.skip("the TVout-VE libraries are not installed")


@needsToolchain
def testGeneratedSketchCompilesForAnUno(tmp_path: Path) -> None:
    skipWithoutLibraries()
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
    skipWithoutLibraries()
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
