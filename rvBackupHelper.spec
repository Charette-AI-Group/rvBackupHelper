# -*- mode: python ; coding: utf-8 -*-
r"""PyInstaller build of the application. Driven by tools\buildExe.py.

A one-folder build rather than one-file, on purpose:

  - It starts immediately. A one-file build unpacks itself to a temporary
    folder on every launch, which for a bundle this size is seconds of nothing
    happening while somebody stands at the back of a vehicle.
  - The sketches and the TVout libraries stay browsable and compilable where
    they land, which matters when the thing you are debugging is a compile.
  - An installer wants a folder anyway.

What ships is only the read-only half: the manual, the hardware check, the
libraries and the bring-up sketch. Everything the application writes lives
under LOCALAPPDATA and is created on first run - see appConfig's two roots and
services/userDataService.py.
"""

from pathlib import Path

projectRoot = Path(SPECPATH)

# Read-only payload. Deliberately not here: arduino/rvbhGrid, which is the
# user's own generated output, and recordings/ and calibration/, which are
# theirs as well.
datas = [
    # The package's own resources. PyInstaller does not collect package data
    # on its own, and appConfig.iconPath points inside the package - so
    # without this the executable wears the icon while the running window
    # does not, which is a confusing half of the job.
    (
        str(projectRoot / "src" / "rvBackupHelper" / "resources"),
        "rvBackupHelper/resources",
    ),
    (str(projectRoot / "docs" / "manual"), "docs/manual"),
    (str(projectRoot / "tools" / "checkHardware.ps1"), "tools"),
    (str(projectRoot / "arduino" / "libraries"), "arduino/libraries"),
    (str(projectRoot / "arduino" / "rvbhBringUp"), "arduino/rvbhBringUp"),
]

# Development-only, and large enough to be worth refusing.
excludes = [
    "pytest",
    "_pytest",
    "pytest_qt",
    "ruff",
    "tkinter",
    "PyInstaller",
    # Nothing here draws a chart or renders a web page, and the Qt hook is
    # otherwise happy to bring both along.
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtCharts",
    "PySide6.Qt3DCore",
    "PySide6.QtDataVisualization",
    "PySide6.QtMultimedia",
    "PySide6.QtQuick",
    "PySide6.QtQml",
]

analysis = Analysis(
    [str(projectRoot / "src" / "rvBackupHelper" / "main.py")],
    pathex=[str(projectRoot / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=["pygrabber.dshow_graph"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(analysis.pure)

executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="rvBackupHelper",
    icon=str(projectRoot / "src" / "rvBackupHelper" / "resources" / "rvBackupHelper.ico"),
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    # No console: the application logs to a file precisely because runApp.cmd
    # already starts it without one, and a console window behind a GUI is a
    # thing users close by accident.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

collected = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="rvBackupHelper",
)
