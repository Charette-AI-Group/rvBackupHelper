"""Compiling and uploading a sketch to the Arduino, without the IDE.

Shells out to arduino-cli, which does exactly what the IDE's upload button
does. The IDE is only needed if you want to edit the sketch by hand.
"""

from __future__ import annotations

import logging
import os
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


def toolchainEnvironment() -> dict[str, str]:
    r"""The environment arduino-cli is run with.

    ARDUINO_DIRECTORIES_USER makes the repo's arduino/ folder the sketchbook,
    so the libraries committed in arduino/libraries are the ones compiled
    against and whatever sits in Documents\Arduino\libraries is bypassed
    entirely - including a stock TVout, which builds this sketch and then
    leaves the board resetting on every sync pulse.

    The cores are left where the machine already keeps them. They are a 295 MB
    download, so a repo-local copy would have to be fetched again per checkout;
    tools/setupToolchain.py installs and verifies those instead.
    """
    environment = dict(os.environ)
    environment["ARDUINO_DIRECTORIES_USER"] = str(appConfig.arduinoUserDir)
    return environment


class UploadService:
    """Runs arduino-cli compile --upload against a sketch folder."""

    def __init__(
        self,
        cliFinder=findArduinoCli,
        portFinder=findBoardPort,
        runner=subprocess.run,
        environmentFactory=toolchainEnvironment,
    ) -> None:
        self.cliFinder = cliFinder
        self.portFinder = portFinder
        self.runner = runner
        self.environmentFactory = environmentFactory

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
        self.checkLibraries()
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
                env=self.environmentFactory(),
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

    def checkLibraries(self) -> None:
        """Fail before compiling if the vendored libraries are not there.

        They are committed, so a checkout has them. A zip download of a single
        folder, or a stray delete, does not - and the compiler's report of that
        is "TVout.h: No such file or directory", which reads as a machine that
        needs libraries installed. It does not; it needs the rest of the repo.
        """
        missing = [
            name
            for name in appConfig.requiredLibraries
            if not (appConfig.arduinoLibrariesDir / name).is_dir()
        ]
        if missing:
            raise UploadError(
                f"{', '.join(missing)} missing from {appConfig.arduinoLibrariesDir}. "
                "These ship with the repository, so this checkout is incomplete - "
                "'git status' there, or clone again. Installing anything is not the fix."
            )

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
            dataDir = self.dataDirectory(cli)
            message += (
                f"\n\nCores visible to this process:\n{self.installedCores(cli)}"
                f"\n\nOn disk, as this process sees it:\n{self.coresOnDisk(dataDir)}"
                f"\n\nLOCALAPPDATA: {os.environ.get('LOCALAPPDATA', 'not set')}"
                f"\n{self.arduinoEnvironment()}"
            )
        return message

    def installedCores(self, cli: str) -> str:
        """What 'core list' reports for this process. Never raises."""
        return self.probe(cli, ["core", "list"])

    def coresOnDisk(self, dataDir: str) -> str:
        """Look for the cores directly, bypassing arduino-cli.

        Separates the two ways this can go wrong. If the folders are here but
        arduino-cli reports none, the fault is in how it was invoked; if they
        are not here either, this process is reading a different filesystem
        view than the one the cores were installed into.
        """
        packages = Path(dataDir) / "packages"
        try:
            if not packages.is_dir():
                return f"{packages} does not exist"
            found = sorted(
                str(path.relative_to(packages))
                for path in packages.glob("*/hardware/*/*")
                if path.is_dir()
            )
            if found:
                return "\n".join(found)
        except OSError as exc:
            return f"{packages} could not be read: {exc}"
        # Nothing matched. That is either an empty tree or one this process
        # cannot walk, and those call for quite different remedies, so descend
        # by hand and say where it stops rather than reporting a bare absence.
        return f"No cores matched under {packages}.\n" + self.describeTree(packages)

    def describeTree(self, root: Path, depth: int = 4) -> str:
        """List what can actually be seen, level by level, errors included."""
        lines: list[str] = []
        level = [root]
        for _ in range(depth):
            children: list[Path] = []
            for directory in level:
                try:
                    entries = sorted(directory.iterdir())
                except OSError as exc:
                    lines.append(f"  {directory}: cannot be listed: {exc}")
                    continue
                if not entries:
                    lines.append(f"  {directory}: empty")
                for entry in entries:
                    try:
                        kind = "dir" if entry.is_dir() else "file"
                    except OSError as exc:
                        kind = f"cannot be inspected: {exc}"
                    lines.append(f"  {entry}: {kind}")
                    if kind == "dir":
                        children.append(entry)
            if not children:
                break
            level = children
        return "\n".join(lines) if lines else "  nothing at all"

    def arduinoEnvironment(self) -> str:
        """Any ARDUINO_* variables, which override where cores are looked for."""
        found = {
            name: value
            for name, value in os.environ.items()
            if name.upper().startswith("ARDUINO")
        }
        if not found:
            return "No ARDUINO_* environment variables are set."
        return "\n".join(f"{name}={value}" for name, value in sorted(found.items()))

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
                env=self.environmentFactory(),
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
