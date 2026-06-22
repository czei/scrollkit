# Phase 0 Research: ScrollKit Showcase Effects

All decisions below are grounded in a direct read of the current source and the
calibrated `matrixportal_s3_baseline.json` / `device_benchmarks.json`. There are
no remaining `NEEDS CLARIFICATION` items; the roadmap resolved intent and the
codebase read resolved mechanics.

> **Revision (post-`after_plan` PAL review)**: D1, D5, D6, D8 were tightened and
> D11 added in response to the gate review. See **Open risks** at the end for the
> items deliberately carried forward.

## Calibrated cost facts (the budget these decisions are measured against)

- **Per-frame budget**: 20 fps target ⇒ `1_000_000 / 20 = 50_000 µs`.
- **`display.refresh()` @ bit_depth 4**: `4_492 µs` (baseline `full_refresh_us =
  4488.12`). @ bit_depth 6: `13_691 µs` (~3×). ⇒ keep **bit_depth 4**; refresh
  alone leaves ~45.5 ms of headroom per frame.
- **Label glyph rebuild**: `16.53 µs/px` (`bitmap_rebuild_us_per_px`). A full
  64×32 rebuild = `2048 × 16.53 ≈ 33_858 µs`. **Two full rebuilds per frame bust
  the budget** — this is *the* reason "no per-frame glyph rebuild" and "reuse
  Labels" are hard rules. A **single** legitimate rebuild (visible string change)
  lands at ~34 ms + refresh ~4.5 ms ≈ ~38–40 ms — under budget but close, and a
  marquee that also overshoots/eases could push one such frame over 50 ms. **This
  is exactly why the strict gate must tolerate isolated spikes (D1).**
- **Bulk C ops (sanctioned)**: `bitmaptools.fill_region` ≈ `147 µs / 512 px`
  (≈0.287 µs/px); `bitmaptools.blit` ≈ `160 µs / 256 px` (≈0.623 µs/px);
  `draw_line` ≈ `30 µs`. Cheap — dozens per frame fit easily.
- **RAM**: `usable_ram_bytes = 2_073_536`; `base_app_ram_bytes = 976`;
  `bytes_per_label_px = 0.1875`. Modeled peak = floor + largest live bitmap.

---

## D1 — Strict gate granularity: steady-state window + transient ceiling

**Problem raised by review (B1)**: a single-frame `total_us > 50_000 ⇒ raise`
with only `warmup_frames` covering frame 0 is too brittle. A *legitimate* Label
rebuild on a mid-run visible-string change (allowed by spec US4) spikes one frame
and would false-trip, making the gate reject valid effects at the first content
swap. A hard single-frame budget answers the wrong question; the real question is
"does this **sustain** ~20 fps on device?"

**Decision** — enforce in `_end_frame()` with **two** thresholds plus a warmup
grace, not one:

1. **Steady-state gate (the real feasibility check)**: the **median** of the last
   `gate_window` frame totals must be `≤ frame_budget_us` (50 000). Median over a
   short window (default `gate_window = 8`) naturally tolerates an isolated rebuild
   spike but fails on *sustained* over-budget cost. Only evaluated once the window
   is full and `_frame_index >= warmup_frames`.
2. **Transient ceiling (catastrophe guard)**: any **single** frame whose
   `total_us > transient_budget_us` fails immediately (after warmup).
   `transient_budget_us = frame_budget_us × transient_factor` (default
   `transient_factor = 2.0` ⇒ 100 000 µs, a ~10 fps floor). A lone glyph rebuild
   (~38–40 ms) passes; two full rebuilds in one frame (~68 ms+) or a runaway
   Python loop trips it. This is the bound on "how bad may a single hiccup be."
3. **RAM gate**: `estimated_peak_ram_bytes() > profile.usable_ram_bytes` fails
   (after warmup).
4. **Warmup grace**: the first `warmup_frames` frames (default **2**) are exempt
   from all three checks (one-time scene/Label/bitmap construction).

