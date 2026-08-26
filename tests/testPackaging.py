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


installerText = (
    appConfig.projectRoot / "installer" / "rvBackupHelper.iss"
).read_text(encoding="utf-8")


def testTheInstallerShipsWhatTheBuildProduces() -> None:
    assert "dist\\rvBackupHelper" in installerText
    assert "rvBackupHelper.exe" in installerText


def testTheInstallerAsksAboutHardwareBeforeInstallingAnything() -> None:
    """The whole point of the ordering: five seconds, not 295 MB, to find out."""
    assert "checkHardware.ps1" in installerText
    assert "dontcopy" in installerText, "the check must run before files are laid down"
    assert "wpWelcome" in installerText, "the hardware page belongs at the front"


def testTheExpensiveDownloadIsOptionalAndLast() -> None:
    assert "avrcore" in installerText
    assert "295 MB" in installerText


def testMissingHardwareDoesNotBlockTheInstall() -> None:
    """Calibrating and generating need no hardware; refusing would be a lie."""
    assert "MB_YESNO" in installerText


def testWingetIsNeverRunWithoutCheckingItIsThere() -> None:
    """Windows Sandbox has no winget, and neither do LTSC or managed builds.

    Handing Inno a filename that does not exist raises an error dialog in the
    middle of an install, which is a poor way to learn about a dependency.
    """
    runLines = [line for line in installerText.splitlines() if "GetWinget" in line]
    runEntries = [line for line in runLines if line.startswith("Filename:")]

    assert runEntries, "the winget step should still exist"
    for line in runEntries:
        assert "Check: ShouldInstallArduinoCli" in line


def testAMachineWithoutWingetIsToldRatherThanLeftGuessing() -> None:
    assert "winget is not available on this machine" in installerText
    assert "ssPostInstall" in installerText


def testTheSandboxConfigurationIsThere() -> None:
    """A disposable clean Windows is the only honest first-run test."""
    sandbox = appConfig.projectRoot / "installer" / "testSandbox.wsb"
    text = sandbox.read_text(encoding="utf-8")

    assert "<Configuration>" in text
    assert "ReadOnly>true" in text, "the host folder must not be writable from inside"
    assert "Networking>Enable" in text, "the core download is part of what it tests"


def testTheInstalledAdviceDoesNotPointAtAToolThatIsNotThere(monkeypatch) -> None:
    """A frozen build has no Python and no tools folder."""
    from rvBackupHelper.services.board.toolchainService import setupAdvice

    monkeypatch.setattr(appConfig, "frozen", True)
    advice = setupAdvice()

    assert "setupToolchain.py" not in advice
    assert "arduino-cli core install arduino:avr" in advice
