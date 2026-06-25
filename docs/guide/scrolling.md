# Characterful Scrolling (Class 1)

`scrollkit.effects.scrolling` provides scrolling content that feels alive instead
of a constant 1 px/frame crawl. All three are async `DisplayContent`, run
**unchanged** on the MatrixPortal S3 and the simulator, do **no per-frame heap
allocation**, and pass the strict feasibility gate at 20 fps. Motion is driven by
a fixed-point (1/16-px) accumulator and the [integer easing tables](effects.md),
and text extent comes from `display.measure_text` (never `len(text) * 6`).

!!! info "Best on scrolling text"
    `KineticMarquee` and `WaveRider` *are* scrolling presentations
    (`PAIRS_WITH = ("scrolling",)`); `SplitFlap` flips characters in place, so it
    reads as held **static** text (`PAIRS_WITH = ("static",)`). See
    [pairing effects to content](effects.md#pairing-effects-to-content).

```python
from scrollkit.effects.scrolling import KineticMarquee, WaveRider, SplitFlap
```

## KineticMarquee

Scrolling text with mass: it eases in, dwells when a `pause_chars` character is
centered, overshoots and springs back at each dwell, then scrolls off. The whole
message is one reused `Label` whose `.x` moves per frame — the glyph bitmap is
built once.

```python
KineticMarquee("SCROLLKIT IN MOTION.", y=12, speed=34,
               pause_chars=".,!?;:", overshoot=True)
```

## WaveRider

Characters ride a precomputed integer sine path as the message scrolls; only the
**visible window** of single-char Labels is realized each frame
(`y = baseline + wave_table[(x // step + phase) & 255]`).

```python
WaveRider("RIDING THE WAVE", y=14, speed=30, amplitude=5, wavelength=16)
```

## SplitFlap

A split-flap board: each cell flips through `flip_steps` (2–4) **deterministic**
intermediate glyphs (a seeded LCG — no per-frame `random` allocation) before
landing on its real character, staggered left-to-right.

```python
SplitFlap("SPLIT FLAP", y=12, speed=30, flip_steps=3, seed=4)
```

## Hardware budget

Each class exposes a `FEASIBILITY` dict (`hardware_safe`, `allocates_per_frame`,
`max_pixel_writes_per_frame`, `modeled_frame_ms`). All three are strict-feasible
at the ~50 ms (20 fps) `bit_depth=4` device budget.

| Effect | Per-frame work | `max_pixel_writes_per_frame` | `modeled_frame_ms` |
|--------|----------------|------------------------------|--------------------|
| `KineticMarquee` | one Label, `.x` only (built once) | 0 (no painter writes) | ~6 |
| `WaveRider` | only the visible-window chars; rebuilds as chars cross the edge | 0 (no painter writes) | ~16 |
| `SplitFlap` | a few cells rebuild while flipping, then stop | 0 (no painter writes) | ~18 |

`max_pixel_writes_per_frame` is 0 because these effects move/restyle Labels rather
than painting pixels; their cost is the (bounded) glyph rebuilds the strict gate's
median window tolerates.