**Covered-swap rule (paired with the gate)**: content swaps that legitimately
rebuild a Label should happen **while covered** by a Class 2 transition (the swap
frame is then a transition frame whose cost is the rebuild + a few mask writes,
comfortably under the transient ceiling and absorbed by the median window). Class 1
effects that rebuild on a visible-string change rely on the median window
absorbing the isolated spike. Both are documented behaviors, not accidents.

**Why median, not mean/pXX**: median is cheap, robust to a single outlier, and
needs no float. The window/factor are constructor params so a test can dial the
gate tighter for a negative-control effect. Computing a median sorts a length-8
list per frame — this lives in the **desktop simulator** perf model (never the
device hot path), so the "no per-frame allocation" rule (which targets device
effect code) does not apply to it; it is still trivially cheap.

**Error message**: include frame index, the window median ms and implied fps (or
the single-frame ms for a transient/RAM breach), the relevant budget, and the
dominant `FrameCost` component, e.g.
`"[hw-strict] frames 6–13 median 71 ms (~14 fps) exceeds 50 ms budget (20 fps);
dominant: bitmap_rebuild — reuse Labels / avoid per-frame glyph rebuild."`

**Alternatives rejected**: single-frame hard budget (false-trips legit rebuilds —
the B1 finding); post-hoc `report()` raise (loses the offending-frame pinpoint and
can't stop the run); a separate budget object (duplicates frame accounting the
manager owns).

---

## D2 — Keeping the existing warning path green (back-compat)

**Decision**: `strict` defaults to **False** at the `PerformanceManager` level.
The ambient-warning path (`_maybe_emit_ambient_warning`, rate-limiting,
`last_warning`, `stutter_fps`, no-sleep-when-not-throttled) is **untouched**.
Strict is purely additive: when off, `_end_frame()` behaves exactly as today.

**Rationale**: `test/unit/simulator/test_hardware_realism.py` pins the warning
behavior in detail (warns below `stutter_fps`, rate-limited to one nag per
`warn_interval`, never sleeps unless `throttle`, sets `last_warning`, the
"one show() == one frame" mapping, etc.). All of these must stay green (FR-010).
Additive `strict` with a default-off flag is the minimal change that satisfies
that.

---

## D3 — Strict plumbing & default policy (incl. device semantics — S2)

**Decision**:
- **Where strict actually runs**: strict feasibility is a **desktop-simulator
  concept**. The `PerformanceManager` only exists when the timing model is active,
  and the model is only ever activated on the desktop (it is a *no-op on
  CircuitPython*, where the device runs at real speed). Therefore
  **`FeasibilityError` is only ever raised in the simulator**; on real hardware
  there is nothing to gate. This resolves the apparent `data-model` ↔ `research`
  inconsistency (S2): `UnifiedDisplay` reads `SCROLLKIT_HW_STRICT` **only on its
  desktop path** (the same place it already conditionally builds a
  `PerformanceManager`); on-device the env read is a documented no-op.
- **Env toggle** `SCROLLKIT_HW_STRICT=1`, read in both
  `SimulatorDisplay._maybe_enable_hardware_timing()` and the desktop branch of
  `UnifiedDisplay._maybe_enable_hardware_timing()`, mirroring how
  `SCROLLKIT_HW_SIM` / `SCROLLKIT_HW_THROTTLE` are already read. When set (and HW
  timing is active) ⇒ `PerformanceManager(..., strict=True)`.
- **Constructor flag** `strict: bool = False` on `SimulatorDisplay.__init__`
  (next to `hardware_timing`/`throttle`). `strict=True` implies hardware timing
  (you can't gate a model you aren't running).
- **`run_headless(..., strict=False)`**: when True, set `SCROLLKIT_HW_STRICT=1`
  for the run (alongside the existing `SCROLLKIT_HW_SIM=1` it sets when
  `hardware=True`), restoring the previous value afterward (the harness already
  saves/restores `SCROLLKIT_HW_SIM`). `FeasibilityError` raised mid-loop is caught
  by the existing per-frame `except Exception` and appended to
  `RunResult.errors` (tagged `feasibility:`), so `result.ok` is False — no harness
  crash, no new catch needed.
