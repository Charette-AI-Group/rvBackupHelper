r"""Guards on what a standalone build ships.

The build itself checks its own output - tools/buildExe.py refuses to call a
bundle shippable when a payload file is missing - but that only runs when
somebody builds. These catch the likelier mistake much earlier: a library added
to appConfig and forgotten in the spec, which would produce an application that
installs cleanly and then cannot compile.
"""

from __future__ import annotations

from rvBackupHelper import appConfig

specText = (appConfig.projectRoot / "rvBackupHelper.spec").read_text(encoding="utf-8")


def testTheSpecExists() -> None:
    assert (appConfig.projectRoot / "rvBackupHelper.spec").is_file()
    assert (appConfig.projectRoot / "tools" / "buildExe.py").is_file()


def testEveryRequiredLibraryIsInThePayload() -> None:
    """Adding one to appConfig and not to the spec builds a broken install."""
    assert "arduino/libraries" in specText
    for name in appConfig.requiredLibraries:
        assert (appConfig.bundledArduinoDir / "libraries" / name).is_dir()


def testTheBringUpSketchIsInThePayload() -> None:
    """Check Toolchain compiles it when no grid has been generated yet."""
    assert appConfig.bringUpSketchName in specText


def testTheManualAndHardwareCheckAreInThePayload() -> None:
    assert "docs/manual" in specText
    assert "checkHardware.ps1" in specText


def testTheGeneratedSketchIsNotShipped() -> None:
    """It is the user's own output, and stale calibration data at that."""
    payloadLines = [
        line for line in specText.splitlines() if "projectRoot /" in line and '"' in line
    ]
    assert payloadLines, "the datas list should name its files"
    assert not any(appConfig.sketchName in line for line in payloadLines)


def testNoConsoleWindowIsAttached() -> None:
    """It logs to a file precisely because it has never had a console."""
    assert "console=False" in specText
