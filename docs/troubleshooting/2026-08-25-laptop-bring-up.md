# 2026-08-25 — Laptop bring-up, and two hours lost to a phantom toolchain

Written on the laptop, for reading on the desktop. It records what actually happened rather
than a tidied version, because the wrong turns are the useful part.

## Outcome

The app's **Upload to Arduino** button works. The cause was mundane and the diagnosis was not:
the `arduino:avr` core had never been installed on this machine, and every check that should
have caught that reported the opposite.

Along the way the app gained real diagnostics, which is the lasting benefit.

## Root cause, stated plainly

`arduino-cli` said, from the first attempt to the last:

```
Error during build: Platform 'arduino:avr' not found: platform not installed
Try running `arduino-cli core install arduino:avr`
```

**That message was correct the entire time, and its suggested fix was the right one.**

The AVR core was genuinely absent: `%LOCALAPPDATA%\Arduino15\packages` contained only
`builtin` (the ctags, dfu/mdns/serial discovery and serial-monitor tools) — no `arduino`
folder, so no `hardware\avr`, so no core.

The reason this took two hours is that **Claude's tool calls were operating against a
filesystem view in which `packages\arduino` existed.** Every verification run through the
assistant agreed the core was installed:

| Check, run via the assistant | Reported |
|---|---|
| `arduino-cli core list` | `arduino:avr 1.8.8` installed |
| `Test-Path ...\packages\arduino` | `True` |
| `arduino-cli compile arduino/rvbhGrid` | `Sketch uses 8374 bytes (25%)` |
| `arduino-cli upload --verify` | `8374 bytes of flash verified` |
| `pytest` incl. `testSketchCompiles.py` | passed, did not skip |

None of that reflected this machine. The contradiction was only resolved by running a probe
from a process the *user* launched, which saw the truth. Two views of the same path, taken
minutes apart:

```
assistant's view : packages -> ['arduino', 'builtin']
real process     : packages -> ['builtin']            <- the actual state
```

**The lesson**: when a tool reports a problem with the environment, evidence gathered by the
agent about that same environment is not independent. Confirm from a process the user starts.

## The fix

Run in a normal terminal, by the user, not through the assistant:

```powershell
arduino-cli core install arduino:avr
arduino-cli core list          # must list arduino:avr
```

## Wrong hypotheses, in the order they were chased

Recorded so the same ground is not re-covered. Each was disproved by evidence, and each
delayed the answer.

1. **Port contention** — the grid toggle holds COM7 for up to ~4 s, so clicking Upload just
   after a failed toggle would find the port busy. Plausible, unfounded: the failure text was
   a build error, which happens before the port is touched.
2. **A second arduino-cli with its own data directory.** Only one exists on the machine.
3. **A different data directory from a different environment** (`LOCALAPPDATA`, elevation, a
   different user). This drove two rounds of work. Killed when the app reported
   `Data directory: C:\Users\Francois\AppData\Local\Arduino15` — the correct one.
4. **`ARDUINO_*` environment variables or an `arduino-cli.yaml`** redirecting the lookup. None
   set, none present, `config dump` empty.
5. **A `sketch.yaml` profile** demanding an uninstalled platform. No such file in the repo.
6. **A junction or redirect on `Arduino15`.** A plain directory, no reparse point.
7. **A permissions problem** stopping traversal below `packages`. This one was worth chasing —
   the probe's `is_dir()` filter returned `False` both for absent and for unreadable
   directories, so it could not tell them apart. Fixing that probe is what produced the
   directory listing that finally showed only `builtin`.

## What the app gained

Real changes, all committed today, and worth keeping regardless of the cause:

