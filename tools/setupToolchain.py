r"""Install and verify everything the Upload button needs, and say what it found.

The libraries ship with the repo, so what this has to deal with is the half
that cannot: arduino-cli and the 295 MB AVR core. Neither is hard to install.
What is hard is being *sure* they are installed, which is what cost a working
day on the laptop - a missing core reported by a message nobody believed,
because checks run from elsewhere kept insisting it was there.

So this ends by compiling the real sketch and printing where every piece came
from. A green verdict here is evidence about this machine, not about a
directory somebody looked at once.

    .venv\Scripts\python.exe tools\setupToolchain.py
    .venv\Scripts\python.exe tools\setupToolchain.py --check
    .venv\Scripts\python.exe tools\setupToolchain.py --data-dir arduino\.toolchain

Exit status is 0 only when a sketch actually compiled.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

projectRoot = Path(__file__).resolve().parents[1]

try:
    from rvBackupHelper import appConfig

    arduinoUserDir = appConfig.arduinoUserDir
    librariesDir = appConfig.arduinoLibrariesDir
    requiredLibraries = appConfig.requiredLibraries
    installedCliPath = Path(appConfig.arduinoCliPath)
    boardFqbn = appConfig.boardFqbn
    sketchName = appConfig.sketchName
except ImportError:
    # Deliberately survivable: on a fresh clone the venv may not exist yet, and
    # a setup tool that cannot run before setup is not much of a setup tool.
    arduinoUserDir = projectRoot / "arduino"
    librariesDir = arduinoUserDir / "libraries"
    requiredLibraries = ("TVout", "TVoutfonts", "pollserial")
    installedCliPath = Path(r"C:\Program Files\Arduino CLI\arduino-cli.exe")
    boardFqbn = "arduino:avr:uno"
    sketchName = "rvbhGrid"

core = boardFqbn.rsplit(":", 1)[0]
wingetPackage = "ArduinoSA.CLI"
# A cold core install pulls the whole avr-gcc toolchain over the wire.
installTimeoutSeconds = 1800.0
compileTimeoutSeconds = 600.0
queryTimeoutSeconds = 60.0


def run(command: list[str], environment: dict[str, str], timeout: float):
    """Run a command, streaming nothing, returning what it said."""
    print(f"  $ {subprocess.list2cmdline(command)}")
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=environment,
    )


def environmentFor(dataDir: Path | None) -> dict[str, str]:
    """The environment every step here shares.

    One environment for the install, the query and the compile, so that a pass
    cannot be about a different directory than the one that was installed into.
    """
    environment = dict(os.environ)
    environment["ARDUINO_DIRECTORIES_USER"] = str(arduinoUserDir)
    if dataDir is not None:
        environment["ARDUINO_DIRECTORIES_DATA"] = str(dataDir)
    return environment


def findCli() -> str | None:
    onPath = shutil.which("arduino-cli")
    if onPath:
        return onPath
    return str(installedCliPath) if installedCliPath.exists() else None


def installCli() -> str | None:
    if shutil.which("winget") is None:
        print("  winget is not available; install arduino-cli by hand and re-run.")
        return None
    run(
        [
            "winget", "install", "--id", wingetPackage, "--exact",
            "--accept-package-agreements", "--accept-source-agreements",
        ],
        dict(os.environ),
        installTimeoutSeconds,
    )
    # winget adds to PATH for new processes, not for this one.
    return findCli()


def coreInstalled(cli: str, environment: dict[str, str]) -> bool:
    result = run([cli, "core", "list"], environment, queryTimeoutSeconds)
    return core in result.stdout


def checkLibraries() -> list[str]:
    return [name for name in requiredLibraries if not (librariesDir / name).is_dir()]


def compileSketch(cli: str, environment: dict[str, str]) -> subprocess.CompletedProcess:
    sketchDir = arduinoUserDir / sketchName
    return run(
        [cli, "compile", "--fqbn", boardFqbn, str(sketchDir)],
        environment,
        compileTimeoutSeconds,
    )


def report(cli: str, environment: dict[str, str]) -> None:
    """Print where each piece actually came from, on this machine, right now."""
    version = run([cli, "version"], environment, queryTimeoutSeconds)
    dataDir = run(
        [cli, "config", "get", "directories.data"], environment, queryTimeoutSeconds
    )
    cores = run([cli, "core", "list"], environment, queryTimeoutSeconds)
    print()
    print("Toolchain in use")
    print(f"  arduino-cli   : {cli}")
    print(f"  version       : {version.stdout.strip() or 'unknown'}")
    print(f"  data directory: {dataDir.stdout.strip() or 'unknown'}")
    print(f"  sketchbook    : {environment['ARDUINO_DIRECTORIES_USER']}")
    print(f"  libraries     : {librariesDir}")
    print("  cores         : " + (cores.stdout.strip() or "none").replace("\n", "\n" + " " * 18))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--check",
        action="store_true",
        help="report what is installed and compile, but install nothing",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=None,
        help=(
            "keep the cores here instead of the machine-wide Arduino15 folder. "
            "Isolates this checkout completely, at the cost of a 295 MB download "
            "per checkout; set ARDUINO_DIRECTORIES_DATA to the same path when "
            "running arduino-cli by hand afterwards"
        ),
    )
    arguments = parser.parse_args()
    dataDir = arguments.data_dir.resolve() if arguments.data_dir else None
    environment = environmentFor(dataDir)

    print("Libraries")
    missing = checkLibraries()
    if missing:
        print(f"  MISSING from {librariesDir}: {', '.join(missing)}")
        print("  These are committed to the repository - this checkout is incomplete.")
        print("  Run 'git status' here, or clone again. Do not install them by hand.")
        return 1
    print(f"  ok: {', '.join(requiredLibraries)} in {librariesDir}")

    print("Arduino CLI")
    cli = findCli()
    if cli is None and not arguments.check:
        print("  not found; installing with winget")
        cli = installCli()
    if cli is None:
        print("  NOT FOUND. Install it with:")
        print(f"    winget install --id {wingetPackage} --exact")
        return 1
    print(f"  ok: {cli}")

    print(f"Core {core}")
    if not coreInstalled(cli, environment):
        if arguments.check:
            print("  NOT INSTALLED. Run this tool without --check, or:")
            print(f"    arduino-cli core install {core}")
            return 1
        print("  not installed; fetching it now (about 295 MB, several minutes)")
        result = run([cli, "core", "install", core], environment, installTimeoutSeconds)
        if result.returncode != 0:
            print(f"  install failed:\n{result.stderr.strip() or result.stdout.strip()}")
            return 1
        if not coreInstalled(cli, environment):
            # Installing into one directory and reading another is exactly the
            # failure this tool exists to make visible, so say so plainly.
            print("  installed, but still not listed. The install and the check are")
            print("  reading different directories; compare the report below.")
            report(cli, environment)
            return 1
    print(f"  ok: {core} present")

    print(f"Compiling arduino/{sketchName}, which is the part that actually proves it")
    result = compileSketch(cli, environment)
    if result.returncode != 0:
        tail = (result.stderr or result.stdout or "").strip().splitlines()[-6:]
        print("  FAILED:")
        print("\n".join(f"    {line}" for line in tail))
        report(cli, environment)
        return 1
    for line in result.stdout.splitlines():
        if line.startswith("Sketch uses"):
            print(f"  ok: {line.strip()}")

    report(cli, environment)
    print()
    print("Ready. Upload to Arduino will work from the app.")
    if dataDir is not None:
        print(f"Cores are in {dataDir}; set ARDUINO_DIRECTORIES_DATA to it for")
        print("arduino-cli runs outside the app, or they will not be found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