- **Default-on for showcase entry points**: the new effect tests call
  `run_headless(app, hardware=True, strict=True, frames=120)`; the demo reel
  constructs its display with `strict=True`. Low-level default stays off.

**Edge — strict without an active model**: `strict=True` via the constructor
forces the model on; the env-var path is a no-op when no model is built. Documented:
strict is meaningful only with the timing model active (i.e., on desktop).

---

## D4 — `FeasibilityError` placement

**Decision**: Define `class FeasibilityError(SLDKError)` in
`src/scrollkit/exceptions.py` (alongside `DisplayError`, `SimulatorError`, …). It
is *raised* only from the desktop `PerformanceManager`, but the *class* lives in
core `exceptions.py`.

**Rationale**: `exceptions.py` is the project's single exception module and is
CircuitPython-safe (pure class defs, base `Exception`). Putting it there lets the
harness, tests, and any caller `from scrollkit.exceptions import FeasibilityError`
without pulling in the simulator. Inheriting `SLDKError` keeps it catchable by
broad handlers and consistent with the family.

**Alternative rejected**: defining it inside `performance_manager.py` (simulator)
would force test/harness imports through the desktop-only module. Rejected.

---

## D5 — The dev==hardware bridge: simulator `bitmaptools` shim + `gfx` accessor

**Problem**: painters (`fill_rect`/`fill_span`), the overlay-mask, and bitmap-text
all need **bulk C ops** on an indexed `Bitmap`. On device these are
`bitmaptools.fill_region(bitmap, x1, y1, x2, y2, value)` and
`bitmaptools.blit(dest, source, x, y, ...)` (built-in C, benchmarked in
`device_benchmarks.json`). The simulator emulates `displayio`
(Bitmap/Palette/TileGrid/Group, with `Bitmap.blit`) but has **no `bitmaptools`
module**. Without a bridge, the same code can't run both places.

**Decision**:
1. Add `src/scrollkit/simulator/bitmaptools.py` — a faithful shim implementing at
   least `fill_region(bitmap, x1, y1, x2, y2, value)` and
   `blit(dest, source, x, y, *, x1=0, y1=0, x2=None, y2=None, skip_index=None)`,
   operating on the numpy-backed simulator `displayio.Bitmap`. It mirrors the
   **exact CircuitPython `bitmaptools` semantics** for the subset we use:
   `fill_region` fills the half-open rectangle `[x1,x2) × [y1,y2)` (CP convention),
   clipped to the bitmap; `blit` copies `source` into `dest` at `(x,y)` honoring
   the source sub-rectangle `[x1,x2)×[y1,y2)` and `skip_index` transparency, with
   clipping at all four edges and at negative offsets; out-of-range/empty regions
   are no-ops (no raise). Desktop-only; never imported on CircuitPython.
2. **Shim conformance is a controlled artifact (addresses B2)**: a **golden
   corpus** pins the shim to the device. `test/claude/bitmaptools_golden.py`
   (host-side device tool, raw-REPL, writes nothing to the board) runs a fixed
   battery of `fill_region`/`blit` ops on real CircuitPython and dumps the
   resulting bitmaps to `test/unit/display/bitmaptools_golden.json`. A
   simulator-side test (`test/unit/display/test_bitmaptools_shim.py`) replays the
   **same** ops through the shim and asserts byte-identical output against the
   golden file. The golden battery deliberately exercises the risky cases: edge
   clipping, negative source offsets, `skip_index` transparency, zero-area
   regions, and full-bitmap fills. Until a board is available, ship a golden file
   captured once and treat its recapture as the calibration step (same model as
   `matrixportal_s3_baseline.json`). **If sim ever diverges from the golden, the
   shim is fixed — never the shared effect logic.**
