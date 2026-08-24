"""Tests for uploading a sketch without the Arduino IDE."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from rvBackupHelper import appConfig
from rvBackupHelper.services.board.uploadService import UploadError, UploadService

goodOutput = (
    "Sketch uses 8342 bytes (25%) of program storage space.\n"
    "Global variables use 99 bytes (4%) of dynamic memory.\n"
)


class FakeRunner:
    """Stands in for subprocess.run, recording the command it was given."""

    def __init__(self, returncode: int = 0, stdout: str = goodOutput, stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr
        self.command: list[str] | None = None

    def __call__(self, command, **kwargs):
        self.command = command
        return subprocess.CompletedProcess(command, self.returncode, self.stdout, self.stderr)


@pytest.fixture
def sketchDir(tmp_path: Path) -> Path:
    """A correctly laid out sketch: folder and .ino share a name."""
    folder = tmp_path / "rvbhGrid"
    folder.mkdir()
    (folder / "rvbhGrid.ino").write_text("void setup(){}", encoding="utf-8")
    return folder


def serviceWith(runner, cli: str | None = "arduino-cli", port: str | None = "COM3"):
    return UploadService(
        cliFinder=lambda: cli, portFinder=lambda: port, runner=runner
    )


def testUploadRunsCompileWithUploadAndVerify(sketchDir: Path) -> None:
    runner = FakeRunner()

    summary = serviceWith(runner).upload(sketchDir / "rvbhGrid.ino")

    assert runner.command is not None
    assert runner.command[1] == "compile"
    assert "--upload" in runner.command
    assert "--verify" in runner.command
    assert runner.command[runner.command.index("--port") + 1] == "COM3"
    assert runner.command[runner.command.index("--fqbn") + 1] == appConfig.boardFqbn
    # A folder is compiled, never the file itself.
    assert runner.command[-1] == str(sketchDir)
    assert "Sketch uses 8342 bytes" in summary
    assert "COM3" in summary


def testAFolderMayBeGivenInsteadOfAFile(sketchDir: Path) -> None:
    runner = FakeRunner()

    serviceWith(runner).upload(sketchDir)

    assert runner.command[-1] == str(sketchDir)


def testMissingCliPointsAtTheAlternative(sketchDir: Path) -> None:
    service = serviceWith(FakeRunner(), cli=None)

    with pytest.raises(UploadError, match="Arduino IDE"):
        service.upload(sketchDir)


def testMissingBoardIsReported(sketchDir: Path) -> None:
    service = serviceWith(FakeRunner(), port=None)

    with pytest.raises(UploadError, match="No Arduino found"):
        service.upload(sketchDir)


def testMissingSketchFolderIsReported(tmp_path: Path) -> None:
    service = serviceWith(FakeRunner())

    with pytest.raises(UploadError, match="Sketch folder not found"):
        service.upload(tmp_path / "nowhere" / "nowhere.ino")


def testAMismatchedSketchNameIsRefusedBeforeCompiling(tmp_path: Path) -> None:
    """The trap that produced rvbhGridV2.ino inside a rvbhGrid folder."""
    folder = tmp_path / "rvbhGrid"
    folder.mkdir()
    (folder / "rvbhGridV2.ino").write_text("void setup(){}", encoding="utf-8")
    runner = FakeRunner()
    service = serviceWith(runner)

    with pytest.raises(UploadError, match="same name as its folder"):
        service.upload(folder / "rvbhGridV2.ino")

    assert runner.command is None  # refused before arduino-cli was run


def testACompileFailureKeepsTheErrorText(sketchDir: Path) -> None:
    runner = FakeRunner(
        returncode=1,
        stdout="",
        stderr="Compiling...\nrvbhGrid.ino:12:3: error: 'foo' was not declared\n",
    )
    service = serviceWith(runner)

    with pytest.raises(UploadError, match="was not declared"):
        service.upload(sketchDir)


def testATimeoutIsReportedNotSwallowed(sketchDir: Path) -> None:
    def slowRunner(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 300)

    service = serviceWith(slowRunner)

    with pytest.raises(UploadError, match="timed out"):
        service.upload(sketchDir)
