# RV Backup Helper

RV backup camera video capture, grid calibration and OSD overlay tooling

## One-time setup

```powershell
cd W:\projects\26rvBackupHelper
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

## Daily workflow

```powershell
cd W:\projects\26rvBackupHelper
.\.venv\Scripts\Activate.ps1
rv-backup-helper
```

Or without the script entry point:

```powershell
python -m rvBackupHelper.main
```

Or just double-click **`runApp.cmd`** in the project folder (needs the one-time setup done first).

## Using the app

**Capture tab** — press **Scan Devices** to probe for capture hardware (OpenCV has no
enumeration API, so this opens and closes each device index in turn and takes a few
seconds). Pick the grabber from the list, press **Start Capture** for a live preview,
and **Start Recording** to write a clip.

Clips land in `recordings/` as timestamped `.avi` files, MJPG encoded. MJPG compresses
each frame on its own, so every frame decodes independently and seeking is frame-exact —
which is what calibration measurements need. The folder is git-ignored.

**Review tab** — open a clip and step through it with the slider, the frame spin box, or
Previous/Next. A clip you just recorded is loaded here automatically. This is the
calibration workhorse: find the frame where the measuring tape is readable and hold on it.

## Tests and lint

```powershell
pytest
ruff check src tests
```

## Structure

| Layer | Folder | Purpose |
|-------|--------|---------|
| Entry | `src/rvBackupHelper/main.py` | Start `QApplication`, show main window |
| Config | `src/rvBackupHelper/appConfig.py` | Paths, defaults, app metadata |
| UI | `src/rvBackupHelper/ui/` | Widgets and dialogs only |
| Services | `src/rvBackupHelper/services/` | Business logic (no Qt widgets) |
| Models | `src/rvBackupHelper/models/` | Plain Python data types |

See `AGENTS.md` for architecture and naming conventions (for you and AI agents).

---
*Created from the Qt App Template.*