3. Add a platform-resolving **`gfx`** accessor on the display, **built once per
   display instance and cached** (addresses S3 — never construct it per access).
   `display.gfx` returns a small, fixed instance (a plain class with the attributes
   set once at `initialize()`, **not** `types.SimpleNamespace`) exposing the
   resolved `Bitmap`, `Palette`, `TileGrid`, `Group`, and `bitmaptools` modules:
   real built-ins on CircuitPython, the `scrollkit.simulator` equivalents
   (incl. the shim) on desktop. `assert display.gfx is display.gfx` holds.
   Effects build their bitmaps via `display.gfx.*` so one code path is correct on
   both platforms.
4. Add `display.add_layer(tilegrid)` / `display.remove_layer(tilegrid)` —
   see **D11** for the group-ownership model these depend on.

**CP-safety of the bridge (addresses S4)**: the `gfx` class carries no runtime
`typing`, no `Protocol`; desktop-only imports (numpy, the simulator `bitmaptools`)
are reached only via the simulator display, never at device import time. The
device path imports the real built-ins lazily inside `initialize()`.

**Rationale**: the literal application of "One display, dev == hardware" — the
*only* platform-specific thing is which modules the display resolves; all effect
logic is shared, and the golden corpus makes "faithful" verifiable rather than
asserted.

**Alternatives rejected**: per-pixel `set_pixel` fast/slow paths (violates the
single-code-path and no-2048-loop rules on the simulator); ad-hoc `bitmaptools`
emulation inside each effect (duplication + drift).

---

## D6 — Costing the bulk painters: base + slope, conservative (addresses B3)

**Problem raised by review**: a pure `px × per_px_cost` model derived from **one**
benchmarked size per op ignores fixed per-call overhead and mis-handles
clipped/no-op blits — yet the strict gate rides on it.

**Decision**: account each bulk op as `cost_us = bulk_base_us + px × slope_us[kind]`:
- `slope_us[fill_region] ≈ 0.287` (147 049 ns / 512 px), `slope_us[blit] ≈ 0.623`
  (159 462 ns / 256 px) — the linear rates we have.
- `bulk_base_us` — a fixed per-call C-dispatch overhead, default **≈ 12 µs**
  (conservative; in the ballpark of `draw_line`'s 30 µs being mostly overhead).
  Adding a base **on top of** the already-call-inclusive linear rate slightly
  **over**-counts, which is the safe direction for a gate (fail conservative).
- `px` passed in is the **clipped** region's pixel count (the bbox actually
  scanned); a fully-clipped/no-op call accounts only `bulk_base_us`. For `blit`,
  `px` is the clipped source bbox (so a `skip_index` blit still pays for the scan,
  matching the C cost).
- Constants live on/near `HardwareProfile` (defaulted fields, seeded from the
  benchmark table) so they stay calibrated, not magic numbers in effects.
- Fold into a new `FrameCost.bulk_ops_us` slot, included in `total_us`, so the
  strict gate counts painter work.

**Calibration TODO (tracked, not blocking)**: `device_benchmarks.py` currently
captures `fill_region`/`blit` at a single size each. Add 2–3 sizes per op so
`bulk_base_us`/`slope_us` can be **fit** rather than estimated; recapture into
`device_benchmarks.json`. Until then the conservative base keeps the gate honest
(erring toward rejecting borderline-heavy effects).

**Rationale**: the gate is only trustworthy if it counts the work the painters do
*and* the per-call overhead that dominates many small ops; base+slope captures both
with the data we have, biased safe.

---

## D7 — Overlay-mask layer (Phase 3 primitive for Phase 5)

**Decision**: `effects/overlay.py` provides an `OverlayMask` that, given a
display, allocates **once**: one indexed `gfx.Bitmap(w, h, value_count)`, one
`gfx.Palette` with **index 0 made transparent** (plus a few opaque "cover"
colors), and one `gfx.TileGrid` added on top via `display.add_layer` (into the
layer group — D11). It exposes bounded mutators (`fill_rect`, `fill_span`,
`clear`, `clear_rect`, `blit_pattern`) that write into the mask bitmap via
`gfx.bitmaptools.fill_region`/`blit` and touch **only dirty spans**. Cover = paint
opaque indices over the region; reveal = set those cells back to transparent
index 0.

