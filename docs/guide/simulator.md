# Simulator

`scrollkit.simulator` is a desktop emulation of the CircuitPython display stack.
It is what lets you develop, test, and demo ScrollKit apps with no hardware.

## What it emulates

- **`displayio`** — `Bitmap`, `Palette`, `TileGrid`, `Group`, `Display`,
  `FourWire`, `OnDiskBitmap`.
- **`adafruit_display_text`** — `Label`, `BitmapLabel`, `ScrollingLabel`.
- **`adafruit_bitmap_font`** — BDF font loading (the same `.bdf` fonts the
  hardware uses).
- **`terminalio`** — the built-in terminal font.
- **Devices** — `MatrixPortalS3` and a generic matrix.

A pygame window renders the virtual LED matrix pixel-for-pixel, so what you see
on screen matches what the panel shows.

```python
from scrollkit.display.simulator import SimulatorDisplay

display = SimulatorDisplay(width=64, height=32)
await display.create_window("My ScrollKit App")
```

## Why it matters

Because the simulator emulates the CircuitPython APIs, **your application code is
identical** on desktop and device. `UnifiedDisplay` picks the simulator on
desktop and the real `displayio` backend on CircuitPython — you never write
platform branches.

!!! note "Keep them in sync"
    If the simulator ever diverges from real hardware behaviour, fix the
    *simulator*, not the shared display code — the device is the source of truth.

## Screenshots

`SimulatorDisplay.screenshot(path)` saves the current frame to an image file —
handy for documentation, bug reports, and visual tests:

```python
await display.show()
display.screenshot("frame.png")   # returns the path, or None on hardware
```

It captures whatever is currently on the simulated matrix. On real hardware
(no pygame) it returns `None`, so the same call is safe to leave in cross-platform
code.

Requires `pygame` on desktop: `pip install pygame`.

## Fonts: BDF vs PCF

ScrollKit ships and uses **BDF** fonts (under `scrollkit/simulator/fonts/`), and
the simulator + hardware both load them with the same
`bitmap_font.load_font(path)` API. BDF is plain-text and easy to work with, which
is why it's the default.

On a memory-constrained device, **PCF** is the more efficient choice for larger
fonts:

| | BDF | PCF |
|--|-----|-----|
| Format | text | binary |
| Load cost | parses the whole font into RAM | glyphs read from flash on demand |
| Best for | small fonts, the simulator, development | large fonts on the MatrixPortal S3 |

Both load through the identical API, so switching is a one-line change:

```python
font = bitmap_font.load_font("/fonts/MyFont.pcf")   # instead of .bdf
```

Convert a BDF to PCF on a desktop with `bdftopcf` (part of the X11 font utils):

```bash
bdftopcf MyFont.bdf -o MyFont.pcf
```

Recommendation: keep BDF as the default (it works everywhere and the simulator
is not RAM-constrained); convert to PCF only the specific large fonts you load on
hardware, where the RAM saving matters. BDF parity is preserved either way — the
same fonts remain available as `.bdf`.
