r"""Putting the writable side of the application where it can be written.

An installed copy lives somewhere it may not write - Program Files - while the
application writes constantly: logs, recordings, calibrations, and the sketches
it generates. So appConfig keeps two roots, and this creates the writable one
and seeds into it the few files that have to be there before anything works.

Seeding is only meaningful for an installed build. Run from a checkout the two
roots are the same folder and there is nothing to copy, which is deliberate:
a clone behaves exactly as it always has.

What gets seeded is what arduino-cli must be able to read *and* write beside:
the TVout-VE libraries, and the bring-up sketch that Check Toolchain compiles
when no grid has been generated yet. The generated sketch itself is not seeded
- it is the user's own output, and a stale copy of somebody else's calibration
would be worse than an empty folder.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from rvBackupHelper import appConfig

logger = logging.getLogger(__name__)


def userFolders() -> tuple[Path, ...]:
    """Everything the application writes into."""
    return (
        appConfig.logsDir,
        appConfig.recordingsDir,
        appConfig.calibrationDir,
        appConfig.arduinoDir,
    )


def seedSources() -> tuple[Path, ...]:
    """The folders copied out of the installed copy on first run."""
    return (
        appConfig.bundledArduinoDir / "libraries",
        appConfig.bundledArduinoDir / appConfig.bringUpSketchName,
    )


def ensureUserData() -> list[Path]:
    """Create the writable folders and seed what is missing. Never raises.

    Returns what it created, for the log. A failure here is reported and
    stepped over rather than thrown: the application can still open a clip and
    the parts that need these folders say so clearly by themselves - upload
    already explains a missing library far better than a traceback would.
    """
    created: list[Path] = []
    for folder in userFolders():
        try:
            if not folder.exists():
                folder.mkdir(parents=True, exist_ok=True)
                created.append(folder)
        except OSError as exc:
            logger.warning("Could not create %s: %s", folder, exc)

    if appConfig.programRoot == appConfig.userDataDir:
        # A checkout. The files are already where they belong, and copying a
        # folder onto itself would be an odd way to find that out.
        return created

    for source in seedSources():
        destination = appConfig.arduinoDir / source.name
        if destination.exists() or not source.is_dir():
            continue
        try:
            shutil.copytree(source, destination)
            created.append(destination)
            logger.info("Seeded %s from %s", destination, source)
        except OSError as exc:
            logger.warning("Could not seed %s: %s", destination, exc)
    return created
