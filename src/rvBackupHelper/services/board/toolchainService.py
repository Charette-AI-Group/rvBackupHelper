r"""Answering "is this machine able to flash the board?" before it matters.

The evidence that settles it is a compile, not a directory listing. A missing
AVR core cost a working day on the laptop because every check short of building
something agreed it was installed, so this runs the compiler and reports what
the compiler used - binary, data directory, sketchbook, cores.

It installs nothing. Fetching a 295 MB core is not something a menu item should
start on its own; tools/setupToolchain.py does that, and this names it.
"""

from __future__ import annotations

import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

from rvBackupHelper import appConfig
from rvBackupHelper.services.board.uploadService import (
    findArduinoCli,
    toolchainEnvironment,
)

logger = logging.getLogger(__name__)

setupCommand = r".venv\Scripts\python.exe tools\setupToolchain.py"


@dataclass(frozen=True)
class ToolchainReport:
    """What was found, in one line and in full."""

    ok: bool
    headline: str
    details: str

    @property
    def text(self) -> str:
        return f"{self.headline}\n\n{self.details}"


class ToolchainService:
    """Checks the toolchain by using it."""

    def __init__(
        self,
        cliFinder=findArduinoCli,
        environmentFactory=toolchainEnvironment,
        runner=subprocess.run,
    ) -> None:
        self.cliFinder = cliFinder
        self.environmentFactory = environmentFactory
        self.runner = runner

    def check(self) -> ToolchainReport:
        missing = self.missingLibraries()
        if missing:
            return ToolchainReport(
                ok=False,
                headline=f"{', '.join(missing)} missing from the repository.",
                details=(
                    f"Expected in {appConfig.arduinoLibrariesDir}.\n\n"
                    "These are committed, so this checkout is incomplete rather "
                    "than this machine being unprepared. Run 'git status' in the "
                    "repository, or clone it again. Do not install them by hand."
                ),
            )

        cli = self.cliFinder()
        if cli is None:
            return ToolchainReport(
                ok=False,
                headline="arduino-cli was not found.",
                details=(
                    "Nothing can be compiled or flashed without it.\n\n"
                    f"Install it and the AVR core with:\n    {setupCommand}\n\n"
                    "or by hand:\n"
                    "    winget install --id ArduinoSA.CLI --exact\n"
                    f"    arduino-cli core install {self.coreName()}"
                ),
            )

        sketchDir = self.sketchToCompile()
        if sketchDir is None:
            return ToolchainReport(
                ok=False,
                headline="No sketch to compile, so nothing could be proved.",
                details=(
                    f"Looked in {appConfig.arduinoDir} for "
                    f"{appConfig.sketchName} and {appConfig.bringUpSketchName}.\n\n"
                    "Generate a sketch from the Calibrate tab and check again."
                ),
            )

        compiled = self.compile(cli, sketchDir)
        details = self.describe(cli, sketchDir, compiled)
        if compiled.returncode == 0:
            return ToolchainReport(
                ok=True,
                headline=f"Ready. {self.sizeLine(compiled.stdout) or 'The sketch compiled.'}",
                details=details,
            )
        return ToolchainReport(
            ok=False,
            headline="The toolchain is not ready: the sketch did not compile.",
            details=details,
        )

    def missingLibraries(self) -> list[str]:
        return [
            name
            for name in appConfig.requiredLibraries
            if not (appConfig.arduinoLibrariesDir / name).is_dir()
        ]

    def coreName(self) -> str:
        """'arduino:avr' from 'arduino:avr:uno'."""
        return appConfig.boardFqbn.rsplit(":", 1)[0]

    def sketchToCompile(self) -> Path | None:
        """The generated sketch if there is one, else the bring-up sketch.

        The generated one is the real artefact, but it only exists once a
        calibration has been made - and a machine wants checking before that,
        not after. The bring-up sketch is committed and pulls in the same core
        and the same libraries, so it proves the same things.
        """
        for name in (appConfig.sketchName, appConfig.bringUpSketchName):
            folder = appConfig.arduinoDir / name
            if (folder / f"{name}{appConfig.sketchExtension}").exists():
                return folder
        return None

    def compile(self, cli: str, sketchDir: Path) -> subprocess.CompletedProcess:
        command = [cli, "compile", "--fqbn", appConfig.boardFqbn, str(sketchDir)]
        logger.info("Checking the toolchain by compiling %s", sketchDir)
        return self.run(command, appConfig.uploadTimeoutSeconds)

    def run(self, command: list[str], timeout: float) -> subprocess.CompletedProcess:
        """Run a command, returning a failed result rather than raising.

        This runs to produce a report; an exception here would replace the
        report with a traceback and tell the reader less than the failure does.
        """
        try:
            return self.runner(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                env=self.environmentFactory(),
            )
        except Exception as exc:  # noqa: BLE001 - the report is the product
            logger.warning("Could not run %s", command[0], exc_info=True)
            return subprocess.CompletedProcess(command, 1, "", str(exc))

    def probe(self, cli: str, arguments: list[str]) -> str:
        result = self.run([cli, *arguments], appConfig.configQueryTimeoutSeconds)
        if result.returncode != 0 or not (result.stdout or "").strip():
            return "could not be determined"
        return result.stdout.strip()

    def sizeLine(self, output: str) -> str:
        for line in output.splitlines():
            if line.startswith("Sketch uses"):
                return line.strip()
        return ""

    def describe(
        self, cli: str, sketchDir: Path, compiled: subprocess.CompletedProcess
    ) -> str:
        """Where every piece came from, so a wrong answer can be seen to be wrong."""
        cores = self.probe(cli, ["core", "list"])
        lines = [
            f"Compiled     : {sketchDir}",
            f"arduino-cli  : {cli}",
            f"version      : {self.probe(cli, ['version'])}",
            f"data dir     : {self.probe(cli, ['config', 'get', 'directories.data'])}",
            f"sketchbook   : {self.environmentFactory()['ARDUINO_DIRECTORIES_USER']}",
            f"libraries    : {appConfig.arduinoLibrariesDir}",
            "cores        : " + cores.replace("\n", "\n" + " " * 15),
        ]
        if compiled.returncode != 0:
            output = (compiled.stderr or compiled.stdout or "no output").strip()
            tail = "\n".join(output.splitlines()[-6:])
            lines.append("")
            lines.append(f"The compiler said:\n{tail}")
            if "platform not installed" in output.lower():
                lines.append("")
                lines.append(
                    f"The {self.coreName()} core is missing from the directory above. "
                    f"Install it with:\n    {setupCommand}"
                )
        return "\n".join(lines)