**Rationale**: a whole class of transitions becomes "write a small pattern into
the mask" — no Label work, no full-screen pixels, allocate-once. Transparent
index 0 lets the underlying Label content show through except where covered.

**State**: mask starts fully transparent; a transition drives it cover →
(swap content while fully covered — the covered-swap rule from D1) → reveal. The
`OverlayMask` is reusable across transitions (`clear()` resets to transparent;
`detach()` removes its layer).

---

## D8 — Fixed-point `ScrollingText` + measured width (incl. font contract — S1)

**Decision** (rewrite `ScrollingText` state/`render` in `display/content.py`):
- Position becomes a fixed-point accumulator in **1/16 px**: `self._pos_q` (int).
  Per frame, advance by `delta_q = round(speed * 16 / LOOP_FPS)` where `speed` is
  px/sec and `LOOP_FPS = 20` (module constant; matches the loop's `sleep(0.05)`
  and the budget). Render at integer `x = self._pos_q >> 4`. Speed N now advances
  ~N× faster than speed 1 (SC-007).
- Width from a new `display.measure_text(text, font=None) -> int`.
- Completion uses measured width (`(_pos_q >> 4) < -_measured_width`).

**`measure_text` font contract (addresses S1/N3)**:
- **Supported font contract**: the font must expose `get_glyph(ch)` returning a
  glyph with an advance (`.dx`/`["dx"]`, or `.shift_x`). `terminalio.FONT` and the
  simulator BDF/bitmap fonts both satisfy this; the contract is documented so any
  custom font must too.
- **Missing glyph**: a char with no glyph (or no advance) contributes a **defined
  replacement advance** (the font's space-glyph advance, else a documented
  constant) — never a crash (spec edge case).
- **Empty string** measures **0** (N3).
- **No per-frame allocation / no hot-path fallback**: `measure_text` is called
  **once** (at `start()`/first render) and cached in `self._measured_width`; it is
  **never** called per frame. The legacy throwaway-Label fallback is used **only**
  when `get_glyph` is entirely unavailable, and **only** at that one-time
  measurement — never on the render hot path. (A small `(font_id, text) → width`
  cache may memoize repeats.)

**Rationale**: makes `speed` meaningful and width accurate, gives Phase 4 a
sub-pixel substrate, and keeps measurement off the hot path so it can't inject a
rebuild cost that the strict gate would then (rightly) flag.

**Back-compat**: `ScrollingText.__init__(speed: int = 30, ...)` keeps its
signature; only behavior changes. `describe()` still exposes
`speed`/`position`/`text_width` (now meaningful).

**N4 note**: `LOOP_FPS = 20` intentionally fixes scroll math to the showcase
budget. Deriving it from display/app config is a future refinement (tracked), not
needed while 20 fps is the fixed target.

---

## D9 — 5×7 bitmap font + palette animation (Phase 6 shape)

**Decision** (contract-level here; full design in the Class 3 sub-feature):
- `display/bitmap_text.py` ships **table-driven** 5×7 glyph bitmasks (no BDF
  parsing) stored compactly (**`bytes`**, one byte per glyph row — see S5) for at
  least the printable ASCII the showcase needs. A message is rendered **once** into
  an indexed `gfx.Bitmap` where glyph pixels carry **palette indices**
  (1..N for ramp position), background = index 0.
- Scroll by moving the glyph `gfx.TileGrid` `.x` (no repaint).
- Palette-animation effects (neon-tube crawl, chrome sheen, rainbow chase, hazard
  stripes) rewrite **palette entries** each frame (a few `palette[i] = color`
  writes) — near-zero per-frame pixel work, no glyph rebuild.
