# Phase 1 Data Model: ScrollKit Showcase Effects

"Entities" here are the runtime objects, value tables, and metadata the feature
introduces or changes. ScrollKit has no database; state lives in display objects,
preallocated bitmaps/palettes, and integer lookup tables. Field types are written
in CircuitPython-safe terms (no runtime `typing`).

> Revised after the `after_plan` PAL review — see `research.md` D1/D5/D6/D8/D11
> and the **Open risks** table.

---

## 1. FeasibilityError (exception)

- **Module**: `src/scrollkit/exceptions.py`
- **Definition**: `class FeasibilityError(SLDKError)` — base of the existing
  `SLDKError` hierarchy.
- **Carried data**: human-readable message including frame index, the window
  median ms / implied fps (steady-state breach) or single-frame ms (transient/RAM
  breach), the relevant budget, and the dominant `FrameCost` component (time) or
  modeled peak vs `usable_ram_bytes` (RAM).
- **Raised by**: `PerformanceManager._end_frame()` **only** — which only ever runs
  in the **desktop simulator** (the timing model is a no-op on CircuitPython).
  So `FeasibilityError` is never raised on real hardware.
- **Caught by**: `run_headless` frame loop (→ `RunResult.errors`, tagged
  `feasibility:`); app `_display_process` (logged). Tests import it directly.

---

## 2. PerformanceManager — new state (strict gate, D1)

- **Module**: `src/scrollkit/simulator/core/performance_manager.py`
- **New constructor params** (added to the existing signature, all defaulted so
  current callers are unaffected):
  - `strict: bool = False` — enable the gate.
  - `target_fps: float = 20.0` — steady-state feasibility target.
  - `warmup_frames: int = 2` — leading frames exempt from all gates (one-time
    scene/Label/bitmap construction).
  - `gate_window: int = 8` — rolling window for the steady-state median.
  - `transient_factor: float = 2.0` — single-frame ceiling multiplier.
- **Derived fields**:
  - `frame_budget_us = 1_000_000 / target_fps` (= 50 000 at 20 fps).
  - `transient_budget_us = frame_budget_us * transient_factor` (= 100 000;
    ~10 fps single-frame floor).
- **New `FrameCost` slot**: `bulk_ops_us` (added to `__slots__`, `total_us`, and
  `as_dict()`), so painter/overlay bulk work is part of the per-frame total.
- **New hook**: `account_bulk_op(kind, px)` — adds
  `bulk_base_us + px × slope_us(kind)` to `self._frame.bulk_ops_us`, where `px` is
  the **clipped** region pixel count actually scanned (a fully-clipped call costs
  only `bulk_base_us`). Costs sourced from the profile (D6) so they stay
  calibrated.
- **Enforcement** (in `_end_frame()`, after `total_us` is known, before reset),
  only when `strict` and `_frame_index >= warmup_frames`:
  1. **Transient ceiling**: `if total_us > transient_budget_us: raise` (catastrophe
     guard — e.g. two full rebuilds / a runaway loop).
  2. **Steady-state**: once the last `gate_window` frame totals are available,
     `if median(window) > frame_budget_us: raise` (sustained over-budget; an
     isolated rebuild spike is absorbed by the median).
  3. **RAM**: `if estimated_peak_ram_bytes() > profile.usable_ram_bytes: raise`.
- **Invariants preserved** (when `strict=False`): warning path, rate-limiting,
  `last_warning`, no-sleep-unless-throttle, and "one show() == one frame" all
  unchanged. The median computation lives in the desktop perf model only (not a
  device hot path), so the no-per-frame-alloc rule does not constrain it.

**State transition (per frame)**: `accumulate
(pixel_writes/refresh/rebuild/gc/bulk_ops) → _end_frame → [strict & past warmup:
transient? steady-state median? RAM?] → raise | append frame & reset`.

---

## 3. HardwareProfile — bulk-cost fields (D6)

