"""rvBackupHelper — RV backup camera capture, calibration and overlay tooling."""

import os

# Scanning for capture devices probes indices that mostly have nothing behind
# them, and OpenCV logs a DSHOW warning for each miss. Those are expected, so
# quiet the logger before anything imports cv2. This must stay in the package
# __init__: OpenCV reads the level once, at import time.
os.environ.setdefault("OPENCV_LOG_LEVEL", "ERROR")

# The one place the version is written. appConfig re-exports it for the About
# box, and pyproject reads it from here, so a release cannot bump one and
# leave another behind - which is exactly what 0.1.1 did.
__version__ = "1.0.0"
