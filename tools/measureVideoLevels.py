"""Report black and white levels in recorded clips, to locate a level problem.

A correctly terminated composite signal puts real blacks near zero. A lifted
black floor means the whole signal is riding high, which is a signal-path
problem rather than a lighting one - an auto-exposure camera pointed at bright
concrete still gives you near-black shadows somewhere in frame.

    .venv\\Scripts\\python.exe tools\\measureVideoLevels.py recordings\\*.avi

Rough reading of the black floor:

      0 -  10   correct
     10 -  60   something is lifting the signal
     60 +       roughly double amplitude; suspect a missing or doubled 75 ohm
                termination, or a reversed connection through the shield
"""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2
import numpy as np

from rvBackupHelper.services.review.clipReaderService import ClipReaderService


def describe(path: Path, samples: int) -> None:
    reader = ClipReaderService()
    try:
        info = reader.open(path)
    except Exception as exc:
        print(f"{path.name:<32} could not open: {exc}")
        return
    try:
        indices = [int(info.frameCount * (i + 0.5) / samples) for i in range(samples)]
        lows, means, highs = [], [], []
        for index in indices:
            grey = cv2.cvtColor(reader.readFrameAt(index), cv2.COLOR_BGR2GRAY)
            low, high = np.percentile(grey, (1, 99))
            lows.append(low)
            means.append(float(grey.mean()))
            highs.append(high)
    finally:
        reader.close()

    black = float(np.mean(lows))
    verdict = "ok" if black <= 10 else ("lifted" if black <= 60 else "BADLY LIFTED")
    print(
        f"{path.name:<32} black {black:5.0f}   mean {np.mean(means):5.0f}   "
        f"white {np.mean(highs):5.0f}   {verdict}"
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("clips", nargs="+", help="clip paths or globs")
    parser.add_argument("--samples", type=int, default=12, help="frames per clip")
    args = parser.parse_args()

    print(f"{'clip':<32} {'black':>9} {'mean':>9} {'white':>9}")
    for pattern in args.clips:
        paths = sorted(Path().glob(pattern)) if "*" in pattern else [Path(pattern)]
        for path in paths:
            describe(path, args.samples)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