- **Module**: `src/scrollkit/simulator/core/hardware_profile.py`
- **New fields** (defaulted from the benchmark table; back-compat preserved):
  - `bulk_base_us: float = 12.0` — fixed per-call C-dispatch overhead
    (conservative; over-counts slightly so the gate fails safe).
  - `fill_region_us_per_px: float = 0.287` — from `bitmaptools_fill_region`
    (147 049 ns / 512 px).
  - `blit_us_per_px: float = 0.623` — from `bitmaptools_blit_16x16`
    (159 462 ns / 256 px).
- **Calibration TODO**: capture `fill_region`/`blit` at 2–3 sizes in
  `device_benchmarks.py` to *fit* base+slope rather than estimate base.
- **Unchanged**: `usable_ram_bytes`, `full_refresh_us`, `bitmap_rebuild_us_per_px`,
  `confidence`, etc.

---

## 4. Easing engine (value tables, S5)

- **Module**: `src/scrollkit/effects/easing.py`
- **Entities**: named **integer lookup tables**, one per curve, each a length-256
  immutable **`bytes`** object mapping `progress 0..255 → eased 0..255`. `bytes`
  (256 B each; six curves ≈ **1 536 B** static) rather than int tuples to bound CP
  RAM (S5). Built **once** at import; no floats on the hot path.
- **Curves (≥6)**: `LINEAR`, `EASE_OUT_QUAD`, `EASE_IN_OUT`, `OVERSHOOT` (back),
  `BOUNCE`, `ELASTIC` (lite).
- **API**: `ease(curve, progress_0_255) -> int` (returns a `bytes` element, 0..255),
  and `interp(curve, a, b, progress_0_255) -> int` (`a + ((b-a)*ease)//255`).
- **Constraints**: pure integers, no allocation per call, importable on device.
  `ease(c,0)==0`, `ease(c,255)==255` for all curves (endpoints pinned); `OVERSHOOT`/
  `ELASTIC` overshoot is expressed by the consuming effect (table values are clamped
  to the 0..255 `bytes` storage; the consumer scales past the endpoints).

---

## 5. Display primitives (DisplayInterface additions)

- **Module**: `src/scrollkit/display/interface.py` (abstract) +
  `unified.py` / `simulator.py` (impls).
- **New methods/attrs**:
  - `async fill_rect(x, y, w, h, color) -> None` — bounded fill via bulk op.
  - `async fill_span(y, x0, x1, color) -> None` — single-row bounded fill.
  - `async clear_rect(x, y, w, h) -> None` — bounded clear to background.
  - `measure_text(text, font=None) -> int` — **sync**; sum of glyph advances; see
    §7 for the font contract (empty ⇒ 0; missing glyph ⇒ replacement advance).
  - `gfx` (property) → a single **cached** namespace instance (built once in
    `initialize()`, identity-stable: `display.gfx is display.gfx`) exposing the
    resolved `Bitmap, Palette, TileGrid, Group, bitmaptools` for the platform.
    Plain attribute-holding class, **not** `types.SimpleNamespace`.
  - `add_layer(tilegrid) -> None` / `remove_layer(tilegrid) -> None` — composite a
    `TileGrid` in the `_layer_group` (see §12); idempotent.
- **Invariants**: painters write only inside their (clipped) bounds; never a
  full-2048 Python loop; bulk-op cost is accounted via `account_bulk_op` (§2). A
  looped fallback exists only as a defensive last resort for **tiny** bounded
  regions and is never taken on the supported targets (device has `bitmaptools`,
  simulator has the shim) — see contract S6. `color` is 24-bit `0xRRGGBB`.

---

## 6. OverlayMask (Phase 3 primitive)

- **Module**: `src/scrollkit/effects/overlay.py`
- **Owned state (allocated once)**:
  - `bitmap`: one indexed `gfx.Bitmap(width, height, value_count)`.
  - `palette`: `gfx.Palette(value_count)` with **index 0 transparent**; indices
    1..N opaque cover colors.
  - `tilegrid`: `gfx.TileGrid(bitmap, pixel_shader=palette)` added via
    `display.add_layer` (into `_layer_group`, §12).
