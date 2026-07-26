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
