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
            raise UploadError(
                self.explainFailure(cli, command, result.stdout, result.stderr)
            )
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

    def explainFailure(
        self, cli: str, command: list[str], stdout: str, stderr: str
    ) -> str:
        """Keep the part of the output that names the problem, and say who said it.

        "Platform not installed" means the core is missing from the data
        directory *this* arduino-cli is using, which is a narrower claim than
        it sounds. That directory is derived from the environment, so a process
        launched with a different one reads an empty folder and reports a core
        that is in fact installed - and the message's own suggestion, to
        install it, quietly creates a second copy rather than fixing the
        mismatch. Naming the binary and the directory turns that into a quick
        comparison instead of a long hunt.
        """
        output = (stderr or stdout or "").strip()
        lines = [line for line in output.splitlines() if line.strip()]
        # The last few lines carry the error; the rest is progress chatter.
        tail = "\n".join(lines[-6:]) if lines else "no output"
        message = (
            f"arduino-cli failed:\n{tail}\n\n"
            f"Command: {subprocess.list2cmdline(command)}\n"
            f"Using: {cli}\n"
            f"Data directory: {self.dataDirectory(cli)}"
        )
        if "platform not installed" in output.lower():
            # What this process can see, rather than advice about what to try:
            # if the core is listed here the installation is not the problem,
            # and installing again would only add a second copy.
            message += f"\n\nCores visible to this process:\n{self.installedCores(cli)}"
        return message

    def installedCores(self, cli: str) -> str:
        """What 'core list' reports for this process. Never raises."""
        return self.probe(cli, ["core", "list"])

    def dataDirectory(self, cli: str) -> str:
        """Where this arduino-cli keeps its cores, or why we cannot say."""
        return self.probe(cli, ["config", "get", "directories.data"])

    def probe(self, cli: str, args: list[str]) -> str:
        """Ask arduino-cli something small, for a failure report.

        Never raises. These run while a failure is already being reported, and
        losing the real error to a secondary one would be a poor trade.
        """
        try:
            result = self.runner(
                [cli, *args],
                capture_output=True,
                text=True,
                timeout=appConfig.configQueryTimeoutSeconds,
            )
        except Exception:  # noqa: BLE001 - diagnostics must not mask the real failure
            logger.debug("Could not run arduino-cli %s", " ".join(args), exc_info=True)
            return "could not be determined"
        if result.returncode != 0 or not (result.stdout or "").strip():
            return "could not be determined"
        return result.stdout.strip()

    def summarise(self, stdout: str, port: str) -> str:
        for line in stdout.splitlines():
            if line.startswith("Sketch uses"):
                return f"Uploaded to {port}. {line.strip()}"
        return f"Uploaded to {port}."
