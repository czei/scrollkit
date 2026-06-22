# Contract: Foundational Primitives (Phase 3)

All primitives below are CircuitPython-safe and run one code path on both
platforms.

## A. Integer easing engine

```python
# scrollkit/effects/easing.py
LINEAR, EASE_OUT_QUAD, EASE_IN_OUT, OVERSHOOT, BOUNCE, ELASTIC  # curve ids

def ease(curve, progress_0_255) -> int:      # returns 0..255 from a precomputed LUT
def interp(curve, a, b, progress_0_255) -> int:  # a + ((b-a)*ease(curve,p))//255
```

Guarantees:

- Each curve is a length-256 immutable **`bytes`** object built **once** at import
  (module constants). `bytes`, not int tuples — 256 B/curve, six curves ≈ 1.5 KB
  static RAM (S5). No float math and no allocation on the hot path; `ease` returns
  a `bytes` element (an `int` 0..255).
- `ease(curve, 0) == 0`, `ease(curve, 255) == 255` for all curves (endpoints
  pinned); monotonic where the curve is monotonic. `OVERSHOOT`/`ELASTIC` overshoot
  is expressed by the consuming effect scaling past the endpoints (table storage is
  clamped to the 0..255 `bytes` range, documented).
- Importable on device (no `typing`, no numpy).

Contract test: `test/unit/effects/test_easing.py` — endpoints, length, `bytes`
type, integer return, determinism, no per-call allocation.

---

## B. Display painters + helpers (on `DisplayInterface`)

```python
# scrollkit/display/interface.py  (abstract; implemented in unified.py + simulator.py)
async def fill_rect(self, x, y, w, h, color) -> None
async def fill_span(self, y, x0, x1, color) -> None
async def clear_rect(self, x, y, w, h) -> None
def measure_text(self, text, font=None) -> int          # sync query
@property
def gfx(self):                                          # resolved graphics namespace
    """Exposes Bitmap, Palette, TileGrid, Group, bitmaptools for this platform."""
def add_layer(self, tilegrid) -> None
def remove_layer(self, tilegrid) -> None
```

Guarantees:

- `fill_rect`/`fill_span`/`clear_rect` write **only** inside the given (clipped)
  bounds and use a **bulk op** (`gfx.bitmaptools.fill_region` / `Bitmap.fill` on a
  subregion). Their bulk-op cost is accounted via
  `PerformanceManager.account_bulk_op(kind, clipped_px)` when the model is active.
- **No full-2048 Python loop, ever (S6)**: on the supported targets the bulk path
  is *always* available (device has `bitmaptools`; simulator has the shim), so the
  bulk op is always taken. The per-pixel "looped fallback" mentioned in FR-013 is a
  defensive last resort **only** for a *tiny* bounded region (≤ a small documented
  pixel cap) and is **forbidden** for full-width/full-screen regions — it must
  never become the forbidden 2048-pixel loop. A test asserts a 64×32 `clear_rect`
  takes the bulk path.
- `color` is 24-bit `0xRRGGBB`.
- **`gfx` is cached (S3)**: built **once** per display in `initialize()` and
  returned by the property with **no per-access allocation** —
  `display.gfx is display.gfx` MUST hold. It is a plain attribute-holding instance
  (not `types.SimpleNamespace`), carrying no runtime `typing`. It returns the
  **real** `displayio`/`bitmaptools` on CircuitPython and the `scrollkit.simulator`
  equivalents (incl. the shim) on desktop; same attribute names both places.
  Desktop-only imports (numpy, sim `bitmaptools`) are reached only via the
  simulator display, never at device import time (S4).
