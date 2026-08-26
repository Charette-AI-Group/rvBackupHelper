r"""Tests for the toolchain check behind Help > Check Toolchain."""

from __future__ import annotations

import subprocess
from pathlib import Path

from rvBackupHelper import appConfig
from rvBackupHelper.services.board.toolchainService import ToolchainService

compiled = (
    "Sketch uses 8374 bytes (25%) of program storage space. Maximum is 32256 bytes.\n"
    "Global variables use 99 bytes (4%) of dynamic memory.\n"
)
coreMissing = (
    "Error during build: Platform 'arduino:avr' not found: platform not installed\n"
    "Try running `arduino-cli core install arduino:avr`\n"
)


class FakeRunner:
    """Answers each arduino-cli subcommand, recording what was asked."""

    def __init__(self, compileResult: tuple[int, str, str] = (0, compiled, "")) -> None:
        self.compileResult = compileResult
        self.commands: list[list[str]] = []
        self.environments: list[dict[str, str]] = []

    def __call__(self, command, **kwargs):
        self.commands.append(command)
        self.environments.append(kwargs.get("env") or {})
        if "compile" in command:
            code, out, err = self.compileResult
            return subprocess.CompletedProcess(command, code, out, err)
        if command[1:] == ["core", "list"]:
            return subprocess.CompletedProcess(
                command, 0, "ID          Installed Latest Name\narduino:avr 1.8.8 ...\n", ""
            )
        if command[1:] == ["version"]:
            return subprocess.CompletedProcess(command, 0, "arduino-cli Version: 1.5.1\n", "")
        if command[1:] == ["config", "get", "directories.data"]:
            return subprocess.CompletedProcess(command, 0, r"C:\Arduino15" + "\n", "")
        return subprocess.CompletedProcess(command, 0, "", "")


def serviceWith(runner, cli: str | None = "arduino-cli") -> ToolchainService:
    return ToolchainService(
        cliFinder=lambda: cli,
        environmentFactory=lambda: {"ARDUINO_DIRECTORIES_USER": r"W:\repo\arduino"},
        runner=runner,
    )


def testACleanToolchainReportsReady() -> None:
    report = serviceWith(FakeRunner()).check()

    assert report.ok
    assert "Ready" in report.headline
    assert "8374 bytes" in report.headline


def testTheVerdictComesFromACompileNotAListing() -> None:
    """The distinction the whole feature exists for.

    core list said the core was installed while the compiler said it was not,
    and the compiler was right, so the compiler decides here.
    """
    runner = FakeRunner(compileResult=(1, "", coreMissing))

    report = serviceWith(runner).check()

    assert not report.ok
    assert any("compile" in command for command in runner.commands)
    assert "core install" in report.details


def testAFailureNamesWhatTheCompilerUsed() -> None:
    report = serviceWith(FakeRunner(compileResult=(1, "", coreMissing))).check()

    assert "arduino-cli" in report.details
    assert r"C:\Arduino15" in report.details
    assert r"W:\repo\arduino" in report.details
    assert "platform not installed" in report.details


def testTheCheckRunsInTheAppsOwnEnvironment() -> None:
    """A check that reads a different directory than the app is worth nothing."""
    runner = FakeRunner()

    serviceWith(runner).check()

    assert runner.environments
    assert all(
        environment.get("ARDUINO_DIRECTORIES_USER") == r"W:\repo\arduino"
        for environment in runner.environments
    )


def testAMissingCliIsReportedWithoutRunningAnything() -> None:
    runner = FakeRunner()

    report = serviceWith(runner, cli=None).check()

    assert not report.ok
    assert "arduino-cli was not found" in report.headline
    assert "setupToolchain.py" in report.details
    assert runner.commands == []


def testAnIncompleteCheckoutIsNamedAsSuch(monkeypatch, tmp_path: Path) -> None:
    """Missing libraries are a repository problem, not a machine problem."""
    monkeypatch.setattr(appConfig, "arduinoLibrariesDir", tmp_path / "libraries")

    report = serviceWith(FakeRunner()).check()

    assert not report.ok
    assert "checkout is incomplete" in report.details
    assert "install them by hand" in report.details


def testTheBringUpSketchIsCheckedWhenNoGridHasBeenGenerated(
    monkeypatch, tmp_path: Path
) -> None:
    """A machine wants checking before a calibration exists, not after."""
    arduinoDir = tmp_path / "arduino"
    bringUp = arduinoDir / appConfig.bringUpSketchName
    bringUp.mkdir(parents=True)
    (bringUp / f"{appConfig.bringUpSketchName}.ino").write_text("void setup(){}")
    monkeypatch.setattr(appConfig, "arduinoDir", arduinoDir)
    runner = FakeRunner()

    report = serviceWith(runner).check()

    assert report.ok
    assert str(bringUp) in report.details


def testTheRealSketchIsPreferredWhenItExists() -> None:
    runner = FakeRunner()

    report = serviceWith(runner).check()

    assert str(appConfig.arduinoDir / appConfig.sketchName) in report.details


def testARunnerThatExplodesStillProducesAReport() -> None:
    """The report is the product; a traceback would say less than a failure."""

    def explode(*args, **kwargs):
        raise OSError("the binary vanished")

    report = serviceWith(explode).check()

    assert not report.ok
    assert "did not compile" in report.headline
    assert "the binary vanished" in report.details
