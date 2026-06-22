# Effects

`scrollkit.effects` adds visual polish: particle systems and colour animations —
all built to respect the device's memory and frame budget.

!!! note "The old transition effects were removed"
    The earlier `transitions`, `basic_transitions`, and `reveal` modules
    (fades/slides/wipes/reveal) were broken or fake — they looped over all 2048
    pixels in Python and only rendered placeholder content — and have been
    removed. Theatrical transitions are being rebuilt on the new overlay-mask
    primitive as part of the *ScrollKit Showcase Effects* work.

## EffectsEngine

`scrollkit.effects.effects.EffectsEngine` coordinates active effects. It caps the
number of concurrent effects (default 2) and uses pre-allocated colour tables to
avoid per-frame allocation on CircuitPython.

```python
from scrollkit.effects.effects import EffectsEngine

effects = EffectsEngine(display)
```

## What's available

| Module | Effects |
|--------|---------|
| `scrollkit.effects.effects` | `EffectsEngine`, colour helpers (`get_rainbow_color`), simple animations |
| `scrollkit.effects.particles` | particle systems (sparkles, rain, embers, snow) |
| `scrollkit.effects.base` | the `Effect` base class for writing your own |

Effects run with functionally equivalent behaviour on hardware and in the
simulator — same effect types and sequencing, though exact pixel timing differs.

!!! tip "Memory ladder"
    Effects are the first thing to disable on a memory-starved device. Keep the
    concurrent-effect cap low and prefer the lighter transitions when targeting
    the MatrixPortal S3.

## Showcase foundation primitives

The *ScrollKit Showcase Effects* work adds a small set of shared, zero-allocation
primitives that the new effects build on. Each runs **unchanged** on the device
and the simulator, and is budgeted against the calibrated MatrixPortal S3 model
(~20 fps / 50 ms per frame at `bit_depth=4`).

| Primitive | What it gives you | Hardware budget framing |
|-----------|-------------------|-------------------------|
| `scrollkit.effects.easing` | Integer easing/tween lookup tables (`ease`, `interp`) for 6 curves | Pure `bytes` lookups — no floats, no per-call allocation |
| `display.fill_rect` / `fill_span` / `clear_rect` | Bounded span/rect painters | C bulk ops (`bitmaptools.fill_region`) — never a full 2048-pixel Python loop |
| `display.measure_text(text)` | Real rendered text width (summed glyph advances) | Replaces the old `len(text) * 6` estimate; measured once, off the hot path |
| `display.gfx` + `add_layer` / `remove_layer` | Platform-resolved `Bitmap`/`Palette`/`TileGrid`/`bitmaptools`, plus a content/layer group split | Cached once per display; persistent effect layers keep a stable z-order across the per-frame clear |
| `scrollkit.effects.overlay.OverlayMask` | One preallocated indexed mask (transparent index 0) composited above content | Allocate once; transitions write only dirty spans |
| `scrollkit.effects.transitions.IrisSnap` | Diamond-aperture cover → swap → reveal transition | Bounded mask spans per frame; swaps content while fully covered |
| `scrollkit.display.bitmap_text.BitmapText` | A message rendered once into an indexed bitmap, scrolled via a TileGrid, with palette animation (`RainbowChase`) | Animation is a few palette writes per frame — near-zero per-frame pixel work, no glyph rebuild |

### Strict feasibility gate

Hardware simulation can run in **strict** mode: an effect whose modeled per-frame
cost busts the device budget raises `scrollkit.exceptions.FeasibilityError` instead
of only warning. The gate is steady-state (a rolling median holds ~20 fps) plus a
single-frame transient ceiling, so a legitimate one-off glyph rebuild is tolerated
while a *sustained* over-budget effect fails.

```python
from scrollkit.dev import run_headless

# strict=True implies hardware modeling; a busting effect -> result.ok is False
result = run_headless(MyApp(), frames=120, hardware=True, strict=True)
assert result.ok and result.advanced       # rendered, animated, within budget
print(result.hardware_text)                 # per-frame budget breakdown
```

Strict mode is opt-in (`strict=True`, or `SCROLLKIT_HW_STRICT=1`); it is a
desktop-simulator concept and a no-op on CircuitPython, where the device runs at
real speed.