- Start with **Option A** (whole message → one indexed bitmap, documented
  `max_width_px`). Ring-buffer viewport variant is explicitly deferred.

**Rationale**: the headline "not just displayio" capability and the cheapest
possible animation (swap colors, not pixels). The simulator already emulates
indexed Bitmap + Palette (RGB565) + TileGrid, so the same path renders both places.

**Open sub-feature questions** (defer to Class 3 `/specify`): exact glyph set &
inter-letter spacing; how many palette indices the ramp uses; max message width
before requiring the viewport variant.

---

## D10 — Removal sequencing without breaking the suite (Phase 1)

**Decision**: Delete `effects/transitions.py` and `effects/reveal.py` outright;
delete the five broken classes in `effects/basic_transitions.py` (the whole file —
`FadeInEffect`, `SlideInEffect`, `WipeEffect`, `FlashEffect`, duplicate
`PulseEffect`); prune `effects/__init__.py` imports + `__all__`
(`FadeInEffect`, `SlideInEffect`, `WipeEffect`, `RevealEffect`); fix the
`example_usage()` imports in `content_classes.py` (lines ~295–316) and the
`strategy.py` docstring example (line ~213). Update
`test/unit/dev/test_capabilities.py` (drop the `FadeInEffect` expectation).
**Retain** `EffectsEngine` / `get_rainbow_color()`, all `effects/effects.py`
`SimpleEffect` subclasses still used by `enhanced_content.py` (`SparkleEffect`,
`EdgeGlowEffect`, the *other* `PulseEffect`), and all of `particles.py`.

**`transitions.py` is delete-then-recreate across phases (addresses S8/N1)**: the
file the file-tree shows as deleted in **Phase 1** is the *broken* one; a
**brand-new** `effects/transitions.py` (the Class 2 pack) is created in **Phase 5**
with entirely different contents. These are two phases apart — not a same-phase
delete/create conflict. `/tasks` must order the delete (P1) strictly before the
recreate (P5).

**Removal is asserted, not assumed**: a test asserts **every** FR-001 name
(`TransitionEngine`, `BaseTransition`, `FadeTransition`, `WipeTransition`,
`SlideTransition`, `RevealEffect`, `RevealCenterEffect`, `FadeInEffect`,
`SlideInEffect`, `WipeEffect`, `FlashEffect`, the duplicate `PulseEffect`) raises
`ImportError`/`AttributeError` from its old location and is absent from
`effects.__all__` and the `capabilities()` catalog.

**Verified safe**: the only existing test asserting a removed name is
`test/unit/dev/test_capabilities.py` (`FadeInEffect`); no test imports the removed
transition/reveal classes. `capabilities()._effects()` introspects
`effects.__all__`, so pruning `__all__` auto-prunes the catalog (FR-002). Demos use
only `get_rainbow_color()` (retained).

---

## D11 — Layer ownership & z-order vs the per-frame `clear()` (addresses B5)

**Problem raised by review**: `add_layer` composites persistent TileGrids "on top
of Label content", but the existing display `clear()` resets the Label pool index
every frame and `draw_text` may **append** new Labels to `main_group` as the pool
grows — which would land Labels *above* a previously-added overlay layer, breaking
z-order, and leaves the persistent layer's lifecycle vs `clear()` undefined.

**Decision** — give the display an explicit two-child structure inside
`main_group`, implemented identically in `UnifiedDisplay` and `SimulatorDisplay`:

```
main_group
├── _content_group   # owned by the Label pool + fill(): backgrounds, Labels
└── _layer_group     # owned by add_layer(): overlay-mask, bitmap-text TileGrids
```

- `_content_group` is **always below** `_layer_group` (fixed sibling order in
  `main_group`), so content can never render above an effect layer regardless of
  pool growth.
- The Label pool and `fill()` operate **only** on `_content_group`; `draw_text`
  appends Labels there. `fill()`'s background TileGrid goes to `_content_group`
  index 0 (today it inserts at `main_group` index 0 — this moves down one level).