| Commit | Change |
|---|---|
| `da21acd` | Repaired the corrupted TVout check in the RV checklist |
| `80992ae` | Upload failures name the arduino-cli binary and its data directory |
| `1bdd953` | Upload failures shown in a dialog, not only the truncating status bar |
| `160a063` | **Logging to `logs/rvBackupHelper.log`**, plus unhandled exceptions |
| `c14f3b5` | Failures quote the exact command, and what `core list` sees in-process |
| `886a0e0` | Failures also check for cores on disk, bypassing arduino-cli |
| `1a614a5` | The on-disk check says *where* it stops instead of reporting a bare absence |

Two of these deserve emphasis:

- **There was no logging at all.** `runApp.cmd` starts `pythonw`, which has no console, and
  nothing configured a handler — so every `logger.info` in the services was discarded. The app
  kept no record of anything it did, which is why so much had to be reproduced by hand.
- **The status bar silently truncated the diagnosis.** The first fix added the data directory
  to the message, and it was invisible: `onUploadFailed` flattened everything onto a one-line
  status bar. It looked like the change had done nothing. A message that cannot be read is
  the same as no message.

## Findings worth keeping, unrelated to the core

Two came out of the same session and both matter at the vehicle.

**The board cannot answer serial commands without video.** `rvbhGrid` polls serial from
TVout's horizontal blanking hook (`tv.set_hbi_hook(pserial.begin(...))`), and in overlay mode
TVout's timing is slaved to the *incoming* sync. No video into the shield means no blanking
interrupts, so nothing reads the UART, and `loop()` waits in `tv.delay_frame(2)` for frames
that never arrive. The grid toggle will be silent — and since the rear camera is likely
powered only in reverse gear, **stay in reverse while toggling the grid.** This looks exactly
like the wrong-TVout fault and is not.

**Washed-out composite with no colour is a bad RCA contact, not an overexposed source.**
Measured on the bench VHS feed before and after reseating the plug:

| | p1 (black floor) | mean | saturation | coloured pixels |
|---|---|---|---|---|
| Bad contact | 146 | 224 | 3.2 | **0.0%** |
| Good contact | **20** | 126 | 26.1 | **21.6%** |

Lifted blacks *with almost no clipping and dead chroma* is a contact fault. Genuine
overexposure clips whites and keeps its colour. Note it took several reseats before contact
was actually good — one failed attempt does not clear the cable. This bears on the open
"washed-out RV footage" item in `CLAUDE.md`, which currently attributes it to a 75 ohm
termination; `tools/measureVideoLevels.py` measures luma only, so it cannot see the chroma
half of that signature.

## Verifying a machine really has the toolchain

The check that settles it, run from a terminal on the machine itself:

```powershell
arduino-cli core list
Select-String TIMER1_CAPT_vect "$env:USERPROFILE\Documents\Arduino\libraries\TVout\video_gen.cpp"
```

`arduino:avr` must be listed, and the second must return exactly one match — one match is the
Video Experimenter fork, none is the stock TVout, which compiles happily and then leaves the
board resetting on every sync pulse.

Confirmed on this laptop from a user-launched process:

```
arduino\hardware\avr\1.8.8
libraries    : ['TVout', 'TVoutfonts', 'pollserial']
video_gen.cpp: 16461 chars, TIMER1_CAPT_vect x1
verdict      : the Video Experimenter fork
core list    : arduino:avr 1.8.8
```

The TVout libraries were real all along; only the core was missing.

## Open items

- **The board's flash state is unknown.** The uploads reported during this session ran through
  the same unreliable view, so do not assume `rvbhGrid` is on it. Re-flash and confirm by
  asking the board `?` with video going into the shield.
- `arduino/rvbhGrid/rvbhGrid.ino` has an uncommitted regeneration in the working tree. Its
  header source clip lost the `rvbh-` prefix (`2026-08-19_09-39-59.mkv`), which may be
  unintended.
- `pytest` figures quoted **earlier** today (224, 227, 237 passing) included
  `testSketchCompiles.py` running against the phantom toolchain and meant nothing. Re-run after
  the core was really installed: **237 passed, 0 skipped**. Worth running once from your own
  terminal to be certain, since that is the whole point of this document.
