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

> **Close OBS first.** Only one application can hold a capture device at a time. If OBS (or
> a video-call app) is running with the grabber as a source, RVBH opens the device but
> receives no frames — even though the video is plainly visible in OBS.

**Capture tab** — press **Scan Devices** to find capture hardware. Devices are listed by
their Windows name, so the grabber (`USB Video`) is easy to tell from a webcam. A device
that opens but is not receiving video is listed as **no video** rather than hidden; hover it
for the reason, which is either nothing connected or another app holding the device. The
scan opens and closes each device in turn and takes a few seconds; it runs off the GUI
thread.

Pick the device, press **Start Capture** for a live preview, and **Start Recording** to
write a clip. Starting capture on a device with no signal is fine: the preview shows
"Waiting for video signal" and starts as soon as video arrives, which is what an RV camera
powered only in reverse gear needs.

Clips are timestamped `.avi` files, MJPG encoded. MJPG compresses each frame on its own,
so every frame decodes independently and seeking is frame-exact — which is what calibration
measurements need.

They are written to `recordings/` inside the project by default, which is **git-ignored** so
video never reaches GitHub. Change the destination with **File → Recordings Folder…**; the
choice persists between sessions and the current location is always shown at the right-hand
end of the status bar. Pointing it outside the project is the safer habit — no reliance on
the ignore rule — and it is what you want on the laptop, where clips can go straight to an
external drive.

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
