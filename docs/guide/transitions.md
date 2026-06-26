# Theatrical Transitions (Class 2)

`scrollkit.effects.transitions` provides cinematic transitions between messages,
built on the preallocated `OverlayMask`. Every transition follows the same
**cover → swap-while-hidden → reveal** sequence: the old content is covered, the
`swap_callback` runs while the screen is fully hidden (so any glyph rebuild it
triggers lands on a covered frame), then the new content is revealed. They are the
proper replacement for the removed wipe/slide effects.

!!! info "Full-screen swaps"
    Transitions cover the whole screen between content items, so they **all** pair
    with any content (`PAIRS_WITH = ("fullscreen",)`) — static or scrolling alike.
    The static-vs-scrolling distinction lives on the content effects that render the
    text (the scrollers and the bitmap-text palette effects), not on transitions.
    See [pairing effects to content](effects.md#pairing-effects-to-content).

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

## Adding your own transition

Subclass `Transition` and implement two methods — the base class runs the
cover → swap → reveal lifecycle for you. The full, heavily-annotated reference is
**`demos/medium/golden_transition.py`** (`GoldenWipe`); copy it. The rules:

1. Implement `_paint_cover(progress)` and `_paint_reveal(progress)`, where
   `progress` is an eased `0..255` through each phase. Paint into `self._mask` (an
   `OverlayMask`) with `fill_rect` / `clear_rect` — **bounded, bulk** writes only.
   No per-pixel Python loop over the panel; no per-frame allocation.
2. Override `start(display, swap_callback)` to capture `display.width/height`, then
   `await super().start(...)`.
3. Declare a `FEASIBILITY` dict on the **class** (CircuitPython can't attach
   attributes to functions).

Then **prove it** — the safety gate is the headless feasibility harness, not a
runtime sandbox:

```python
from scrollkit.dev import run_headless
result = run_headless(my_app, frames=120, strict=True)
assert result.ok and not result.errors   # raises FeasibilityError if over budget
```

To make it a **selectable built-in** (offered in the `transition_style` setting):

1. Add the class to `_TRANSITION_MAP` in `scrollkit/effects/transitions.py`.
2. Add its user-facing name to `TRANSITION_NAMES` in
   `scrollkit/config/transition_names.py`, in the same position.

These two lists are the single source of truth for transitions; a unit test
(`test_transition_registry.py`) fails if they drift, so a selectable name can never
silently fail to dispatch, and importing the settings never drags the effects
package onto the device boot path. To use a custom transition **without** making it
a built-in, override `_get_transition()` on your app to return an instance (see the
golden demo).
