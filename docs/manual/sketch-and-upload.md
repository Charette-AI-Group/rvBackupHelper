# 4. Sketch and upload

[← Calibrating](calibrating.md) · [Manual index](README.md) · [Next: Enclosure and vehicle install →](enclosure.md)

The last step turns the calibration into C, compiles it, and flashes it to the
board — all from inside the application.

**Contents**

* [Generating the sketch](#generating-the-sketch)
* [What the generated sketch contains](#what-the-generated-sketch-contains)
* [Uploading](#uploading)
* [Uploading by hand](#uploading-by-hand)
* [Changing what the grid looks like](#changing-what-the-grid-looks-like)
* [Tips and traps](#tips-and-traps)

---

## Generating the sketch

**Generate Arduino Sketch…** on the Calibrate tab. Pick a name; the default is
`arduino/rvbhGrid/rvbhGrid.ino`.

The Arduino tools require a sketch file to carry the same name as the folder it
sits in, so if you name a sketch something that does not match, it is given its
own folder automatically and the status bar says so. This is not fussiness: a
second `.ino` beside an existing one is treated as *another tab of the same
sketch* and collides with it, producing errors that point nowhere useful.

Versioning by name works well — `rvbhGridV1`, `rvbhGridV2` — because the
calibration each was built from is committed alongside.

> **Never hand-edit a generated sketch.** Regenerating from the JSON is one
> click, and the file says `GENERATED FILE` at the top for a reason.

## What the generated sketch contains

The measurements arrive as a table:

```c
const GridLine GRID[] PROGMEM = {
  {  92, 1,   1,  89,  16, gridLabel0 },  // 0 ft, scan line 346 of 360, frame 441
  {  86, 2,   1,  83,  16, gridLabel1 },  // 1 ft, scan line 324 of 360, frame 1001  <- emphasised
  {  78, 1,   1,  75,  16, gridLabel2 },  // 2 ft, scan line 294 of 360, frame 1642
```

Each row carries the scan line and the frame it came from, so a line that looks
wrong on the vehicle can be traced back to the moment it was measured.

The header carries the rest of the provenance — source clip, capture size,
timestamp — plus the board, library and jumper requirements, so the sketch
stands on its own if it is ever opened away from this project.

Tables and labels live in flash rather than RAM. That is not tidiness: the frame
buffer takes 1632 of the Uno's 2048 bytes at run time, and keeping the tables out
of RAM is what leaves enough stack to run at all.

## Uploading

**Upload to Arduino** compiles and flashes with `arduino-cli` — exactly what the
IDE's upload button does. It takes a few seconds and reports the board's own size
summary when it finishes, so you see what actually landed rather than an
assumption:

```
Uploaded to COM3. Sketch uses 7978 bytes (24%) of program storage space.
```

If `arduino-cli` is not installed the button says so and points you at the IDE
instead. If no board is plugged in it says that.

### Checking before you need it

**Help → Check Toolchain** answers "will this machine be able to flash the
board?" without a board attached. It compiles a sketch — the generated one if
there is one, the bring-up sketch otherwise — and reports which `arduino-cli`,
which data directory and which libraries were used:

```
Ready. Sketch uses 8374 bytes (25%) of program storage space.
```

The compile is the point. A missing AVR core once cost a working day because
every check short of building something insisted it was installed. This one
installs nothing; when something is absent it names
`tools\setupToolchain.py`, which does.

The button offers **the last sketch you generated**, remembered between
sessions — so a sketch saved as `rvbhGridV2` is still what Upload flashes after
a restart. Hover the button to see which one it will use. If that file has since
been renamed or deleted it falls back to the default path, and if nothing is
there the button is disabled and says so.

## Uploading by hand

Nothing about the app is required. Any sketch folder can be flashed directly:

```powershell
arduino-cli board list
arduino-cli compile --fqbn arduino:avr:uno --upload --port COM3 --verify arduino/rvbhGridV2
```

Success is quiet: `arduino-cli` prints only `New upload port: COM3 (serial)` and
exits zero. The absence of progress output is not a failure.

> **A hand flash does not turn the grid back on.** That is the app's doing, not
> the sketch's, and `arduino-cli` knows nothing about it. If the overlay was
> blanked for a recording it is still blanked afterwards, so finish with
> **Arduino Grid → On** on the Capture tab, or the board goes to the vehicle
> showing nothing.

## Changing what the grid looks like

A few choices live in `src/rvBackupHelper/appConfig.py` rather than in the
generated file, so they survive regeneration:

| Setting | Default | Effect |
|---|---|---|
| `emphasisedDistancesFeet` | `(1.0,)` | Which distances are drawn with a heavier line |
| `emphasisedThickness` | `2` | How many rows that heavier line takes |
| `dashLengthPixels` | `3` | Dash on/off run for the width corridor |
| `labelGapPixels` | `2` | Clear space either side of a label in its line |

Line weight is the only visual hierarchy available, since the overlay has no
colour. Thickness grows *downward*, so the far edge of a heavy line stays on the
measured distance — a thicker line never makes an obstacle look closer than it
is.

## Tips and traps

> **Upload turns the grid back on for you.** Blanking the overlay to record
> calibration footage writes that state into the board's EEPROM, where it
> survives a reflash and every power cycle after it. A board flashed at the end
> of a calibration round therefore used to come up blank in the vehicle — on the
> barrel jack, with no PC anywhere to ask it for the grid. A successful **Upload
> to Arduino** now asks the board to show the grid, and the Capture tab's toggle
> follows whatever the board answers.
>
> **If that step fails, it says so, and it must not be waved through.** The
> flash itself still succeeded, so the board is running the new grid with the
> overlay still blanked. Put it right with **Arduino Grid → On** on the Capture
> tab before the board leaves the desk.

> **Trap — a torn overlay means the build and the jumpers disagree**, not broken
> hardware. See [Hardware setup](hardware-setup.md#the-two-settings-that-must-agree-with-your-build).

**Watch the memory line when you add points.** More distances mean more table,
and the useful figure is not the percentage the compiler prints. Roughly 250
bytes of stack remain with nine points; the test suite asserts at least 200 so
this cannot creep up unnoticed.
