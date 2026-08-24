r"""Report black, white and clipping levels in recorded clips.

Composite video that is riding too high clips at the white end: real detail
gets flattened into 255 and cannot be recovered. That is the reliable symptom,
because it does not depend on what is in shot.

A lifted black floor on its own is weaker evidence. A sunlit concrete driveway
genuinely contains no black, so a high floor there is the scene, not the
signal. Read the two together: clipping plus a lifted floor means the signal is
too big; a lifted floor with no clipping usually just means a bright scene.

    .venv\Scripts\python.exe tools\measureVideoLevels.py recordings\*.avi
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from rvBackupHelper.services.review.clipReaderService import ClipReaderService

# Above this share of pixels pinned at white, detail is being lost.
clippingWarnPercent = 0.5
clippingBadPercent = 2.0


def verdictFor(clipped: float, black: float) -> str:
    if clipped >= clippingBadPercent:
        return "CLIPPING - signal too high"
    if clipped >= clippingWarnPercent:
        return "some clipping"
    if black > 60:
        return "ok, but bright scene"
    return "ok"


def describe(path: Path, samples: int) -> None:
    reader = ClipReaderService()
    try:
        info = reader.open(path)
    except Exception as exc:
        print(f"{path.name:<32} could not open: {exc}")
        return
    try:
        indices = [int(info.frameCount * (i + 0.5) / samples) for i in range(samples)]
        lows, means, highs, clipped = [], [], [], []
        for index in indices:
            grey = cv2.cvtColor(reader.readFrameAt(index), cv2.COLOR_BGR2GRAY)
            low, high = np.percentile(grey, (1, 99))
            lows.append(low)
            means.append(float(grey.mean()))
            highs.append(high)
            clipped.append(100.0 * float((grey >= 254).mean()))
    finally:
        reader.close()

    black = float(np.mean(lows))
    pinned = float(np.mean(clipped))
    print(
        f"{path.name:<32} {info.frameWidth}x{info.frameHeight}  "
        f"black {black:5.0f}  mean {np.mean(means):5.0f}  white {np.mean(highs):5.0f}  "
        f"clipped {pinned:5.2f}%  {verdictFor(pinned, black)}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clips", nargs="+", help="clip paths or globs")
    parser.add_argument("--samples", type=int, default=12, help="frames per clip")
    args = parser.parse_args()

    for pattern in args.clips:
        paths = sorted(Path().glob(pattern)) if "*" in pattern else [Path(pattern)]
        for path in paths:
            describe(path, args.samples)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
