"""Measure how much the shield's overlay wanders, in pixels.

Turns "the overlay looks jumpy" into a number you can watch while adjusting
the R4 pot on the Video Experimenter, which is the documented remedy for
vertical jumpiness.

    .venv\\Scripts\\python.exe tools\\measureOverlayJitter.py "R4 one turn up"

Point the shield's video OUT at the USB grabber, flash a sketch that draws
horizontal lines (arduino/rvbhBringUp), then run this. Lower is better.

IMPORTANT: repeat every measurement three or four times before believing it.
On an unstable source the same firmware has measured anywhere from 1.3 to
5.5 px, so a single reading tells you very little.
"""

from __future__ import annotations

import argparse

import numpy as np

from rvBackupHelper.models.captureModels import CaptureSettings
from rvBackupHelper.services.capture.cameraService import CameraService

grabberLabel = "USB Video"
warmupFrames = 15
# The composite chain washes the overlay down to roughly 130-180, not white.
brightness = 130
# An overlay line spans the picture; video rarely produces a full bright row.
coverage = 0.50
searchWindow = 40


def rowCoverage(frame: np.ndarray) -> np.ndarray:
    return (frame.max(axis=2) > brightness).mean(axis=1)


def findLines(fraction: np.ndarray) -> list[int]:
    rows = np.flatnonzero(fraction > coverage)
    if rows.size == 0:
        return []
    groups = np.split(rows, np.flatnonzero(np.diff(rows) > 2) + 1)
    return [int(round(group.mean())) for group in groups]


def trackLine(fraction: np.ndarray, expected: int) -> int | None:
    """Strongest covered row near where the line was, or None if it vanished.

    Searching a window around the previous position is what stops the measure
    from silently comparing one line against a different one.
    """
    low = max(0, expected - searchWindow)
    high = min(len(fraction), expected + searchWindow + 1)
    window = fraction[low:high]
    if window.max() <= coverage:
        return None
    return low + int(np.argmax(window))


def capture(frameCount: int) -> list[np.ndarray]:
    service = CameraService()
    grabber = next(
        (device for device in service.listDevices() if grabberLabel in device.label),
        None,
    )
    if grabber is None:
        raise SystemExit(f"No capture device labelled '{grabberLabel}' was found.")
    service.open(CaptureSettings(deviceIndex=grabber.index, backend=grabber.backend))
    try:
        for _ in range(warmupFrames):
            service.readFrame()
        frames = []
        while len(frames) < frameCount:
            frame = service.readFrame()
            if frame is not None:
                frames.append(rowCoverage(frame))
        return frames
    finally:
        service.close()


def report(label: str, frames: list[np.ndarray]) -> None:
    reference = findLines(frames[0])
    print(f"--- {label} ---")
    print(f"Frames: {len(frames)}   lines found at rows: {reference}")
    if not reference:
        print("No overlay lines in the reference frame - is a grid sketch running?")
        return

    deviations = []
    for expected in reference:
        found = [trackLine(fraction, expected) for fraction in frames]
        seen = [value for value in found if value is not None]
        if len(seen) < len(frames) * 0.5:
            print(f"  row {expected:3d}: lost too often to measure")
            continue
        offsets = np.array(seen) - expected
        steps = np.abs(np.diff(np.array(seen)))
        deviations.append(float(offsets.std()))
        print(
            f"  row {expected:3d}: sd {offsets.std():5.2f} px   "
            f"range {offsets.max() - offsets.min():3d} px   "
            f"moved >1px on {100 * (steps > 1).mean():3.0f}% of frames"
        )

    if deviations:
        # Mean of the per-line deviations. Pooling raw offsets would instead
        # measure how far the lines sit from each other, not how much they shake.
        print(f"JITTER: {np.mean(deviations):.2f} px (mean per-line sd) - lower is better")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("label", nargs="?", default="overlay", help="note for the output")
    parser.add_argument("--frames", type=int, default=150, help="frames to capture")
    parser.add_argument("--repeat", type=int, default=3, help="measurement passes")
    args = parser.parse_args()

    for pass_ in range(1, args.repeat + 1):
        report(f"{args.label} (pass {pass_} of {args.repeat})", capture(args.frames))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