- **`measure_text` contract (S1/N3)**: returns the rendered pixel width by summing
  font glyph advances (`font.get_glyph(ch)` → `.dx`/`["dx"]`/`.shift_x`), not
  `len(text) * 6`; uses the panel default font when `font is None`. Empty string ⇒
  **0**. A missing/advance-less glyph contributes a **defined replacement advance**
  (the font's space advance, else a documented constant) — never a crash. It is a
  **sync query** intended to be called **once** (at content start), not per frame;
  the throwaway-Label fallback is permitted only when `get_glyph` is entirely
  unavailable and only at that one-time call — never on a render hot path.
- `add_layer(tg)` composites `tg` into the `_layer_group` (above all Label
  content — see §F); `remove_layer(tg)` removes it. Both idempotent (re-adding a
  present layer / removing an absent one are no-ops).

Contract test: `test/unit/display/test_painters.py` — bounded writes, clipping,
bulk path on a full-width rect, `measure_text` accuracy vs a rendered Label width
(plus empty/missing-glyph), `gfx` identity stability + attribute presence.

---

## C. Simulator `bitmaptools` shim (desktop only)

```python
# scrollkit/simulator/bitmaptools.py   (NEVER imported on CircuitPython)
def fill_region(bitmap, x1, y1, x2, y2, value) -> None
def blit(dest, source, x, y, *, x1=0, y1=0, x2=None, y2=None, skip_index=None) -> None
```

Guarantees:

- Operates on the numpy-backed `scrollkit.simulator.displayio.Bitmap`.
- Semantics match CircuitPython `bitmaptools` for the used subset: `fill_region`
  fills the **half-open** rectangle `[x1,x2) × [y1,y2)` (CP convention) with
  `value`, clipped to the bitmap; `blit` copies `source` into `dest` at `(x,y)`
  honoring the source sub-rectangle `[x1,x2)×[y1,y2)` and `skip_index`
  transparency, clipped at all four edges and at negative offsets; empty/fully
  clipped regions are no-ops (no raise).
- No behavioral divergence from the device is permitted; if found, the **shim** is
  corrected (never the shared effect logic).

**Conformance is verified, not asserted (B2)**: a **golden corpus** pins the shim
to real-device output.

- `test/claude/bitmaptools_golden.py` — host-side device tool (raw-REPL, writes
  nothing to the board) that runs a fixed battery of `fill_region`/`blit` ops on
  real CircuitPython and dumps the resulting bitmaps to
  `test/unit/display/bitmaptools_golden.json`.
- `test/unit/display/test_bitmaptools_shim.py` — replays the **same** battery
  through the shim and asserts **byte-identical** output against the golden file.
- The battery MUST exercise the risky cases: edge clipping, negative source
  offsets, `skip_index` transparency, zero-area regions, and full-bitmap fills.
- Until a board is available, ship a once-captured golden file and treat its
  recapture as a calibration step (same model as `matrixportal_s3_baseline.json`).
  This is a tracked residual risk (see research Open risks).

## F. Layer ownership & z-order (D11 — `add_layer` vs per-frame `clear()`)

The display restructures `main_group` into two child groups so persistent effect
layers keep a stable z-order across the per-frame label-pool reset:

```
main_group
├── _content_group   # BELOW — Labels + fill() background; owned by the label pool
└── _layer_group     # ABOVE — overlay-mask + bitmap-text TileGrids; owned by add_layer
```

Guarantees:

- `_content_group` always renders **below** `_layer_group`, so content can never
  appear above an effect layer regardless of label-pool growth.
- The Label pool and `fill()` operate **only** on `_content_group`; `fill()`'s
  background goes to `_content_group[0]`.
- `clear()` resets the label-pool index in `_content_group` and **never touches
  `_layer_group`** — added layers persist across frames by design.
- `add_layer(tg)` appends to `_layer_group` (insertion order = z-order);
  `remove_layer(tg)` removes it; both idempotent. Layer owners (`OverlayMask`,
  `BitmapText`) call `detach()` when done.
- Implemented **identically** in `UnifiedDisplay` and `SimulatorDisplay`.

Contract test: `test/unit/display/test_layers.py` — a layer added via `add_layer`
survives N `clear()` calls and stays above Labels even after the pool grows;
`add_layer`/`remove_layer` idempotency.

---

## D. `OverlayMask`

```python
# scrollkit/effects/overlay.py
class OverlayMask:
    def __init__(self, display, value_count=4): ...   # allocates ONCE
    async def fill_rect(self, x, y, w, h, index): ...
    async def fill_span(self, y, x0, x1, index): ...
    async def clear(self): ...
    async def clear_rect(self, x, y, w, h): ...
    async def blit_pattern(self, x, y, pattern_bitmap, *, skip_index=0): ...
    def set_cover_color(self, index, color): ...       # palette[index] = color
    def detach(self): ...                              # remove_layer + drop refs
```

Guarantees:

- Allocates exactly one `gfx.Bitmap` + one `gfx.Palette` (index 0 transparent) +
  one `gfx.TileGrid` (added via `display.add_layer`) at construction; **no further
  allocation** across its lifetime.
- All mutators touch only dirty spans via `gfx.bitmaptools`.
- Index 0 = transparent (underlying content shows through); indices 1..N = opaque
  cover colors.
- Reusable across transitions (`clear()` resets to transparent).

Contract test: `test/unit/effects/test_overlay.py` — single allocation (object
identity of bitmap/palette stable across many mutations), transparency, bounded
writes, strict-feasible.

---

## E. Fixed-point `ScrollingText`

```python
# scrollkit/display/content.py
LOOP_FPS = 20
class ScrollingText(DisplayContent):
    def __init__(self, text, x=None, y=0, color=0xFFFFFF, speed=30, priority=2): ...
```

Guarantees (changed behavior; signature stable):

- Position is a 1/16-px fixed-point accumulator; rendered `x = pos_q >> 4`.
- `speed` (px/sec) drives motion: per frame `pos_q -= round(speed*16/LOOP_FPS)`.
  Speed N advances ~N× faster than speed 1 (SC-007).
- Scroll extent uses `display.measure_text(text)`, **not** `len(text)*6`; measured
  **once** at `start()`/first render, cached in `_measured_width`, never per frame;
  completion when `(pos_q >> 4) < -measured_width`.
- Only a reused Label's `.x` changes per frame (no glyph rebuild unless the
  visible string changes — and such a rebuild is an isolated spike the strict
  gate's median window tolerates, D1).
- `describe()` still returns `speed`, `position`, `text_width` (now meaningful).

Contract test: `test/unit/display/test_scrolling_text.py` — position after K
frames scales with `speed`; measured width matches a rendered Label's width;
no per-frame allocation; completes when fully scrolled off.
