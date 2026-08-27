# Bundled resources

Files the application loads at runtime. Paths come from
[`appConfig.py`](../appConfig.py) — never build one by hand, because a frozen build reads them
from the bundle rather than from the source tree, and `appConfig` is what knows the difference.

## The icon

**Do not edit `rvBackupHelper.ico`.** It is generated — edit the drawing and re-run it:

```powershell
.venv\Scripts\python.exe tools\makeIcons.py
```

| File | Used for | Found through |
|---|---|---|
| `rvBackupHelper.ico` | The window, the taskbar, the executable and the installer | `appConfig.iconPath` |

It carries **16, 24, 32, 48, 64, 128 and 256 px**, each one *drawn* at that size rather than
shrunk from the largest: below about 24 px a scaled-down rendering loses its strokes and turns
to mush, so the generator thickens lines and drops detail as it goes down. At 16 px what
survives is a corridor and one amber line, which is the least that still says what this is.

The artwork is what the driver sees — distance lines across a receding corridor, the nearest
one amber and heavier because it is the "about to touch something" line that
`appConfig.emphasisedDistancesFeet` marks on the board. Following the approach pySPWB uses for
its own icons, including the hand-packed multi-size `.ico`.

If the file is missing the application starts anyway and logs that it did: an icon is not worth
refusing to run over. `tests/testIcons.py` checks that it exists, carries every size, and is
actually worn by the window.
