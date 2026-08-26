r"""Tests for creating and seeding the writable side of an installed copy."""

from __future__ import annotations

from pathlib import Path

from rvBackupHelper import appConfig
from rvBackupHelper.services.userDataService import ensureUserData


def asInstalled(monkeypatch, tmp_path: Path) -> tuple[Path, Path]:
    """Two separate roots, the way a frozen build has them.

    programRoot carries what shipped; userDataDir is empty and writable.
    """
    programRoot = tmp_path / "program"
    userDataDir = tmp_path / "userData"
    bundledArduino = programRoot / "arduino"
    for name in appConfig.requiredLibraries:
        (bundledArduino / "libraries" / name).mkdir(parents=True)
        (bundledArduino / "libraries" / name / f"{name}.h").write_text("// shipped")
    bringUp = bundledArduino / appConfig.bringUpSketchName
    bringUp.mkdir(parents=True)
    (bringUp / f"{appConfig.bringUpSketchName}.ino").write_text("void setup(){}")
    # A generated sketch in the installed copy, which must NOT be seeded.
    generated = bundledArduino / appConfig.sketchName
    generated.mkdir(parents=True)
    (generated / f"{appConfig.sketchName}.ino").write_text("// somebody else's")

    monkeypatch.setattr(appConfig, "programRoot", programRoot)
    monkeypatch.setattr(appConfig, "userDataDir", userDataDir)
    monkeypatch.setattr(appConfig, "bundledArduinoDir", bundledArduino)
    monkeypatch.setattr(appConfig, "arduinoDir", userDataDir / "arduino")
    monkeypatch.setattr(appConfig, "arduinoUserDir", userDataDir / "arduino")
    monkeypatch.setattr(
        appConfig, "arduinoLibrariesDir", userDataDir / "arduino" / "libraries"
    )
    monkeypatch.setattr(appConfig, "logsDir", userDataDir / "logs")
    monkeypatch.setattr(appConfig, "recordingsDir", userDataDir / "recordings")
    monkeypatch.setattr(appConfig, "calibrationDir", userDataDir / "calibration")
    return programRoot, userDataDir


def testACheckoutKeepsBothRootsTheSame() -> None:
    """The running-from-source case, which must behave as it always has."""
    assert appConfig.programRoot == appConfig.projectRoot
    assert appConfig.userDataDir == appConfig.projectRoot
    assert not appConfig.frozen


def testTheWritableFoldersAreCreated(monkeypatch, tmp_path: Path) -> None:
    _, userDataDir = asInstalled(monkeypatch, tmp_path)

    ensureUserData()

    for name in ("logs", "recordings", "calibration", "arduino"):
        assert (userDataDir / name).is_dir()


def testTheLibrariesAreSeededSoUploadCanCompile(monkeypatch, tmp_path: Path) -> None:
    """Without these the build fails, and the message reads as a bad install."""
    _, userDataDir = asInstalled(monkeypatch, tmp_path)

    ensureUserData()

    for name in appConfig.requiredLibraries:
        assert (userDataDir / "arduino" / "libraries" / name / f"{name}.h").exists()


def testTheBringUpSketchIsSeeded(monkeypatch, tmp_path: Path) -> None:
    """Check Toolchain compiles it when no grid has been generated yet."""
    _, userDataDir = asInstalled(monkeypatch, tmp_path)

    ensureUserData()

    sketch = appConfig.bringUpSketchName
    assert (userDataDir / "arduino" / sketch / f"{sketch}.ino").exists()


def testAGeneratedSketchIsNotSeeded(monkeypatch, tmp_path: Path) -> None:
    """It is the user's own output; somebody else's calibration is not a start."""
    _, userDataDir = asInstalled(monkeypatch, tmp_path)

    ensureUserData()

    assert not (userDataDir / "arduino" / appConfig.sketchName).exists()


def testSeedingDoesNotOverwriteWhatIsAlreadyThere(monkeypatch, tmp_path: Path) -> None:
    """Run every startup, so it must never undo an edit or a newer library."""
    _, userDataDir = asInstalled(monkeypatch, tmp_path)
    ensureUserData()
    edited = userDataDir / "arduino" / "libraries" / "TVout" / "TVout.h"
    edited.write_text("// mine now", encoding="utf-8")

    created = ensureUserData()

    assert edited.read_text(encoding="utf-8") == "// mine now"
    assert created == [], "a second run has nothing left to do"


def testACheckoutSeedsNothing(monkeypatch, tmp_path: Path) -> None:
    """Both roots are one folder there; copying it onto itself is not a plan."""
    monkeypatch.setattr(appConfig, "programRoot", tmp_path)
    monkeypatch.setattr(appConfig, "userDataDir", tmp_path)
    monkeypatch.setattr(appConfig, "bundledArduinoDir", tmp_path / "arduino")
    monkeypatch.setattr(appConfig, "arduinoDir", tmp_path / "arduino")
    monkeypatch.setattr(appConfig, "logsDir", tmp_path / "logs")
    monkeypatch.setattr(appConfig, "recordingsDir", tmp_path / "recordings")
    monkeypatch.setattr(appConfig, "calibrationDir", tmp_path / "calibration")

    created = ensureUserData()

    assert (tmp_path / "arduino").is_dir()
    assert not (tmp_path / "arduino" / "libraries").exists()
    assert all(path.name in {"logs", "recordings", "calibration", "arduino"} for path in created)


def testAnUnwritableLocationIsLoggedRatherThanRaised(
    monkeypatch, tmp_path: Path
) -> None:
    """The app still opens clips; the parts that need a folder say so themselves."""
    asInstalled(monkeypatch, tmp_path)
    blocked = tmp_path / "blocked"
    blocked.write_text("this is a file, not a folder", encoding="utf-8")
    monkeypatch.setattr(appConfig, "logsDir", blocked / "logs")

    created = ensureUserData()

    assert blocked / "logs" not in created
