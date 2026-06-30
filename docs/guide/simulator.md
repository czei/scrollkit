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

## Recording animated GIFs

`screenshot()`'s sibling captures *many* frames and encodes an animated GIF —
ideal for a README, a docs preview, or a bug report. Turn recording on, run the
animation, then save:

```python
display.start_recording()
for _ in range(80):
    await content.render(display)
    await display.show()          # each shown frame is captured
display.save_gif("demo.gif")      # encodes + returns the path (None on hardware)
```

`save_gif(path, *, fps=20, target_width=360, max_colors=48, frame_step=1, ...)`
downscales to `target_width`, shares one adaptive palette across frames, and only
stores each frame's changed region, so files stay small. Raise `frame_step` (keep
only every Nth frame) for an even smaller file; raise the display's `pitch` (e.g.
`SimulatorDisplay(pitch=4)`) for crisper recordings.

To capture a whole `ScrollKitApp` headlessly there's a one-call helper:

```python
from scrollkit.dev import record_gif

record_gif(MyApp(), "demo.gif", seconds=4)   # target_width=, max_colors=, ... forwarded
```

This is exactly how the [Demo Gallery](../demos.md) previews are generated
(`demos/render_gifs.py`). Like `screenshot()`, recording is desktop-only and a
no-op on hardware.

## Recording MP4 video

For full-colour animation an MP4 is far smaller and smoother than a GIF (no
256-colour palette, real inter-frame compression), so it's the right format for a
site hero or a long clip. The recording flow is identical — just save with
`save_video` instead of `save_gif`:

```python
display.start_recording()
for _ in range(120):
    await content.render(display)
    await display.show()
display.save_video("hero.mp4")    # H.264 MP4; returns the path, or None on hardware
```

`save_video(path, *, fps=24, target_width=None, crf=20, preset="medium", border=0,
border_color=(10, 10, 13))` pipes the recorded frames straight to **`ffmpeg`**.
`target_width` optionally downscales (`None` keeps native size); `crf` trades size
for quality (≈18 best … 24 smaller; 20 is a good default); `border` adds a dark
bezel of that many pixels on every side, like a real sign's frame.

The whole-app one-call helper mirrors `record_gif`:

```python
from scrollkit.dev import record_video

record_video(MyApp(), "hero.mp4", seconds=6, border=22)   # crf=, target_width=, ... forwarded
```

This is how the landing-page hero is generated (`demos/render_hero.py`, run via
`make hero`). MP4 recording needs the **`ffmpeg`** binary on your PATH
(`brew install ffmpeg`); without it `save_video` returns `None`. Like every
recording call, it's desktop-only and a no-op on hardware.

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
