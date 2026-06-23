# Theatrical Transitions (Class 2)

`scrollkit.effects.transitions` provides cinematic transitions between messages,
built on the preallocated `OverlayMask`. Every transition follows the same
**cover → swap-while-hidden → reveal** sequence: the old content is covered, the
`swap_callback` runs while the screen is fully hidden (so any glyph rebuild it
triggers lands on a covered frame), then the new content is revealed. They are the
proper replacement for the removed wipe/slide effects.

Each writes only a **bounded** set of mask spans/blocks per frame through the C
bulk painter (`bitmaptools.fill_region`) — never a full-2048-pixel Python loop —
with no per-frame allocation, and is strict-feasible at 20 fps.

```python
from scrollkit.effects.transitions import (
    IrisSnap, VenetianShutters, MosaicResolve, CRTCollapse, LightSlitRewrite,
)

t = IrisSnap(duration_frames=8, cover_color=0x101840)
await t.start(display, swap_callback)     # swap_callback runs while fully covered
# then each frame:
await t.render(display)
if t.is_complete:
    ...
```

## The pack

| Transition | Motion |
|------------|--------|
| `IrisSnap` | A chunky diamond aperture grows to hide the screen, then a diamond hole opens to reveal it (per-row span table). |
| `VenetianShutters` | Coarse horizontal bands (default 8) close then open like blinds, slightly staggered. |
| `MosaicResolve` | Blocks (default 8×4) cover then reveal in a fixed pseudo-random order — only the newly-changed blocks are written each frame. Deterministic given `seed`. |
| `CRTCollapse` | A CRT power-off: the picture collapses to a center scanline, then blooms back open from that line. |
| `LightSlitRewrite` | A bright vertical scanner (default 3 px) sweeps across, covering on the way out and revealing the new content on the way back. |

## Using a transition between content items

`swap_callback` is the sanctioned place to swap content — it fires while the mask
fully covers the screen, so a Label rebuilt there is invisible and its cost is
absorbed by the strict gate's median window:

```python
def swap():
    self.label = next_message()   # rebuilds a Label, but it's hidden

await t.start(display, swap)
```

## Hardware budget

Each class exposes a `FEASIBILITY` dict. A full-screen cover on the 64×32 panel is
2048 px done as **one** bulk `fill_region` (~0.6 ms), not a loop.

| Effect | `max_pixel_writes_per_frame` | `modeled_frame_ms` |
|--------|------------------------------|--------------------|
| `IrisSnap` | 2048 (bulk) | ~7 |
| `VenetianShutters` | 2048 (bulk) | ~8 |
| `MosaicResolve` | ~512 (a dozen blocks) | ~6 |
| `CRTCollapse` | 2048 (bulk) | ~8 |
| `LightSlitRewrite` | 2048 (bulk) | ~8 |

All are `hardware_safe = True`, `allocates_per_frame = False`, and stay well under
the ~50 ms (20 fps) `bit_depth=4` device budget.
