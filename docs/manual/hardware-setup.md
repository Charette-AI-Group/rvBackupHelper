# 1. Hardware setup

[← Manual index](README.md) · [Next: Capturing footage →](capturing-footage.md)

Everything else assumes this page is done. It is worth doing carefully once,
because most of the confusing failures further along are really a wrong switch
here.

**Contents**

* [Where this approach comes from](#where-this-approach-comes-from)
* [What the rig is](#what-the-rig-is)
* [Wiring](#wiring)
* [The two settings that must agree with your build](#the-two-settings-that-must-agree-with-your-build)
* [Proving the rig before you trust it](#proving-the-rig-before-you-trust-it)
* [The software toolchain](#the-software-toolchain)
* [Tips and traps](#tips-and-traps)

---

## Where this approach comes from

An RV backup camera is analogue composite video — the same CVBS signal
television used before HDMI. That is unglamorous, and it is exactly why this
works: composite is a single wire carrying brightness and sync together, and a
chip can slice the sync out of it and inject extra brightness on top without
understanding the picture at all. That trick is old. Character generators did it
for broadcast captions in the 1970s, and radio-controlled aircraft have used the
same idea for decades to put battery voltage and altitude over a live camera
feed.

The alternative would be to digitise the video, draw on it, and re-encode it.
That is easy to write and wrong for this job: it inserts a computer between the
driver and the rear view. If it hangs, the picture goes with it. The analogue
overlay adds nothing to the signal path when it fails — the camera passes
straight through and the driver simply sees no lines.

## What the rig is

| Part | Notes |
|---|---|
| **Arduino Uno R3** or Duemilanove | Must be an ATmega328P. **Not** an Uno R4 — the video library is hand-written AVR assembly and will not run on the R4's Renesas chip. Leonardo and Mega are also out. |
| **Nootropic Design Video Experimenter** shield | The overlay hardware. Sits on the Uno. |
| **USB video capture dongle** | To record the camera onto a PC. Any UVC composite grabber. |
| RCA leads | Composite is one signal wire and a ground. |

## Wiring

```
   RV camera ──▶ Video Input ─┤ shield ├─ Video Output ──▶ display or USB grabber
```

Signal in, overlay mixed in, signal out. That is the whole of it.

For calibration work the output goes to the USB grabber so the PC can record it.
In the vehicle it goes to the display instead — the shield sits inline where you
originally tapped the camera feed.

## The two settings that must agree with your build

The shield has a jumper and a slide switch. They must match the sketch you
flashed, and a mismatch does not look like a mismatch — it looks like broken
hardware.

| Setting | For the overlay (normal use) | For a standalone test |
|---|---|---|
| **SYNC SELECT** | jumper on the two **rightmost** pins — sync taken from V INPUT | two **leftmost** pins — sync generated on pin 9 |
| **OUTPUT SELECT** | **Overlay** | **Sync only** |
| Sketch built with | `USE_OVERLAY 1` | `USE_OVERLAY 0` |

There is also a small **R4** pot in the lower left. It tunes the sync separator.
Leave it fully counter-clockwise and only raise it if the overlay is vertically
jumpy.

> **Trap — a torn or doubled overlay is not broken hardware.** If the pattern
> appears but drifts, tears, or shows twice, the *build and the jumpers
> disagree*. A `USE_OVERLAY 0` build free-runs its own sync, so with OUTPUT
> SELECT on Overlay it slides against the incoming video. Flashing the matching
> build fixes it with no wiring change at all.

## Proving the rig before you trust it

`arduino/rvbhBringUp/` is a diagnostic sketch that draws a border, three
labelled reference rows and the current mode. Flash it before the real grid, so
that a later problem is known to be in the calibration and not the rig.

What to look for:

* **All four border edges.** A missing side means the frame buffer is not the
  size the sketch thinks it is.
* **The on-board LED blinking steadily.** That is the sketch telling you it
  could not allocate its frame buffer, so nothing will ever be drawn. It blinks
  rather than failing silently, because the shield still passes video through
  and you would otherwise just see no grid and no reason.

## The software toolchain

**The full list lives in *One-time setup* in the project README**, written for a
machine with nothing on it and kept in that one place so the copies cannot
drift. In short: Python 3.14 and a virtual environment for the application,
then one command for the rest —

```powershell
.venv\Scripts\python.exe tools\setupToolchain.py
```

which installs `arduino-cli` and the AVR core if they are missing and then
compiles the real sketch to prove this machine can. The Arduino IDE is **not**
required: the app uploads by itself, and the IDE is only useful if you want to
hand-edit a sketch.

The video library needs nothing at all. It is a **fork** — the TVout in the
Arduino library manager will not work, and produces a board that uploads
cleanly and then answers nothing — so the right one is committed to this
repository at `arduino/libraries` and compiled against from there. A clone has
it, and whatever sits in `Documents\Arduino\libraries` is not consulted.

Confirm the whole chain with `pytest`, or with **Help > Check Toolchain** in the
app. With the toolchain present the suite compiles a real sketch for an Uno as
one of its tests; without it that test skips itself rather than failing, so a
skip there is worth reading as a missing AVR core.

## Tips and traps

> **Trap — a clone Uno needs the CH340 driver.** A genuine Arduino is
> recognised by Windows on its own. Clones usually are not, and the symptom is
> simply no serial port. Install the driver before leaving for the vehicle, not
> at the campground.

> **Trap — the camera may only be powered in reverse gear.** Many RV cameras
> are wired that way. If nothing appears, check the ignition and gear selector
> before suspecting the shield.

**SRAM is the real constraint on this board, and the compiler hides it.** The
video library allocates its frame buffer at run time — 1632 bytes of the Uno's
2048 — and that never appears in the "global variables" figure a build reports.
A sketch that compiles with "4% of dynamic memory" used is not roomy. If you
ever edit a generated sketch, watch that, not the percentage.
