# Contract: Showcase Effect Classes + Demo/Docs (Phases 4–7)

These contracts fix the **public interfaces** the three classes expose. Per the
roadmap, each class is expected to get its own `/specify` → `/plan` → `/tasks`
cycle for the detailed per-effect work; the signatures and the universal
guarantees below are the binding part so the classes build consistently on the
Phase 3 foundation.

## Universal guarantees (every showcase effect)

- A `DisplayContent` (or `Transition`) usable from an app's content queue / loop.
- Runs **unchanged** on device and simulator (FR-027).
- **No per-frame heap allocation** on the hot path (FR-028).
- **No per-pixel Python loop over all 2048 pixels** — bounded work via the Phase 3
  painters/overlay/palette only (FR-029).
- **Async-only** (FR-031); cooperates with the 20 fps loop.
- Passes the strict feasibility gate at 20 fps:
  `run_headless(app, frames=120, hardware=True, strict=True).ok is True`
  with `advanced is True` and non-blank frames (FR-032). The gate is steady-state
  (median over a rolling window) + a transient ceiling, so an **isolated**
  legitimate glyph rebuild (visible-string change) is tolerated; **sustained**
  per-frame rebuilds or two-rebuilds-in-a-frame are not (D1).
- Ships feasibility metadata (§D).

---

## A. Class 1 — Characterful scrolling (`scrollkit/effects/scrolling.py`)

```python
class KineticMarquee(DisplayContent):
    def __init__(self, text, y=0, color=0xFFFFFF, speed=30,
                 pause_chars=".,!?;:", overshoot=True, priority=2): ...

class WaveRider(DisplayContent):
    def __init__(self, text, y=0, color=0xFFFFFF, speed=30,
                 amplitude=4, wavelength=16, priority=2): ...

class SplitFlap(DisplayContent):
    def __init__(self, text, y=0, color=0xFFFFFF, speed=30,
                 flip_steps=3, seed=1, priority=2): ...
```

Behavioral contract:

- `KineticMarquee`: accelerates in (eased), coasts, dwells `~N` frames at each
  `pause_chars` boundary/keyword, overshoots then springs off; only Label `.x`
  changes per frame.
- `WaveRider`: realizes only the **visible window** of single-char Labels;
  `y = baseline + wave_table[(x + phase) & 255]`; rebuild a char only when it
  enters the viewport.
- `SplitFlap`: each entering char flips through `flip_steps` (2–4) deterministic
  intermediate glyphs (seeded PRNG, no `random` per-frame alloc) before landing.

Tests: lit pixels advance; deterministic given `seed`; no per-frame alloc;
strict-feasible.

---

## B. Class 2 — Theatrical transitions (`scrollkit/effects/transitions.py`, fresh)

```python
class Transition:
    def __init__(self, duration_frames=12, curve=EASE_IN_OUT): ...
    async def start(self, display, swap_callback): ...  # swap_callback runs while covered
    async def render(self, display) -> None: ...        # advance one frame
    @property
    def is_complete(self) -> bool: ...

class IrisSnap(Transition): ...
class VenetianShutters(Transition): ...        # bands=8
class MosaicResolve(Transition): ...           # block_w=8, block_h=4
class CRTCollapse(Transition): ...
class LightSlitRewrite(Transition): ...        # slit_px=3
```

Behavioral contract:

- Each drives a shared `OverlayMask` cover → invoke `swap_callback` (swap content)
  while fully covered → reveal. The swap is invisible to the viewer (FR-020).
- **Covered-swap rule (D1)**: because `swap_callback` runs while the mask is fully
  covering, any Label glyph rebuild it triggers lands on a *covered* frame whose
  cost (rebuild + a few mask writes) stays under the transient ceiling and is
  absorbed by the median window — so a transition never false-trips the strict
  gate on the swap. This is the sanctioned place to put content swaps that rebuild.
- Per frame writes only a **bounded** set of mask spans/blocks (no full repaint).
- Invokable between content-queue items as the replacement for the removed
  wipe/slide (FR-021).

Tests: correct cover→swap→reveal ordering (assert content hidden at peak cover);
bounded writes; strict-feasible across the covered swap.

---

## C. Class 3 — Palette-animated bitmap text (`scrollkit/display/bitmap_text.py`)

```python
FONT_5x7  # table-driven glyph bitmasks; no BDF

class BitmapText(DisplayContent):
    def __init__(self, text, y=0, palette_effect=None, scroll_speed=30,
                 max_width_px=192, priority=2): ...

class NeonTubeCrawl:   # palette-effect strategies
class ChromeSheen: ...
class RainbowChase: ...
class HazardStripes: ...
```

Behavioral contract:

- `BitmapText` renders the message **once** into an indexed `gfx.Bitmap` (glyph
  pixels carry palette indices, bg = index 0) + `gfx.Palette` + `gfx.TileGrid`
  added via `display.add_layer`; scroll moves the TileGrid `.x` (no repaint,
  FR-023).
- A `palette_effect` rewrites a few `palette[i] = color` entries per frame to
  animate (neon crawl / chrome sheen / rainbow chase / hazard stripes) with **no
  glyph rebuild** and near-zero per-frame pixel work (FR-024).
- Option A only (whole message → one bitmap, documented `max_width_px`); ring-
  buffer viewport variant deferred.

Tests: palette rotation changes rendered output **without** glyph rebuild (assert
the bitmap object identity is stable across frames); TileGrid scroll moves text;
strict-feasible.

---

## D. Feasibility metadata + demo reel (Phase 7)

Each shipped showcase effect advertises:

```python
{
  "hardware_safe": True,            # passes strict gate at 20 fps
  "allocates_per_frame": False,     # MUST be False
  "max_pixel_writes_per_frame": int,
  "modeled_frame_ms": number,       # <= 50.0
}
```

surfaced in `docs/guide/*` (and, where natural, the `capabilities()` catalog).

Demo reel (`demos/hard/showcase.py` or `demos/showcase/`):

- A scripted `ScrollKitApp` chaining the signatures (e.g. CRT-collapse intro →
  neon title → kinetic marquee → iris snap → wave-rider → split-flap → mosaic
  exit), constructing its display with `strict=True`.
- Contract: `run_headless(ShowcaseApp(), frames=N, hardware=True, strict=True).ok
  is True` end to end; runs unchanged on device vs simulator (FR-025, SC-008).
