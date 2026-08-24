"""Tests for stored user preferences."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from rvBackupHelper import appConfig
from rvBackupHelper.services.settingsService import SettingsService


@pytest.fixture
def settingsFile(tmp_path: Path) -> QSettings:
    """File-backed settings, so tests never touch the real user preferences."""
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def testRecordingsDirDefaultsToTheBundledFolder(settingsFile: QSettings) -> None:
    service = SettingsService(settingsFile)

    assert service.recordingsDir() == appConfig.recordingsDir


def testRecordingsDirRoundTrips(settingsFile: QSettings, tmp_path: Path) -> None:
    service = SettingsService(settingsFile)
    chosen = tmp_path / "clips"

    service.setRecordingsDir(chosen)

    assert service.recordingsDir() == chosen


def testRecordingsDirSurvivesANewServiceInstance(
    settingsFile: QSettings, tmp_path: Path
) -> None:
    """The point of the setting is that it outlives the session."""
    chosen = tmp_path / "elsewhere"
    SettingsService(settingsFile).setRecordingsDir(chosen)

    reopened = QSettings(settingsFile.fileName(), QSettings.Format.IniFormat)

    assert SettingsService(reopened).recordingsDir() == chosen


def testPathWithSpacesRoundTrips(settingsFile: QSettings, tmp_path: Path) -> None:
    service = SettingsService(settingsFile)
    chosen = tmp_path / "RV Clips" / "Bay Star"

    service.setRecordingsDir(chosen)

    assert SettingsService(settingsFile).recordingsDir() == chosen


def testNoSketchIsRememberedInitially(settingsFile: QSettings) -> None:
    assert SettingsService(settingsFile).lastSketchPath() is None


def testLastSketchRoundTrips(settingsFile: QSettings, tmp_path: Path) -> None:
    service = SettingsService(settingsFile)
    sketch = tmp_path / "rvbhGridV2" / "rvbhGridV2.ino"

    service.setLastSketchPath(sketch)

    assert service.lastSketchPath() == sketch


def testLastSketchSurvivesANewServiceInstance(
    settingsFile: QSettings, tmp_path: Path
) -> None:
    """Upload has to still offer it after the application restarts."""
    sketch = tmp_path / "rvbhGridV3" / "rvbhGridV3.ino"
    SettingsService(settingsFile).setLastSketchPath(sketch)

    reopened = QSettings(settingsFile.fileName(), QSettings.Format.IniFormat)

    assert SettingsService(reopened).lastSketchPath() == sketch
