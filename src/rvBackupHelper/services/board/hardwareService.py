r"""Is the hardware plugged in, and is it the right hardware?

The work is done by tools/checkHardware.ps1 rather than here, and on purpose.
An installer has to ask this question before Python exists on the machine, so
the rules live in something Windows can run on its own - and the application
running that same script is what stops "will this work here?" having two
answers that drift apart.

It answers about presence, never about fitness. The shield is passive and
enumerates nothing, and whether the camera is composite or AHD is invisible
from the USB bus.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass

from rvBackupHelper import appConfig

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HardwareReport:
    """What was found, in one line and in full."""

    ok: bool
    headline: str
    details: str

    @property
    def text(self) -> str:
        return f"{self.headline}\n\n{self.details}"


class HardwareService:
    """Runs the hardware check and turns its answer into something readable."""

    def __init__(self, runner=subprocess.run) -> None:
        self.runner = runner

    def check(self) -> HardwareReport:
        script = appConfig.hardwareCheckScript
        if not script.exists():
            return HardwareReport(
                ok=False,
                headline="The hardware check script is missing.",
                details=(
                    f"Expected at {script}.\n\n"
                    "It is committed to the repository, so this checkout is "
                    "incomplete rather than this machine being unprepared."
                ),
            )
        try:
            result = self.runner(
                [
                    appConfig.powerShellExecutable,
                    "-NoProfile",
                    "-ExecutionPolicy", "Bypass",
                    "-File", str(script),
                    "-Json",
                ],
                capture_output=True,
                text=True,
                timeout=appConfig.hardwareCheckTimeoutSeconds,
            )
        except Exception as exc:  # noqa: BLE001 - the report is the product
            logger.warning("Could not run the hardware check", exc_info=True)
            return HardwareReport(
                ok=False,
                headline="The hardware check could not be run.",
                details=f"{exc}\n\nIt needs Windows PowerShell, which ships with Windows.",
            )
        return self.interpret(result.stdout, result.stderr)

    def interpret(self, stdout: str, stderr: str) -> HardwareReport:
        """Turn the script's JSON into a headline and a body.

        A shape that cannot be parsed is reported with what was actually said,
        because a mangled answer here would otherwise look like a hardware
        fault rather than a broken check.
        """
        try:
            found = json.loads(stdout)
            board = found["board"]
            capture = found["capture"]
        except (ValueError, KeyError, TypeError) as exc:
            logger.warning("Hardware check output could not be read: %s", exc)
            output = (stderr or stdout or "no output").strip()
            return HardwareReport(
                ok=False,
                headline="The hardware check gave an answer that could not be read.",
                details=f"It said:\n{output}",
            )

        details = "\n\n".join(
            [
                f"Arduino: {board['message']}",
                f"Capture: {capture['message']}",
                f"Note: {found['shieldNote']}",
            ]
        )
        if found.get("ok"):
            return HardwareReport(
                ok=True,
                headline=f"Ready. {board['message']}",
                details=details,
            )
        return HardwareReport(
            ok=False,
            headline=self.problemHeadline(board, capture),
            details=(
                f"{details}\n\n"
                "Calibrating and generating a sketch need none of this - only "
                "capturing footage and uploading do."
            ),
        )

    def problemHeadline(self, board: dict, capture: dict) -> str:
        """Name the blocking problem, board first: it is the harder one to fix."""
        if board.get("verdict") == "wrongBoard":
            return f"Wrong board: {board['model']} will not run this sketch."
        if not board.get("found"):
            return "No Arduino found."
        if not capture.get("found"):
            return "No video capture device found."
        return "The hardware is not ready."