- `clear()` resets the Label pool index in `_content_group` and **never touches
  `_layer_group`** — persistent layers survive frames by design.
- `add_layer(tg)` appends `tg` to `_layer_group` (top = last; insertion order is
  z-order) and records it; `remove_layer(tg)` removes it. Both are **idempotent**
  (re-adding an present layer is a no-op; removing an absent one is a no-op).
- Layer owners (`OverlayMask`, `BitmapText`) call `detach()` to remove their layer
  when done.

**Rationale**: this reconciles the new persistent-layer model with the existing
per-frame label-pool/`clear()` model with a single, explicit ownership rule, and
guarantees stable z-order. It is a small structural change (one extra nesting
level) that both the simulator `Display._render_group` recursion and real
`displayio.Group` already handle.

**Implementation note/risk**: `fill()` and any code assuming background lives at
`main_group[0]` must be updated to `_content_group[0]`; the painter `clear_rect`
and overlay both rely on this ordering. Covered by Phase-3 painter/overlay tests.

---

## Open risks (carried into implementation; tracked, not blocking)

| Risk | Mitigation in plan | Residual |
|---|---|---|
| **Shim fidelity** (D5/B2): sim `bitmaptools` could diverge from device | Golden-corpus conformance test; "fix the simulator" rule | Golden must be (re)captured on a real board to be authoritative; until then it's a one-time capture, like the baseline JSON |
| **Strict false-trips** (D1/B1) | Steady-state median + transient ceiling + warmup + covered-swap rule | Window/factor defaults are judgment calls; tunable via ctor params and revisited if a legit effect trips |
| **Bulk-cost accuracy** (D6/B3) | base+slope, conservative base, clipped-px input | Single-size benchmark per op; recalibration TODO in `device_benchmarks.py` |
| **Foundation API stability** (B4) | Phase 3 ships a **proving consumer** per primitive (see plan Scope & sequencing) before the API is frozen | Full Class 4–6 effects still land in sub-features; their needs could surface a missed API affordance |
| **Simulator-first verification** | Whole gate is modeled, not measured on device per effect | Only the BASIC display path is device-verified today (per project memory) |

---

## Decisions summary

| # | Decision | Rationale (1-liner) |
|---|----------|---------------------|
| D1 | Strict = steady-state median window + transient ceiling + warmup(2) | Tolerates legit isolated rebuild spikes; still catches sustained over-budget (B1) |
| D2 | `strict` default-off, warning path untouched | Keeps `test_hardware_realism` green (FR-010) |
| D3 | `SCROLLKIT_HW_STRICT` + ctor flag + `run_headless(strict=)`; sim-only; default-on at showcase | Matches "HW on ⇒ strict"; clarifies device no-op (S2) |
| D4 | `FeasibilityError(SLDKError)` in `exceptions.py` | Core, CP-safe, importable without simulator |
| D5 | Sim `bitmaptools` shim + cached `gfx`/`add_layer` + golden-corpus conformance | dev==hardware bridge, verifiable not asserted (B2,S3,S4) |
| D6 | Bulk cost = `base + px·slope`, conservative; clipped px | Counts per-call overhead; gate fails safe (B3) |
| D7 | `OverlayMask`: one indexed bitmap, transparent idx 0 | Transitions = "paint a tiny mask", allocate-once |
| D8 | Fixed-point (1/16 px) `ScrollingText`; measured width, off hot path, defined font contract | Speed drives motion; real width; no hot-path alloc (SC-007,S1,N3) |
| D9 | 5×7 `bytes` font → indexed bitmap → palette swaps | Cheapest animation; headline differentiator (S5) |
| D10 | Surgical removal; retain particles + rainbow; assert every name gone | Suite stays green; one test edited (S8/N1) |
| D11 | `_content_group` below `_layer_group`; `clear()` never touches layers | Stable z-order; persistent-layer lifecycle vs pool `clear()` (B5) |
