# Effects

`scrollkit.effects` adds visual polish: particle systems and colour animations —
all built to respect the device's memory and frame budget.

!!! note "The old transition effects were removed and replaced"
    The earlier `transitions`, `basic_transitions`, and `reveal` modules
    (fades/slides/wipes/reveal) were broken or fake — they looped over all 2048
    pixels in Python and only rendered placeholder content — and have been
    removed. Their replacements are the *ScrollKit Showcase* effect classes,
    built on the zero-allocation overlay-mask/painter/easing primitives:

    - **[Characterful scrolling](scrolling.md)** — kinetic marquee, wave-rider, split-flap
    - **[Theatrical transitions](transitions.md)** — iris, venetian, mosaic, CRT, light-slit
    - **[Palette-animated bitmap text](bitmap-text.md)** — rainbow, neon, chrome, hazard

    See `demos/hard/showcase.py` for a reel that announces and demonstrates every
    one of them.

## One effect contract, plus standalone helpers

After the effects consolidation there is **one** content-swap contract —
`scrollkit.effects.transitions.Transition` (see
[Theatrical transitions](transitions.md)) — plus standalone splash and particle
helpers. The old `Effect` / `EffectRegistry`, `SimpleEffect` / `EffectsEngine`, and
`EnhancedDisplayContent` systems were **removed**: they overlapped, were unused, and
the enhanced-content family even looped over all 2048 pixels in Python — the exact
anti-pattern the feasibility gate forbids. There is intentionally no shared
per-frame "effect" base class to inherit from.

To add your own effect, write a `Transition`: see
**[Adding your own transition](transitions.md#adding-your-own-transition)** and the
heavily-annotated reference in `demos/medium/golden_transition.py`.

## What's available

| Module | What it gives you |
|--------|-------------------|
| `scrollkit.effects.transitions` | content-swap transitions on the `Transition` base ([guide](transitions.md)) |
| `scrollkit.effects.scrolling` | characterful scrolling text ([guide](scrolling.md)) |
| `scrollkit.display.bitmap_text` | palette-animated bitmap text ([guide](bitmap-text.md)) |
| `scrollkit.effects.particles` | standalone particle systems (sparkles, rain, embers, snow) |
| `scrollkit.effects` splash helpers | `show_reveal_splash`, `show_drip_splash`, `show_swarm_splash` |

Effects run with functionally equivalent behaviour on hardware and in the
simulator — same effect types and sequencing, though exact pixel timing differs.

## Pairing effects to content

Some effects read best on **static** (held) text, some on **scrolling** text, and
the transitions are **full-screen** swaps between content. Each effect class carries
a `PAIRS_WITH` tag (`"static"` / `"scrolling"` / `"fullscreen"`) that
`scrollkit.dev.capabilities()` surfaces as `pairs_with` (and `as_text()` prints as
`[best on: …]`), so app authors and AI agents can pick the right effect for the
content.

| Best on | Effects |
|---------|---------|
| **Scrolling** text | `KineticMarquee`, `WaveRider` — Class 1, they *are* the scroll |
| **Static** / held text | `SplitFlap` (flips in place); the `Drop from Sky` transition (drops text into place) |
| **Either** static or scrolling | the `BitmapText` palette effects: `RainbowChase`, `NeonTubeCrawl`, `ChromeSheen`, `HazardStripes` |
| **Full screen** (swap between content) | every `Transition`: `IrisSnap`, `VenetianShutters`, `MosaicResolve`, `CRTCollapse`, `LightSlitRewrite`, `PixelDissolve`, `ColumnRain`, `GradualReveal`, `ScanFold`, `GlitchBars`, `DiagonalWipe` — plus `HorizontalWipe`, which also suits fast-**scrolling** text |

The tag is guidance, not a constraint — nothing stops you using an effect
elsewhere; it just records what looks good.

!!! tip "Memory ladder"
    Effects are the first thing to disable on a memory-starved device. Prefer the
    lighter transitions and keep splash/particle counts low when targeting the
    MatrixPortal S3.

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
| `scrollkit.effects.scrolling` | [Characterful scrolling](scrolling.md): `KineticMarquee`, `WaveRider`, `SplitFlap` | One / a few small Labels repositioned per frame; bounded rebuilds |
| `scrollkit.effects.transitions` | [Theatrical transitions](transitions.md): `IrisSnap`, `VenetianShutters`, `MosaicResolve`, `CRTCollapse`, `LightSlitRewrite` | Bounded mask spans per frame; swaps content while fully covered |
| `scrollkit.display.bitmap_text` | [Palette-animated bitmap text](bitmap-text.md): `BitmapText` + `RainbowChase`/`NeonTubeCrawl`/`ChromeSheen`/`HazardStripes` | Animation is a few palette writes per frame — zero per-frame pixel work, no glyph rebuild |

Every showcase effect carries an advertised `FEASIBILITY` dict (`hardware_safe`,
`allocates_per_frame`, `max_pixel_writes_per_frame`, `modeled_frame_ms`); see the
per-class pages above.

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
