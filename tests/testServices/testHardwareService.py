r"""Tests for the hardware check behind Help > Check Hardware."""

from __future__ import annotations

import json
import subprocess

from rvBackupHelper import appConfig
from rvBackupHelper.services.board.hardwareService import HardwareService

shieldNote = "The Video Experimenter shield cannot be detected."


def answer(board: dict, capture: dict, ok: bool) -> str:
    return json.dumps(
        {"ok": ok, "board": board, "capture": capture, "shieldNote": shieldNote}
    )


unoFound = {
    "found": True,
    "usable": True,
    "verdict": "ok",
    "model": "Arduino Uno R3",
    "name": "Arduino Uno (COM3)",
    "port": "COM3",
    "id": "2341:0043",
    "message": "Arduino Uno R3 on COM3.",
}
noBoard = {
    "found": False,
    "usable": False,
    "verdict": "missing",
    "model": "",
    "name": "",
    "port": "",
    "id": "",
    "message": "No Arduino found. Plug the board in by USB.",
}
unoR4 = {
    "found": True,
    "usable": False,
    "verdict": "wrongBoard",
    "model": "Arduino Uno R4 Minima",
    "name": "Arduino Uno R4 (COM7)",
    "port": "COM7",
    "id": "2341:0069",
    "message": "Arduino Uno R4 Minima found on COM7. The grid sketch runs only on an Uno R3.",
}
grabberFound = {
    "found": True,
    "verdict": "ok",
    "devices": ["USB Video"],
    "message": "Capture device(s) present: USB Video.",
}
noGrabber = {
    "found": False,
    "verdict": "missing",
    "devices": [],
    "message": "No video capture device found. Plug the USB grabber in.",
}


class FakeRunner:
    def __init__(self, stdout: str = "", stderr: str = "", returncode: int = 0) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.returncode = returncode
        self.command: list[str] | None = None

    def __call__(self, command, **kwargs):
        self.command = command
        return subprocess.CompletedProcess(
            command, self.returncode, self.stdout, self.stderr
        )


def testHardwarePresentReadsAsReady() -> None:
    runner = FakeRunner(answer(unoFound, grabberFound, ok=True))

    report = HardwareService(runner).check()

    assert report.ok
    assert "Ready" in report.headline
    assert "COM3" in report.headline
    assert "USB Video" in report.details


def testTheScriptIsRunThroughWindowsPowerShell() -> None:
    """It has to work on a machine where nothing has been installed yet."""
    runner = FakeRunner(answer(unoFound, grabberFound, ok=True))

    HardwareService(runner).check()

    assert runner.command is not None
    assert runner.command[0] == appConfig.powerShellExecutable
    assert "-ExecutionPolicy" in runner.command
    assert str(appConfig.hardwareCheckScript) in runner.command
    assert "-Json" in runner.command


def testAMissingBoardIsNamedAsTheProblem() -> None:
    report = HardwareService(FakeRunner(answer(noBoard, grabberFound, False))).check()

    assert not report.ok
    assert report.headline == "No Arduino found."


def testAMissingGrabberIsNamedAsTheProblem() -> None:
    report = HardwareService(FakeRunner(answer(unoFound, noGrabber, False))).check()

    assert not report.ok
    assert report.headline == "No video capture device found."


def testTheWrongBoardIsNamedRatherThanCalledMissing() -> None:
    """"Wrong board" is a far more useful answer than "not found"."""
    report = HardwareService(FakeRunner(answer(unoR4, grabberFound, False))).check()

    assert not report.ok
    assert "Wrong board" in report.headline
    assert "Uno R4 Minima" in report.headline


def testTheBoardIsReportedBeforeTheGrabberWhenBothAreMissing() -> None:
    """A board is the harder of the two to put right, so it leads."""
    report = HardwareService(FakeRunner(answer(noBoard, noGrabber, False))).check()

    assert report.headline == "No Arduino found."


def testTheUndetectableShieldIsSaidEveryTime() -> None:
    """Nothing can see it, so nobody should read presence as proof of it."""
    report = HardwareService(FakeRunner(answer(unoFound, grabberFound, True))).check()

    assert shieldNote in report.details


def testAFailureSaysWhatStillWorksWithoutHardware() -> None:
    """Calibrating and generating a sketch need none of it."""
    report = HardwareService(FakeRunner(answer(noBoard, noGrabber, False))).check()

    assert "Calibrating and generating" in report.details


def testUnreadableOutputIsReportedAsSuchNotAsAHardwareFault() -> None:
    runner = FakeRunner(stdout="not json at all", stderr="")

    report = HardwareService(runner).check()

    assert not report.ok
    assert "could not be read" in report.headline
    assert "not json at all" in report.details


def testARunnerThatExplodesStillProducesAReport() -> None:
    def explode(*args, **kwargs):
        raise OSError("powershell is missing")

    report = HardwareService(explode).check()

    assert not report.ok
    assert "could not be run" in report.headline
    assert "powershell is missing" in report.details


def testAMissingScriptIsACheckoutProblem(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(appConfig, "hardwareCheckScript", tmp_path / "gone.ps1")
    runner = FakeRunner()

    report = HardwareService(runner).check()

    assert not report.ok
    assert "checkout is incomplete" in report.details
    assert runner.command is None, "nothing should be run when the script is absent"


def testTheRealScriptShipsWithTheRepository() -> None:
    assert appConfig.hardwareCheckScript.exists()
