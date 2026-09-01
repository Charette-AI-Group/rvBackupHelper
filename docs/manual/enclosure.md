# 5. Enclosure and vehicle install

[← Sketch and upload](sketch-and-upload.md) · [Manual index](README.md)

The first four pages end with a flashed board sitting on a desk and RCA leads
hanging off it. This page is about turning that into something that can live
behind the dash of a moving vehicle for years. None of it is difficult, but two
of the decisions are hard to undo once the holes are drilled, so they are worth
making deliberately.

**Contents**

* [What has to fit](#what-has-to-fit)
* [Keep the 4-pin connectors outside the box](#keep-the-4-pin-connectors-outside-the-box)
* [Choosing the box](#choosing-the-box)
* [Height is the dimension that bites](#height-is-the-dimension-that-bites)
* [Layout](#layout)
* [Holes, glands and service access](#holes-glands-and-service-access)
* [Power](#power)
* [Mounting and vibration](#mounting-and-vibration)
* [What changes if you move to the MAX7456](#what-changes-if-you-move-to-the-max7456)

---

## What has to fit

| Item | Size | Note |
|---|---|---|
| Uno R3 PCB | 68.6 × 53.4 mm | USB-B and barrel jack overhang the edge by about 2 mm |
| Uno + shield stack | **40–50 mm tall — measure yours** | See [Height](#height-is-the-dimension-that-bites) |
| 12 V to 9 V regulator | about 15 × 10 × 12 mm | Do not feed a raw RV rail to VIN |
| Fuse holder and TVS diode | about 40 mm inline | Transient voltage suppressor, see [Power](#power) |
| RCA plug and bend radius | 40 mm clear ahead of the jacks | The plug is longer than you remember |
| Voyager 4-pin mated pair | about 20 mm across, 80–90 mm long, **each** | This is what decides the box size |

## Keep the 4-pin connectors outside the box

Two mated Voyager 4-pin junctions consume something like 180 mm of length
between them. Put both inside and there is no room left for the Arduino in any
enclosure you would willingly mount behind a dash. So do not put them inside.
Break the Voyager connector out to RCA and 12 V *outside* the box with an
adapter pigtail — ASA part 31300006 is the 4-pin-to-RCA-with-power lead — and
bring only thin cable in through the glands.

```
                       ┌── outside the box ────┐
   camera ══4-pin══▶   │  4-pin → RCA + 12 V   │
                       └───────────┬───────────┘
                                   │  RCA + 12 V, through a gland
                       ┌───────────▼───────────┐
                       │  V IN                 │
                       │     Uno + shield      │   inside the box
                       │                V OUT  │
                       └───────────┬───────────┘
                                   │  RCA, through a gland
                       ┌───────────▼───────────┐
  display ◀══4-pin══   │  RCA → 4-pin          │
                       └───────────────────────┘
```

There is a second reason, and it is the better one. With the mating outside, a
dead Arduino is bypassed at the roadside by unplugging two adapters and mating
the camera and display 4-pins straight to each other. No tools, no lid, no
wire. For a live backing aid that is worth more than the tidiness of hiding the
connectors.

## Choosing the box

**Hammond 1554H2GYCL** — 180.3 × 119 × 61 mm, polycarbonate, clear gasketed
lid, IP66, UV stabilised, four M4 stainless screws into moulded stainless
bushings. Around $25–35.

The clear lid is the reason to pick this over a cheaper opaque ABS box, and the
reason is diagnostic rather than decorative. The bring-up sketch reports a
failed frame-buffer allocation by blinking the on-board LED, and tuning R4 is a
watch-the-picture-and-turn-the-pot job. Both are things you want to do without
first removing four screws in an awkward space.

| Alternative | Size (mm) | When |
|---|---|---|
| Hammond 1591ESBK | 190.5 × 110 × 61, ABS, IP54, about $13 | Dry location, budget build. No gasket, opaque. |
| Hammond 1554W2GY | 180 × 180 × 66 | Square, more room to coil pigtail slack |
| Hammond 1554VA2GYCL | 238.8 × 160 × 88.9 | Only if you insist on the mated 4-pins living inside |

> **Check the internal dimensions against Hammond's own drawing before
> committing to a layout.** The usable interior of the 1554H is roughly
> 168 × 107 × 50 mm, but the tongue-and-groove lid joint and the corner bosses
> eat into that unevenly, and the figure quoted here is approximate.

## Height is the dimension that bites

The footprint is easy — the Uno takes about a third of the floor. Height is
what sends people back to the supplier.

```
   lid  ─────────────────────────────────────      61 mm external
          │  clearance for wiring          ~5 mm
          ├──────────────────────────────────
          │  RCA jacks / pot shaft        ~13 mm   ◀ tallest item
          ├── shield PCB ─────────────────  1.6 mm
          │  stacking header gap          ~13 mm
          ├── Uno PCB ────────────────────  1.6 mm
          │  M3 standoffs                   12 mm
   floor ─────────────────────────────────
                                     about 46 mm of ~50 mm usable
```

> **Trap — the tallest thing on the shield is probably not the RCA jacks.** It
> is the threshold potentiometer with the long shaft, which can stand 20 mm or
> more above the board and will quietly cost you 20 mm of box. That pot serves
> the frame-capture threshold feature, which the distance grid does not use, so
> the shaft can be shortened with a hacksaw. The one that must stay reachable is
> the small **R4** trimmer that tunes the sync separator.

Measure your assembled stack, from the bottom of the Uno to the top of its
tallest component, before ordering. If it comes out above about 45 mm and you
are not willing to trim the shaft, go to the 88.9 mm box instead.

## Layout

```
        ┌──────────────────────────────────────────────────────────┐
   ═════╡         ┌───────────────────────────┐  ┌──────────────┐  │
   cam  ╡  40 mm  │ [V IN ]                   │  │ fuse 500 mA  │  │
   ═════╡  clear  │                           │  │ + TVS        │  ╞═════
        │  for    │  Arduino Uno R3           │  └──────────────┘  │ USB
   ═════╡  plugs  │  + Video Experimenter     │                    ╞═════
   dsp  ╡  and    │  68.6 × 53.4 mm           │  ┌──────────────┐  │
   ═════╡  bends  │  on 12 mm M3 standoffs    │  │ R-78E9.0-0.5 │  │
        │         │ [V OUT]                   │  │ 12 V → 9 V   │  │
        │         └───────────────────────────┘  └──────────────┘  │
        └──────────────────────────────────────────────────────────┘
          ▲                                                      ▲
          2 × PG9 gland                                service USB-B

               interior about 168 × 107 mm, seen from above
```

The Uno sits with its jack edge facing the gland wall, which keeps the RCA
leads short and stops them looping back across the board. Everything on the
right is the power chain. It carries no video, so it can be crowded without
consequence.

## Holes, glands and service access

* **Two PG9 glands** on one short wall: camera in (RCA plus 12 V) and display
  out (RCA).
* **A panel-mount USB-B on the opposite wall.** Do not skip this. Every
  recalibration regenerates and reflashes a sketch, and a buried box with no USB
  access means unscrewing the lid every time. A Neutrik NAUSB-W keeps the seal;
  a plain USB-B bulkhead extension is fine in a dry location.

Drill from the inside out where you can, and deburr. Polycarbonate chips, and a
chip trapped under the lid gasket is a leak.

## Power

The Voyager 4-pin carries 12 V for the camera alongside the video, so tap it
there. On many installations that line is live only in reverse gear, which is
exactly what you want — the overlay powers up with the camera. Expect a second
or two of picture before the grid appears, while the sketch boots and TVout
allocates its 1632-byte buffer.

Do not run the Uno from the RV rail directly. A charging rail sits at
13.8–14.8 V and carries transients well above that. [The reason this is not
optional](#why-not-feed-it-the-12-v-rail-directly) is at the end of this
section, and it is not the one most people expect. The chain is:

```
   12 V tap ──▶ 500 mA fuse ──▶ TVS (SMBJ16CA) ──▶ R-78E9.0-0.5 ──▶ barrel jack
```

The **TVS** — transient voltage suppressor — is the part that does nothing at
all until it matters. Below its 16 V standoff it is invisible to the circuit.
Above it, it conducts hard and clamps the spike at around 26 V, comfortably
under the regulator's 28 V limit, absorbing the energy that would otherwise
reach the Arduino. That is what the pairing is for: the regulator handles the
normal rail, the TVS catches what the regulator could not survive. The worst
case it exists for is load dump, where a battery connection opens while the
alternator is charging and the rail can reach 40 V for a few hundred
milliseconds.

> **A bidirectional TVS is not reverse-polarity protection.** The `CA` suffix
> means it clamps transients of either polarity, which is worth having in a
> vehicle. It does not mean you can wire the 12 V tap backwards — do that and
> the TVS conducts continuously and burns, and you are relying on the fuse
> blowing first. Guarding against that is the barrel jack's job, below.

The R-78E accepts up to 28 V in and needs no heatsink.

### What the Arduino needs at the jack

| | Voltage |
|---|---|
| Absolute limits | 6–20 V |
| Recommended | 7–12 V |
| This build | **9 V** |

The floor is set by the dropout of the Uno's own NCP1117 linear regulator, not
by anything digital. Below about 7 V it can no longer hold a true 5 V, the rail
sags, and the board misbehaves in ways that look like a shield fault rather than
a power fault. The ceiling is purely thermal: the NCP1117 burns the whole
difference between its input and 5 V as heat, in a small package on a small
copper pad.

That is why this runs at 9 V rather than 12 V, and it matters more here than on
a desk because the box is sealed. Taking the Uno and the shield together at
roughly 100 mA:

```
   at  9 V:  (9 - 5) x 0.1 = 0.4 W burnt in the regulator
   at 12 V:  (12 - 5) x 0.1 = 0.7 W
```

Behind a dash in summer the air in that box can be near 50 °C before the Arduino
heats anything at all. 0.4 W is comfortable there; 0.7 W is not. 9 V also leaves
real margin above the 7 V floor, which 7.5 V would not once regulator tolerance
and rail droop are allowed for.

> **Feed the barrel jack, not the VIN pin.** The jack's path to VIN runs through
> a series reverse-protection diode; the VIN pin bypasses it. The ~0.7 V that
> diode costs is irrelevant at 9 V — the regulator still sees about 8.3 V — and
> it buys protection against the one failure the TVS does not cover. Reverse the
> polarity into the barrel jack and the diode simply blocks.

The other common approach is a 5 V converter wired straight to the 5 V pin,
skipping the on-board regulator for better efficiency. Avoid it here. That pin
has no protection ahead of it at all, so a converter that fails high puts
unregulated volts directly onto the ATmega.

### Why not feed it the 12 V rail directly

A fair question, because 12 V is inside the Uno's recommended range. On a bench,
in open air, off a bench supply, connecting it directly is fine. In the vehicle
it is not, and the reason that settles it is not heat.

**The numbers leave no room for a TVS.** Work through what a protection diode
would have to do if the Arduino were the first thing on the rail:

| | |
|---|---|
| Rail while charging | up to 14.8 V — the TVS must ignore this |
| So the lowest usable standoff | 16 V |
| Which breaks down at | 17.8–19.7 V |
| And clamps at up to | **26 V** |
| NCP1117 absolute maximum input | **20 V** |

The clamp sits above the part it is supposed to protect. That is not fixed by
choosing a better TVS: the window between *must stay dormant at 14.8 V* and
*must hold below 20 V* is too narrow for any TVS to occupy, because a TVS clamps
well above its own breakdown voltage once real surge current flows through it.
There is no arrangement in which a diode alone protects the Uno's own regulator
on an RV rail.

The R-78E is what closes that gap. Rated to 28 V in, it sits above the 26 V
clamp, which finally gives the TVS something it can protect. The buck regulator
is not a convenience in this chain — it is the part that makes the protection
scheme valid at all.

**Heat is the second reason, and the weaker one.** The rail is not 12 V, it is
13.8–14.8 V while charging, so a direct connection runs at or past the top of
the recommended range continuously, inside a sealed box:

```
   at 14.4 V:  (14.4 - 5) x 0.1 = 0.94 W burnt in the NCP1117
```

For a SOT-223 on the Uno's modest copper pour, in air that can already sit near
50 °C behind a dash, that is marginal at best and can be expected to reach
thermal shutdown in summer. Treat the figure as an estimate rather than a
measurement — the current draw is approximate and the Uno's thermal resistance
is not published — but it points the same way as the argument above, which does
not depend on any estimate.

## Mounting and vibration

Mount the **Uno only**, on 12 mm M3 nylon standoffs into the box's PCB bosses.
The shield rides on its headers.

> **Trap — a shield will walk off its stacking headers in a vehicle.** Not in a
> week, but over a season of road vibration, and it is intermittent before it is
> total, which is the worst kind of fault to diagnose at a campground. Put a
> block of closed-cell foam between the top of the stack and the lid so the
> shield is held down, or a nylon tie through the board. Either is a minute's
> work now and an afternoon later.

Strain-relieve every cable at its gland. The gland grips the jacket, not the
conductors, and a cable tugged at the connector rather than at the gland fails
at the solder joint.

## What changes if you move to the MAX7456

Nothing on this page, except one addition. The Video Experimenter passes video
through untouched when the Arduino is dead, which is why the signal chain above
has no bypass in it. The MAX7456 does not — its video buffer disable is a
tri-state, not a bypass — so a Stage 2 board needs a normally-closed relay, or
an analog video mux, routing camera to display unless the OSD holds it
energised. The 1554H has room for it. Read the Stage 2 notes in `CLAUDE.md`
before ordering anything.
