r"""Build the standalone application, and check that what shipped is right.

PyInstaller succeeds cheerfully while leaving out a data file, and the symptom
turns up later as a missing manual or a compile that cannot find TVout.h - the
same class of failure that has already cost this project two sessions. So the
build is followed by an inventory of what actually landed in the bundle, and
this exits non-zero if anything is absent.

    .venv\Scripts\python.exe tools\buildExe.py
    .venv\Scripts\python.exe tools\buildExe.py --smoke

--smoke additionally launches the built executable for a few seconds and
confirms it wrote a log, which is the cheapest proof that a windowed build
starts at all: it has no console to print to.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

projectRoot = Path(__file__).resolve().parents[1]
specFile = projectRoot / "rvBackupHelper.spec"
distDir = projectRoot / "dist" / "rvBackupHelper"
executable = distDir / "rvBackupHelper.exe"
buildTimeoutSeconds = 1800.0
smokeSeconds = 12.0

# Everything the read-only half of the application reaches for at runtime,
# relative to the bundle's _internal folder - which is what sys._MEIPASS
# points at in a one-folder build, and therefore what appConfig.programRoot
# becomes.
expectedPayload = [
    Path("docs/manual/README.md"),
    Path("tools/checkHardware.ps1"),
    Path("arduino/libraries/TVout/video_gen.cpp"),
    Path("arduino/libraries/TVoutfonts/fontALL.h"),
    Path("arduino/libraries/pollserial/pollserial.h"),
    Path("arduino/rvbhBringUp/rvbhBringUp.ino"),
]
# The user's own output. Shipping it would hand every install somebody else's
# calibration, which is worse than an empty folder.
refusedPayload = [
    Path("arduino/rvbhGrid"),
    Path("recordings"),
    Path("calibration"),
]


def folderSize(folder: Path) -> int:
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())


def humanSize(byteCount: int) -> str:
    return f"{byteCount / 1_000_000:.0f} MB"


def build() -> int:
    if distDir.exists():
        shutil.rmtree(distDir)
    command = [
        sys.executable, "-m", "PyInstaller",
        str(specFile),
        "--noconfirm",
        "--clean",
        "--distpath", str(projectRoot / "dist"),
        "--workpath", str(projectRoot / "build"),
    ]
    print(f"$ {subprocess.list2cmdline(command)}")
    result = subprocess.run(command, cwd=projectRoot, timeout=buildTimeoutSeconds)
    return result.returncode


def internalDir() -> Path:
    """Where a one-folder build puts its data. _MEIPASS, at runtime."""
    candidate = distDir / "_internal"
    return candidate if candidate.is_dir() else distDir


def checkPayload() -> list[str]:
    problems: list[str] = []
    internal = internalDir()
    for relative in expectedPayload:
        if not (internal / relative).exists():
            problems.append(f"missing from the bundle: {relative}")
    for relative in refusedPayload:
        if (internal / relative).exists():
            problems.append(f"should not have shipped: {relative}")
    return problems


def smokeTest() -> list[str]:
    """Start it, and see whether it left a log behind.

    A windowed build has no console, so there is nothing to read except what
    it writes. The log is the first thing main() sets up, so its appearance
    means the interpreter, PySide6 and the imports all came up.
    """
    appData = Path(os.environ.get("LOCALAPPDATA", Path.home()))
    logPath = appData / "RV Backup Helper" / "logs" / "rvBackupHelper.log"
    before = logPath.stat().st_mtime if logPath.exists() else 0.0

    print(f"$ {executable}")
    process = subprocess.Popen([str(executable)], cwd=distDir)
    try:
        deadline = time.monotonic() + smokeSeconds
        while time.monotonic() < deadline:
            if logPath.exists() and logPath.stat().st_mtime > before:
                break
            if process.poll() is not None:
                return [f"the application exited early, with code {process.returncode}"]
            time.sleep(0.25)
        else:
            return [f"no log appeared at {logPath} within {smokeSeconds:.0f} s"]
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()

    recent = logPath.read_text(encoding="utf-8", errors="replace").splitlines()[-12:]
    print("\nWhat it logged:")
    for line in recent:
        print(f"  {line}")
    return []


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="also launch the built executable and confirm it starts",
    )
    arguments = parser.parse_args()

    code = build()
    if code != 0:
        print(f"\nPyInstaller failed with code {code}.")
        return code
    if not executable.exists():
        print(f"\nBuild reported success but {executable} is not there.")
        return 1

    problems = checkPayload()
    if arguments.smoke and not problems:
        problems += smokeTest()

    print()
    print(f"Bundle    : {distDir}")
    print(f"Executable: {executable.name} ({humanSize(executable.stat().st_size)})")
    print(f"Total     : {humanSize(folderSize(distDir))}")
    if problems:
        print("\nNOT SHIPPABLE:")
        for problem in problems:
            print(f"  - {problem}")
        return 1
    print("\nPayload is complete and carries nothing that belongs to a user.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
