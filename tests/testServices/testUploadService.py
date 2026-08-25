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


coreListing = "ID          Installed Latest Name\narduino:avr 1.8.8     1.8.8  Arduino AVR Boards"


class FailingBuildRunner:
    """Fails the build, but answers the diagnostic probes normally.

    Three commands with three different outcomes, which a single canned reply
    cannot express.
    """

    def __init__(self, stderr: str, dataDir: str = r"C:\Users\Someone\Arduino15") -> None:
        self.stderr = stderr
        self.dataDir = dataDir

    def __call__(self, command, **kwargs):
        if "config" in command:
            return subprocess.CompletedProcess(command, 0, self.dataDir + "\n", "")
        if "core" in command:
            return subprocess.CompletedProcess(command, 0, coreListing + "\n", "")
        return subprocess.CompletedProcess(command, 1, "", self.stderr)


def testAFailureNamesTheCliAndDataDirectoryThatProducedIt(sketchDir: Path) -> None:
    runner = FailingBuildRunner("error: 'foo' was not declared")

    service = UploadService(
        cliFinder=lambda: r"C:\Tools\arduino-cli.exe",
        portFinder=lambda: "COM3",
        runner=runner,
    )

    with pytest.raises(UploadError) as caught:
        service.upload(sketchDir)

    message = str(caught.value)
    # The real error still leads; the toolchain detail supports it.
    assert "was not declared" in message
    assert r"C:\Tools\arduino-cli.exe" in message
    assert r"C:\Users\Someone\Arduino15" in message


def testAMissingPlatformReportsWhatThisProcessCanActuallySee(sketchDir: Path) -> None:
    # arduino-cli's advice here is to install the core. When the core is in fact
    # installed that is the wrong move, so show what this process sees instead
    # of repeating guidance that may send the reader the wrong way.
    runner = FailingBuildRunner(
        "Error during build: Platform 'arduino:avr' not found: platform not installed"
    )
    service = serviceWith(runner)

    with pytest.raises(UploadError) as caught:
        service.upload(sketchDir)

    message = str(caught.value)
    assert "Cores visible to this process:" in message
    assert "arduino:avr 1.8.8" in message


def testTheOnDiskCheckListsCoresArduinoCliDidNotSee(tmp_path: Path) -> None:
    # The discriminator: folders present here but no cores reported by
    # arduino-cli means the fault is in how it was invoked, not the install.
    core = tmp_path / "packages" / "arduino" / "hardware" / "avr" / "1.8.8"
    core.mkdir(parents=True)

    found = UploadService().coresOnDisk(str(tmp_path))

    assert "arduino" in found
    assert "1.8.8" in found


def testTheOnDiskCheckSaysWhenThereIsNothingThere(tmp_path: Path) -> None:
    reported = UploadService().coresOnDisk(str(tmp_path / "absent"))

    assert "does not exist" in reported


def testTheFailureQuotesTheExactCommandItRan(sketchDir: Path) -> None:
    runner = FailingBuildRunner("error: 'foo' was not declared")
    service = serviceWith(runner)

    with pytest.raises(UploadError) as caught:
        service.upload(sketchDir)

    message = str(caught.value)
    # Everything needed to run it by hand: board, port and the sketch folder.
    assert "Command:" in message
    assert appConfig.boardFqbn in message
    assert "COM3" in message
    assert str(sketchDir) in message


def testTheDataDirectoryQueryNeverMasksTheRealFailure(sketchDir: Path) -> None:
    def runner(command, **kwargs):
        if "config" in command:
            raise OSError("cannot run")
        return subprocess.CompletedProcess(command, 1, "", "error: 'foo' was not declared")

    with pytest.raises(UploadError) as caught:
        serviceWith(runner).upload(sketchDir)

    message = str(caught.value)
    assert "was not declared" in message
    assert "could not be determined" in message
