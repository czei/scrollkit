# Sensors: Tilt & Orientation

Everything else in ScrollKit is output. This is the one part that reads the
physical world back in: the Adafruit MatrixPortal S3 carries an onboard **LIS3DH**
accelerometer, so a sign built on one knows which way is down — and can do
something about it.

```python
from scrollkit.sensors.tilt import TiltSensor

tilt = TiltSensor(display)
if tilt.available and tilt.orientation != "bottom":
    print("someone has turned the sign on its side")
```

That same code runs on the desktop, where the simulator supplies a **virtual**
gravity vector you steer with the arrow keys. You develop against the identical
API you ship.

---

## The address gotcha

!!! danger "The S3's LIS3DH lives at 0x19, not 0x18"
    Adafruit's own CircuitPython libraries default to I2C address **0x18**. On the
    MatrixPortal S3 the accelerometer answers at **0x19**. Adafruit
    [documents this explicitly](https://learn.adafruit.com/adafruit-matrixportal-s3/pinouts),
    and getting it wrong does not raise anything useful — it simply finds nothing,
    which is indistinguishable from "this board has no accelerometer".

ScrollKit keeps the address in the board registry
(`src/scrollkit/display/boards.py`), not in the driver, so it is declared once per
board alongside everything else that varies between them.

## Panel coordinates, not chip coordinates

Everything `TiltSensor` reports is in **panel** space: `+X` toward the panel's
right edge, `+Y` toward its bottom edge (the displayio convention, where `y` grows
downward). You never have to think about how the chip is soldered on.

| Property | What it gives you |
|----------|-------------------|
| `available` | `True` if a real or simulated accelerometer is answering |
| `read()` | Smoothed `(x, y, z)` acceleration in g |
| `gravity_angle` | Degrees clockwise from "bottom edge down", `[0, 360)` |
| `orientation` | Which edge is down: `"bottom"`, `"right"`, `"top"`, `"left"`, or `"flat"` |
| `magnitude` | Strength of in-plane gravity — ~1.0 hanging, ~0.0 lying flat |
| `is_flat` | `True` when the panel is face up or down |
| `describe()` | A JSON-able snapshot of all of the above |

`gravity_angle` is the continuous one — use it when you want a response that
varies smoothly with angle. `orientation` is the snapped one, for deciding *which
way* something should happen.

```python
tilt = TiltSensor(display)

tilt.orientation      # 'bottom'  — hanging normally
tilt.gravity_angle    # 0.0
# ... stand the box on its right-hand end ...
tilt.orientation      # 'right'
tilt.gravity_angle    # 90.0
```

### It never raises

A board with no accelerometer (the Pimoroni Interstate 75 W), a busy I2C bus, a
desktop run with no display attached — all of them give you `available == False`,
`orientation == "flat"`, and a `read()` of `(0.0, 0.0, 1.0)`. Write the interesting
path and let the boring one degrade:

```python
edge = tilt.orientation if tilt.available else "bottom"
```

A single dropped I2C transaction is swallowed too, keeping the last good vector —
one flaky read must not blank an effect mid-animation.

### Hysteresis, because signs wobble

A sign resting near a 45° diagonal would otherwise flip between two orientation
names every frame, and anything keyed to it would thrash. `orientation` only
changes once the angle is past the boundary by the `hysteresis` margin (8° by
default), so it commits to an answer and stays there.

### Reads are throttled

The display loop runs at ~20 fps and I2C is not free while the panel is being
driven. `read()` does real bus work at most every `min_interval` seconds (0.1 s by
default — far quicker than anyone can turn a sign) and returns the cached vector in
between, so calling it every frame costs essentially nothing. `read(force=True)`
bypasses the throttle.

---

## Tilting a laptop

You can't. So the simulator carries a virtual accelerometer instead, and
`TiltSensor` reads it automatically when there's no real chip:

| Key | Effect |
|-----|--------|
| ++left++ / ++right++ | Swing gravity 15° |
| ++down++ | Snap back upright |
| ++up++ | Lay the panel flat on its back |

For tests and headless runs, set it exactly:

```python
display.set_virtual_tilt(angle=90)     # right edge down
display.set_virtual_tilt(flat=True)    # lying face up
```

Because the simulated and real sensors expose the same class, a tilt-driven app is
written, debugged and regression-tested on the desktop before it ever reaches a
board.

---

## Making something happen: `GravityDripAnimator`

The payoff effect. Whatever is on screen lets go and pours toward whichever edge is
now the floor — turn the box mid-fall and the pile changes direction with you. It's
an [image animator](effects.md#image-animators), following the usual
start/step/detach contract:

```python
from scrollkit.effects.image_animators import GravityDripAnimator

drip = GravityDripAnimator(edge=tilt.orientation)
drip.start(display, tile, bitmap, palette, base_colors)
for frame in range(drip.HOLD_FRAMES):
    drip.set_gravity(edge=tilt.orientation)     # follow the box, live
    drip.step(frame)
    await display.show()
    if drip.is_complete:
        break
drip.detach()
```

`set_gravity()` also accepts a continuous `angle=` (snapped to the nearest edge)
and a `speed=`, so you can drive the fall rate from `tilt.magnitude` and have things
tumble more slowly as the box comes back to level.

The runnable version is `demos/medium/tilt_drip.py`:

```bash
PYTHONPATH=src python demos/medium/tilt_drip.py
```

### What it can and can't melt

The animator needs the lit pixels of what's on screen, and **`displayio` cannot be
read back on hardware** — there is no way to ask the panel what it is showing. So
it works from an indexed `Bitmap` the library already owns: a
[`BitmapText`](bitmap-text.md) banner, or an image `TileGrid`. Plain `StaticText`
labels have no readable bitmap behind them; convert them to `BitmapText` if you
want them to melt.

The lifted pixels move onto a **full-panel overlay** and the source is blanked, so a
7-row `BitmapText` strip still falls all the way to the panel floor rather than
piling up inside its own strip.

### Budget

`start()` refuses (raises `ValueError`) past `max_pixels` — 400 by default — so an
over-dense image falls back to the still frame instead of blowing the frame budget.
Per frame it touches only the pixels that actually moved: one write for the new
cell, one erase for the vacated one. 400 lit pixels is ~800 writes ≈ 5.6 ms at the
device-measured ~7 µs/write, well inside the 50 ms (20 fps) budget — and it drops to
zero as the pile settles.

---

## Verifying on real hardware

The simulator has no I2C bus, so the address, the register writes, the burst read,
and above all **which way the chip's axes actually point** can only be confirmed
with a board on the end of a cable:

```bash
make copy-to-circuitpy
PYTHONPATH=src python test/claude/tilt_probe_s3.py --port /dev/cu.usbmodemXXXX
PYTHONPATH=src python test/claude/tilt_probe_s3.py --port /dev/cu.usbmodemXXXX --watch 30
```

The probe writes nothing to the board. `--watch` streams live readings while you
physically turn it — check that `orientation` names the edge actually facing the
floor. If it's consistently rotated or mirrored, fix `AXIS_MAP` in
`src/scrollkit/sensors/tilt.py`. That single constant is the only place the
chip-to-panel mounting is encoded, and every angle, orientation and tilt-driven
effect follows from it.

## Which boards have what

Ask the library rather than hard-coding it, so a future board flows through
automatically:

```python
from scrollkit.dev import capabilities
capabilities()["sensors"]["by_board"]
# {'adafruit_matrixportal_s3': {'tilt': True},
#  'pimoroni_interstate75_w': {'tilt': False}}
```