- **Mutators (bounded, reuse the bitmap)**: `fill_rect`, `fill_span`, `clear`,
  `clear_rect`, `blit_pattern` — all via `gfx.bitmaptools.fill_region`/`blit`,
  dirty-span only.
- **State**: fully transparent (idle) → covering (opaque indices over region) →
  transparent again (reveal). Reusable across transitions; `detach()` calls
  `display.remove_layer`.
- **Constraints**: no per-frame allocation; the mask is the substrate for all
  Class 2 transitions. Identity of `bitmap`/`palette` is stable across all
  mutations (single allocation — asserted in tests).

---

## 7. ScrollingText (fixed-point rewrite, D8)

- **Module**: `src/scrollkit/display/content.py`
- **Module constant**: `LOOP_FPS = 20` (keeps scroll math ↔ budget in sync).
- **Changed fields**:
  - `speed: int` (px/sec) — now **honored**.
  - `_pos_q: int` — position in **1/16 px** (fixed point); render `x = _pos_q >> 4`.
  - `_measured_width: int` — from `display.measure_text` (replaces `len*6`),
    computed **once** at `start()`/first render and cached; **never** per frame.
- **Per-frame update**: `_pos_q -= round(speed * 16 / LOOP_FPS)`; complete when
  `(_pos_q >> 4) < -_measured_width`.
- **`measure_text` font contract** (shared with §5):
  - Font must expose `get_glyph(ch)` with an advance (`.dx`/`["dx"]`/`.shift_x`);
    `terminalio.FONT` and the sim BDF/bitmap fonts satisfy it.
  - Empty string ⇒ **0**.
  - Missing/advance-less glyph ⇒ a **defined replacement advance** (font's space
    advance, else a documented constant) — never a crash.
  - If `get_glyph` is unavailable entirely, a one-time Label-width fallback is
    allowed **only** at the single start-time measurement — never on a render
    hot path.
- **`describe()`**: still exposes `speed`, `position` (`_pos_q >> 4`),
  `text_width` (now `_measured_width`).
