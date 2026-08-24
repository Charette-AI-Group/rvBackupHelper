"""Compiling and uploading a sketch to the Arduino, without the IDE.

Shells out to arduino-cli, which does exactly what the IDE's upload button
does. The IDE is only needed if you want to edit the sketch by hand.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from rvBackupHelper import appConfig
from rvBackupHelper.services.board.gridService import findBoardPort

logger = logging.getLogger(__name__)


class UploadError(RuntimeError):
    """The sketch could not be compiled or uploaded."""


def findArduinoCli() -> str | None:
    onPath = shutil.which("arduino-cli")
    if onPath:
        return onPath
    installed = Path(appConfig.arduinoCliPath)
    return str(installed) if installed.exists() else None


class UploadService:
    """Runs arduino-cli compile --upload against a sketch folder."""

    def __init__(
        self,
        cliFinder=findArduinoCli,
        portFinder=findBoardPort,
        runner=subprocess.run,
    ) -> None:
        self.cliFinder = cliFinder
        self.portFinder = portFinder
        self.runner = runner

    def upload(self, sketchPath: Path) -> str:
        """Compile and flash the sketch. Returns the size summary on success."""
        cli = self.cliFinder()
        if cli is None:
            raise UploadError(
                "arduino-cli was not found. Install it with "
                "'winget install --id ArduinoSA.CLI --exact', or open the sketch "
                "in the Arduino IDE and upload from there."
            )
        port = self.portFinder()
        if port is None:
            raise UploadError(
                "No Arduino found. Check it is plugged in, and that nothing else "
                "is holding the port."
            )
        sketchDir = self.sketchDirectory(sketchPath)

        command = [
            cli, "compile",
            "--fqbn", appConfig.boardFqbn,
            "--upload",
            "--port", port,
            "--verify",
            str(sketchDir),
        ]
        logger.info("Uploading %s to %s", sketchDir, port)
        try:
            result = self.runner(
                command,
                capture_output=True,
                text=True,
                timeout=appConfig.uploadTimeoutSeconds,
            )
        except subprocess.TimeoutExpired as exc:
            raise UploadError(f"arduino-cli timed out after {exc.timeout:.0f} s.") from exc
        except OSError as exc:
            raise UploadError(f"Could not run arduino-cli: {exc}") from exc

        if result.returncode != 0:
            raise UploadError(self.explainFailure(result.stdout, result.stderr))
        return self.summarise(result.stdout, port)

    def sketchDirectory(self, sketchPath: Path) -> Path:
        """arduino-cli compiles a folder, not a file."""
        sketchDir = sketchPath.parent if sketchPath.suffix else sketchPath
        if not sketchDir.is_dir():
            raise UploadError(f"Sketch folder not found: {sketchDir}")
        if not (sketchDir / f"{sketchDir.name}{appConfig.sketchExtension}").exists():
            raise UploadError(
                f"{sketchDir.name} has no {sketchDir.name}{appConfig.sketchExtension} "
                "in it. The Arduino tools require the sketch file to carry the same "
                "name as its folder."
            )
        return sketchDir

    def explainFailure(self, stdout: str, stderr: str) -> str:
        """Keep the part of the output that names the problem."""
        output = (stderr or stdout or "").strip()
        lines = [line for line in output.splitlines() if line.strip()]
        # The last few lines carry the error; the rest is progress chatter.
        tail = "\n".join(lines[-6:]) if lines else "no output"
        return f"arduino-cli failed:\n{tail}"

    def summarise(self, stdout: str, port: str) -> str:
        for line in stdout.splitlines():
            if line.startswith("Sketch uses"):
                return f"Uploaded to {port}. {line.strip()}"
        return f"Uploaded to {port}."
