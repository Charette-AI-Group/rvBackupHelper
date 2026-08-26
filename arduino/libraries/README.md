# Vendored Arduino libraries

These three folders are the **Video Experimenter fork of TVout**, copied here verbatim from
<https://github.com/nootropicdesign/arduino-tvout-ve> at commit `cfb3c7a` (2024-03-30). MIT
licensed — see `LICENSE`, which is the fork's own, kept alongside the code as the licence
requires.

## Why they live in the repo

The stock TVout compiles the generated grid sketch without a murmur and then leaves the input
capture interrupt `initOverlay()` enables with no handler, so the board resets on every sync
pulse. The only symptom is a board that uploads cleanly and never answers. That cost a bench
session on 2026-08-25, and the fix was a manual copy into `Documents\Arduino\libraries` that
nothing in the repo could check or guarantee.

They are 281 KB and they change roughly never. Committing them turns "install this correctly by
hand on every machine" into "clone the repo", and there is no longer a wrong version to install.

## How the app finds them

`UploadService` sets `ARDUINO_DIRECTORIES_USER` to the `arduino/` folder above this one, which
makes that folder arduino-cli's sketchbook — and a sketchbook's `libraries/` is where it looks.
Whatever is in `Documents\Arduino\libraries` is then irrelevant, including a wrong or missing
copy. `tests/testServices/testSketchCompiles.py` compiles through the same setting.

To compile by hand with the same libraries:

```powershell
$env:ARDUINO_DIRECTORIES_USER = "$PWD\arduino"
arduino-cli compile --fqbn arduino:avr:uno arduino/rvbhGrid
```

## Re-syncing with upstream

Rarely needed, but if upstream moves:

```powershell
git clone https://github.com/nootropicdesign/arduino-tvout-ve $env:TEMP\tvout-ve
robocopy $env:TEMP\tvout-ve\TVout arduino\libraries\TVout /MIR
robocopy $env:TEMP\tvout-ve\TVoutfonts arduino\libraries\TVoutfonts /MIR
robocopy $env:TEMP\tvout-ve\pollserial arduino\libraries\pollserial /MIR
```

Then run `pytest tests/testServices/testSketchCompiles.py` and note the new commit above. Do
not edit these files in place: the next re-sync would silently discard the change.