- **Invariant**: only `.x` of a reused Label changes per frame (no glyph rebuild
  unless the visible string changes — and such a rebuild is an isolated spike the
  strict gate's median window tolerates, D1).

---

## 8. Class 1 — Characterful scrolling content (Phase 4)

- **Module**: `src/scrollkit/effects/scrolling.py` (each a `DisplayContent`).
- **KineticMarquee**: fields — `text`, `color`, `speed`, `pause_chars`
  (punctuation/keywords to dwell on), inertia state (`_velocity_q`, `_pos_q`),
  `_dwell_frames`. Uses `easing` for accel/overshoot. Per-frame: only Label `.x`.
- **WaveRider**: fields — `text`, `color`, `amplitude`, `wavelength`,
  `_phase`, a precomputed `wave_table` (256-entry int sine, stored compactly), a
  small pool of single-char Labels for the **visible window only**. Per-frame:
  `y = baseline + wave_table[(x + phase) & 255]` per visible char.
- **SplitFlap**: fields — `text`, `color`, `flip_steps` (2–4), a deterministic
  PRNG seed (no `random` churn), per-cell `_flip_state`. Entering chars flip
  through intermediate glyphs before landing.
- **Shared invariants**: no per-frame heap alloc; rebuild only on visible-string
  change (an isolated spike, D1); strict-feasible at 20 fps.

---

## 9. Class 2 — Theatrical transitions (Phase 5)

- **Module**: `src/scrollkit/effects/transitions.py` (fresh; replaces the removed
  broken file — D10).
- **Base `Transition`**: drives `OverlayMask` through cover → swap → reveal, with
  the **content swap performed while fully covered** (covered-swap rule, D1);
  `progress` 0..255 via `easing`; `is_complete`. Invokable by the content queue
  between items.
- **Effects** (each a precomputed pattern over the mask):
  - `IrisSnap` — diamond aperture; radius→span lookup table.
  - `VenetianShutters` — 8 coarse bands, staggered open/close.
  - `MosaicResolve` — 4×4/8×4 blocks in a fixed pseudo-random order (~4–12/frame).
  - `CRTCollapse` — brightness ramp + a few horizontal bars.
  - `LightSlitRewrite` — 2–4 px bright scanner; content swap at mid-sweep.
- **Invariants**: bounded mask writes only; swap invisible; strict-feasible.

---

## 10. Class 3 — BitmapText + palette effects (Phase 6)

- **Module**: `src/scrollkit/display/bitmap_text.py`
- **Font5x7**: table of 5×7 glyph bitmasks stored as **`bytes`** (one byte per
  glyph row; S5), table-driven, no BDF. Covers the printable ASCII the showcase
  needs.
- **BitmapText** (`DisplayContent`): renders a message **once** into an indexed
  `gfx.Bitmap` (glyph pixels = palette indices, bg = index 0) + a `gfx.Palette`
  + a `gfx.TileGrid` added via `add_layer` (into `_layer_group`, §12). `scroll_x`
  moves the TileGrid `.x`. Field: documented `max_width_px` (Option A).
- **Palette effects** (rewrite palette entries per frame, no glyph rebuild):
  `NeonTubeCrawl`, `ChromeSheen`, `RainbowChase`, `HazardStripes`. Each holds a
  small color ramp + a `_phase`; per-frame writes a few `palette[i] = color`.
- **Invariants**: palette rotation changes output with **no** glyph rebuild and no
  per-pixel loop (bitmap object identity stable across frames — asserted);
  strict-feasible.

---

## 11. Feasibility metadata (effect catalog tags — Phase 7)

Each shipped showcase effect advertises a small, JSON-able metadata block
(surfaced in docs and, where natural, the `capabilities()` catalog):

- `hardware_safe: bool` — passes the strict gate at 20 fps.
- `allocates_per_frame: bool` — must be `False` for showcase effects.
- `max_pixel_writes_per_frame: int` — bounded worst-case bulk writes.
- `modeled_frame_ms: number` — typical modeled per-frame cost (≤ 50 ms).

Descriptive (documentation/advertising), derived from the strict-mode verification
runs; not a second enforcement path.

---

## 12. Display group structure (layer ownership — D11/B5)

- **Modules**: `display/unified.py`, `display/simulator.py` (identical structure).
- **Structure** inside the existing `main_group`:
  - `_content_group` (`gfx.Group`) — **below**; owned by the Label pool and
    `fill()`: background TileGrid (index 0) + pooled Labels. `draw_text` appends
    Labels here; `clear()` resets the pool index here and **nowhere else**.
  - `_layer_group` (`gfx.Group`) — **above**; owned by `add_layer`/`remove_layer`:
    overlay-mask and bitmap-text TileGrids. Insertion order = z-order. `clear()`
    never touches it (persistent across frames).
- **Invariant**: content can never render above an effect layer regardless of
  Label-pool growth; `add_layer`/`remove_layer` are idempotent; layer owners
  `detach()` when done.
- **Migration**: code assuming the background lives at `main_group[0]` moves to
  `_content_group[0]`.

---

## Entity relationships (text)

```
PerformanceManager (strict) ──reads──> HardwareProfile (budget, base+slope per-px)
        │ raises (sim only)
        ▼
FeasibilityError ──surfaced in──> RunResult.errors (via run_headless)

DisplayInterface.gfx (cached) ──resolves──> {displayio, bitmaptools}  (real on device / shim on sim)
        ▲                                          ▲
        │ used by                                  │ bulk ops accounted by
   OverlayMask, BitmapText, painters ─────────────┘──> PerformanceManager.account_bulk_op

main_group = [_content_group (Labels/fill, below)] + [_layer_group (effect layers, above)]
   add_layer/remove_layer ── manage ──> _layer_group ;  clear() ── resets ──> _content_group pool only

easing LUTs (bytes) ──used by──> ScrollingText, Class 1 (scrolling), Class 2 (transitions)
OverlayMask ──substrate for──> Class 2 transitions (cover→swap-while-covered→reveal)
Font5x7 (bytes) + Palette ──substrate for──> Class 3 palette effects
```
