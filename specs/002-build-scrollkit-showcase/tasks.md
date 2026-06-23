---

description: "Task list for ScrollKit Showcase Effects — committed scope: Phases 1–3 (US1–US3)"
---

# Tasks: ScrollKit Showcase Effects

**Input**: Design documents from `specs/002-build-scrollkit-showcase/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md (all present)

**Tests**: INCLUDED. This project requires `make test-unit` green every phase and
FR-033 mandates per-effect unit tests (lit pixels advance, animation advances, no
per-frame allocation, strict-feasible). Test tasks pin the documented behavior in
the contracts.

**Organization**: Tasks are grouped by user story. **US1, US2, US3 (Phases 1–3)
plus the proving spikes are implemented and committed** (T001–T049, all `[X]`).
The spec marks the full Class 1/2/3 effects and the showcase reel as MUST
requirements (FR-016…FR-026, US4–US7), so they are **in scope for this feature**
and tracked below as **Phases 7–10 (T050–T070, unchecked)** for
`/speckit.implement` to build — they were wrongly deferred earlier.

> **Revision (post-`after_tasks` PAL review)**: added a Foundational gate-check
> (T003), a global removed-symbol sweep (T013), and a feasibility-breakdown
> threading task (T022); strengthened the `measure_text` tests (T028/T032), the
> golden-fixture tasks (T030/T036), and the `IrisSnap` proving spike (T033/T044).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependency on an incomplete task)
- **[Story]**: US1 / US2 / US3 (Setup, Foundational, Polish have no story label)
- Paths are repo-relative; run pytest with `PYTHONSAFEPATH=1 PYTHONPATH=src`.

## Path Conventions

Single library: code in `src/scrollkit/`, tests in `test/unit/`, host-side device
tools in `test/claude/`, docs in `docs/`.

> **Build-order note (overrides default story parallelism)**: unlike typical
> independent stories, US1 → US2 → US3 are a **hard linear chain** (the roadmap's
> mandated build order). US1 (clean slate) before US2 (the gate that validates
> later work) before US3 (primitives the proving spikes need). They are still
> *independently testable* at each checkpoint.

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Confirm a clean starting point.

- [X] T001 Confirm clean baseline on branch `002-build-scrollkit-showcase`: run `make test-unit` and `make lint-errors` (Makefile targets at repo root); both MUST be green before any change.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one shared primitive that US2 and US3 (and their tests) all import.

**⚠️ CRITICAL**: Complete before US2/US3 work begins.

- [X] T002 Add `class FeasibilityError(SLDKError)` to `src/scrollkit/exceptions.py` (CP-safe class def; imported by the strict gate, the harness, and all strict tests).
- [X] T003 Run `make test-unit` and `make lint-errors` (repo root); confirm `from scrollkit.exceptions import FeasibilityError` works and the suite is still green (depends on T002).

**Checkpoint**: `FeasibilityError` importable; suite green.

---

## Phase 3: User Story 1 - Honest effects catalog: remove broken effects (Priority: P1) 🎯 MVP

**Goal**: Delete the broken/fake transition effects and prune the public surface,
leaving an honest catalog while keeping the suite green.

**Independent Test**: Removed names are unimportable and absent from
`capabilities()`; retained `particles` + `EffectsEngine.get_rainbow_color()` still
pass; no removed symbol is referenced anywhere in `src/`/`test/`/`demos/`/`docs/`;
`make test-unit` + `make lint-errors` green.

### Tests for User Story 1

- [X] T004 [P] [US1] Write `test/unit/effects/test_removal.py` asserting every FR-001 name (`TransitionEngine`, `BaseTransition`, `FadeTransition`, `WipeTransition`, `SlideTransition`, `RevealEffect`, `RevealCenterEffect`, `FadeInEffect`, `SlideInEffect`, `WipeEffect`, `FlashEffect`, the duplicate `PulseEffect`) raises `ImportError`/`AttributeError` from its old module, is absent from `scrollkit.effects.__all__`, and is absent from `capabilities()`.
- [X] T005 [P] [US1] Update `test/unit/dev/test_capabilities.py` to drop the `FadeInEffect` (and any other removed-name) expectation.

### Implementation for User Story 1

- [X] T006 [P] [US1] Delete `src/scrollkit/effects/transitions.py` (the broken `TransitionEngine`/`BaseTransition`/`FadeTransition`/`WipeTransition`/`SlideTransition`). NOTE: a brand-new, unrelated `transitions.py` is created later in this task list's US3 section as the minimal `IrisSnap` proving spike (T044) — this delete MUST come first; the full roadmap Phase 5/Class 2 work is deferred.
- [X] T007 [P] [US1] Delete `src/scrollkit/effects/reveal.py` (`RevealEffect`, `RevealCenterEffect`).
- [X] T008 [P] [US1] Delete `src/scrollkit/effects/basic_transitions.py` in full (`FadeInEffect`, `SlideInEffect`, `WipeEffect`, `FlashEffect`, duplicate `PulseEffect`).
- [X] T009 [US1] Prune `src/scrollkit/effects/__init__.py`: remove the `from .basic_transitions import …` and `from .reveal import …` lines and drop `FadeInEffect`, `SlideInEffect`, `WipeEffect`, `RevealEffect` from `__all__` (depends on T006–T008).
- [X] T010 [P] [US1] Fix `src/scrollkit/content_classes.py` `example_usage()` (≈lines 295–316): remove the import and uses of `RevealEffect`, `FadeInEffect`, and the basic-transitions `PulseEffect`.
- [X] T011 [P] [US1] Fix the docstring example in `src/scrollkit/display/strategy.py` (≈line 213) that references `RevealEffect`.
- [X] T012 [P] [US1] Rewrite the "what's available" section of `docs/guide/effects.md` to match the pruned catalog (keep `particles`, `get_rainbow_color()`).
- [X] T013 [US1] Global removed-symbol sweep: `rg -n 'TransitionEngine|BaseTransition|FadeTransition|WipeTransition|SlideTransition|RevealEffect|RevealCenterEffect|FadeInEffect|SlideInEffect|WipeEffect|FlashEffect' src/ test/ demos/ docs/` and update or intentionally document (as historical/removal notes) every remaining mention — the contract requires NO surviving reference to a removed symbol anywhere (depends on T006–T012).
- [X] T014 [US1] Run `make test-unit` + `make lint-errors`; confirm green, including the retained `test/unit/effects/test_effects_engine.py` and `test/unit/effects/test_particles.py` (depends on T004–T013).

**Checkpoint**: US1 complete — honest catalog, suite green, removal asserted and swept.

---

## Phase 4: User Story 2 - Strict hardware-feasibility gate (Priority: P1)

**Goal**: A strict mode where a *sustained* over-budget effect (steady-state median
breach) or a *catastrophic* single frame (transient ceiling) raises
`FeasibilityError`, while an isolated legitimate rebuild does not — plumbed through
the displays and `run_headless`, default-off at the low level.

**Independent Test**: Over-budget effect under `strict=True` ⇒ `result.ok is False`
with a feasibility error; cheap effect ⇒ `True`; one isolated rebuild ⇒ `True`;
existing warning-path tests unchanged.

### Tests for User Story 2

- [X] T015 [P] [US2] Add strict-gate cases to `test/unit/simulator/test_hardware_realism.py`: sustained over-budget raises `FeasibilityError`; an isolated single spike does NOT (median tolerates); a catastrophic frame raises (transient ceiling); a RAM breach raises; the `warmup_frames` grace exempts the first frames; and ALL existing warning-path + `breakdown_ms` assertions still pass with `strict=False`.
- [X] T016 [P] [US2] Add strict cases to `test/unit/dev/test_harness.py`: `run_headless(app, hardware=True, strict=True)` over-budget ⇒ `result.ok is False` and an error containing `feasibility`; cheap ⇒ `ok True`; a one-isolated-rebuild app ⇒ `ok True`; `strict=False` behaves exactly as today.

### Implementation for User Story 2

- [X] T017 [US2] Extend `PerformanceManager.__init__` in `src/scrollkit/simulator/core/performance_manager.py` with `strict=False`, `target_fps=20.0`, `warmup_frames=2`, `gate_window=8`, `transient_factor=2.0`; derive `frame_budget_us = 1_000_000/target_fps` and `transient_budget_us = frame_budget_us*transient_factor`.
- [X] T018 [US2] Add a `bulk_ops_us` slot to `FrameCost` (`__slots__`, `total_us`, `as_dict()`) in `src/scrollkit/simulator/core/performance_manager.py`.
- [X] T019 [US2] Add bulk-cost fields to `src/scrollkit/simulator/core/hardware_profile.py`: `bulk_base_us=12.0`, `fill_region_us_per_px=0.287`, `blit_us_per_px=0.623` (defaulted; seeded from `device_benchmarks.json`); load them in the calibrated factory.
- [X] T020 [US2] Add `account_bulk_op(kind, px)` to `PerformanceManager` in `src/scrollkit/simulator/core/performance_manager.py` (cost `= bulk_base_us + px*slope(kind)`, `px` = clipped pixels) writing to `bulk_ops_us`.
- [X] T021 [US2] Implement strict enforcement in `PerformanceManager._end_frame()` (`src/scrollkit/simulator/core/performance_manager.py`): after computing `total_us`, when `strict` and `_frame_index >= warmup_frames` → (1) transient ceiling, (2) steady-state median over the last `gate_window` totals vs `frame_budget_us`, (3) RAM vs `usable_ram_bytes`, raising `FeasibilityError` with a descriptive message (frame/window, ms, fps, budget, dominant component). Leave the ambient-warning path untouched when `strict=False`.
- [X] T022 [US2] Thread the new `bulk_ops_us` component through the feasibility report in `src/scrollkit/simulator/core/feasibility.py`: add a `bulk_ops` key to `FeasibilityReport.breakdown_ms` (and `as_dict()`/`as_text()` as needed) so the new per-frame cost is surfaced, and confirm the existing `breakdown_ms` keys (`bitmap_rebuild`, `pixel_writes`, …) and their ordering used by `test_hardware_realism.py` do not drift (depends on T018, T020).
- [X] T023 [US2] Plumb strict into `src/scrollkit/display/simulator.py`: add a `strict=False` keyword to `SimulatorDisplay.__init__` (implies hardware timing) and read `SCROLLKIT_HW_STRICT=1` in `_maybe_enable_hardware_timing()`; pass `strict` into `PerformanceManager`.
- [X] T024 [US2] Plumb strict into the desktop branch of `UnifiedDisplay._maybe_enable_hardware_timing()` in `src/scrollkit/display/unified.py` (read `SCROLLKIT_HW_STRICT`; document it as a no-op on CircuitPython).
- [X] T025 [US2] Add `strict=False` to `run_headless` and `run_headless_async` in `src/scrollkit/dev/harness.py`: set/restore `SCROLLKIT_HW_STRICT`, and ensure a `FeasibilityError` raised mid-loop is caught by the existing per-frame `except Exception`, appended to `RunResult.errors` tagged `feasibility:` (so `result.ok` is False; harness does not crash).
- [X] T026 [US2] Run `make test-unit` + `make lint-errors`; confirm green, including the unchanged warning-path + `breakdown_ms` assertions (depends on T015–T025).

**Checkpoint**: US2 complete — the gate bites on sustained/catastrophic frames,
tolerates isolated rebuilds, the breakdown surfaces bulk-op cost, and the legacy
warning path is intact.

---

## Phase 5: User Story 3 - Foundational primitives & working scroll speed (Priority: P1)

**Goal**: Ship the shared substrate — integer easing, the `bitmaptools` shim +
cached `gfx` + layer groups, bounded painters + `measure_text`, the `OverlayMask`,
and a fixed-point `ScrollingText` — and PROVE the API with one thin vertical
consumer per primitive (a minimal `IrisSnap` and a minimal `BitmapText`) before it
is frozen.

**Independent Test**: Each foundation unit test green; the proving spikes pass the
strict gate at 20 fps headless (`result.ok is True`, advancing, non-blank); the
shim matches the golden corpus; `make test-unit` + `make lint-errors` green.

### Tests for User Story 3

- [X] T027 [P] [US3] Write `test/unit/effects/test_easing.py`: pinned endpoints (`ease(c,0)==0`, `ease(c,255)==255`), LUTs are `bytes`, integer returns, determinism, no per-call allocation.
- [X] T028 [P] [US3] Write `test/unit/display/test_painters.py`. For `measure_text`, use a **controlled fake font** with known *unequal* glyph advances (e.g. `A.dx=3`, `W.dx=7`) so the test cannot pass falsely against a uniform-6px font: assert width == the exact sum of advances (NOT `len*6`), `measure_text("")==0`, a missing glyph contributes the defined replacement advance, and the one-time Label fallback is NOT taken on render frames. Also assert: `fill_rect`/`fill_span`/`clear_rect` write only in (clipped) bounds; a 64×32 `clear_rect` takes the bulk path (no full Python loop); `display.gfx is display.gfx`.
- [X] T029 [P] [US3] Write `test/unit/display/test_layers.py`: a TileGrid added via `add_layer` survives N `clear()` calls and stays above Labels after the pool grows; `add_layer`/`remove_layer` idempotent.
- [X] T030 [P] [US3] Write `test/unit/display/test_bitmaptools_shim.py`: replay the golden battery through the shim and assert byte-identical output vs the **committed** fixture `test/unit/display/bitmaptools_golden.json` (edge clip, negative offset, `skip_index`, zero-area, full-fill). The test runs desktop-only and MUST NOT reach for a board; it MUST fail clearly with an explanatory message if the fixture is missing (no skip, no board access).
- [X] T031 [P] [US3] Write `test/unit/effects/test_overlay.py`: `OverlayMask` allocates once (bitmap/palette object identity stable across many mutations), index 0 transparent, bounded writes.
- [X] T032 [P] [US3] Write `test/unit/display/test_scrolling_text.py`: at `speed=60` it advances ~2× the px of `speed=30` over equal frames; using the same **controlled fake font** as T028 (unequal advances), the measured scroll width equals the sum of advances (NOT `len*6`); width is measured once (not per frame); completes when fully scrolled off; no per-frame allocation.
- [X] T033 [P] [US3] Write `test/unit/effects/test_proving_spikes.py`: a minimal-`IrisSnap` app and a minimal-`BitmapText`+`RainbowChase` app each pass `run_headless(frames=120, hardware=True, strict=True)` with `ok is True`/`advanced is True`. For `IrisSnap` assert: cover → swap-while-covered → reveal (content hidden at peak cover), and per-frame mask writes are **bounded** (the aperture grows by a bounded span count per frame, not a full repaint). For `BitmapText` assert: palette rotation changes output with the glyph bitmap object identity unchanged (no rebuild).

### Implementation for User Story 3

- [X] T034 [P] [US3] Implement `src/scrollkit/effects/easing.py`: curve ids (`LINEAR`, `EASE_OUT_QUAD`, `EASE_IN_OUT`, `OVERSHOOT`, `BOUNCE`, `ELASTIC`), six length-256 `bytes` LUTs built once at import, `ease(curve, p)->int`, `interp(curve, a, b, p)->int`; CP-safe (no `typing`, no numpy).
- [X] T035 [US3] Implement the simulator shim `src/scrollkit/simulator/bitmaptools.py`: `fill_region(bitmap, x1, y1, x2, y2, value)` (half-open `[x1,x2)×[y1,y2)`, clipped) and `blit(dest, source, x, y, *, x1=0, y1=0, x2=None, y2=None, skip_index=None)` (sub-rect, `skip_index` transparency, four-edge + negative-offset clipping, empty/clipped ⇒ no-op) on the numpy-backed sim `Bitmap`.
- [X] T036 [P] [US3] Add the host-side capture tool `test/claude/bitmaptools_golden.py` (raw-REPL via `test/claude/cpy_repl.py`; writes nothing to the board) that runs the fixed battery on real CircuitPython and emits `test/unit/display/bitmaptools_golden.json`. This tool is **manual/optional calibration only — NOT part of normal test execution**; commit a once-captured `bitmaptools_golden.json` as a required CI fixture (recapture is the calibration step, like `matrixportal_s3_baseline.json`).
- [X] T037 [US3] Add to `src/scrollkit/display/interface.py` the abstract surface: `fill_rect`/`fill_span`/`clear_rect` (async), `measure_text(text, font=None)` (sync), the cached `gfx` property contract, and `add_layer`/`remove_layer` (a plain attribute-holder for `gfx`, no `typing`/`SimpleNamespace`).
- [X] T038 [US3] Restructure `main_group` in `src/scrollkit/display/unified.py` into `_content_group` (below) + `_layer_group` (above); build a cached `gfx` (real `displayio`/`bitmaptools`) once in `initialize()`; implement `add_layer`/`remove_layer`; route the label pool + `fill()` background into `_content_group[0]`; make `clear()` reset the pool in `_content_group` only and never touch `_layer_group`.
- [X] T039 [US3] Apply the identical `_content_group`/`_layer_group` restructure + cached `gfx` (sim `displayio` + the shim) + `add_layer`/`remove_layer` in `src/scrollkit/display/simulator.py` (dev==hardware parity with T038; fix the simulator, not shared logic).
- [X] T040 [US3] Implement the painters + `measure_text` in `src/scrollkit/display/unified.py`: `fill_rect`/`fill_span`/`clear_rect` via `gfx.bitmaptools.fill_region` (clipped bounds; call `account_bulk_op`; tiny-region fallback only, never a full loop); `measure_text` summing font glyph advances (empty ⇒ 0; missing glyph ⇒ replacement advance), no hot-path fallback (depends on T037, T038).
- [X] T041 [US3] Implement the same painters + `measure_text` in `src/scrollkit/display/simulator.py` using the shim (depends on T035, T039).
- [X] T042 [US3] Implement `src/scrollkit/effects/overlay.py` `OverlayMask`: allocate-once indexed `gfx.Bitmap` + `gfx.Palette` (index 0 transparent) + `gfx.TileGrid` added via `display.add_layer`; bounded mutators (`fill_rect`/`fill_span`/`clear`/`clear_rect`/`blit_pattern`) via `gfx.bitmaptools`; `set_cover_color`/`detach` (depends on T038–T041).
- [X] T043 [US3] Rewrite `ScrollingText` in `src/scrollkit/display/content.py`: module `LOOP_FPS = 20`; fixed-point `_pos_q` (1/16 px), `_pos_q -= round(speed*16/LOOP_FPS)`, render `x = _pos_q >> 4`; `_measured_width` via `display.measure_text` computed once at `start()`/first render and cached; complete when `(_pos_q>>4) < -_measured_width`; keep the ctor signature and `describe()` keys (depends on T040/T041).
- [X] T044 [US3] Create the FRESH `src/scrollkit/effects/transitions.py` with a `Transition` base (cover → `swap_callback` while covered → reveal, `progress` via `easing`, `is_complete`) and a minimal `IrisSnap` implemented as a **diamond aperture driven by a precomputed radius→span lookup table** writing only bounded mask spans per frame (the intended Class 2 shape, so the spike de-risks future US5) — the proving consumer for `gfx`/`add_layer`/`OverlayMask`/`easing` (depends on T034, T042). NOTE: this is the new file; the old one was deleted in T006.
- [X] T045 [US3] Create `src/scrollkit/display/bitmap_text.py` with a compact 5×7 `bytes` glyph subset (enough for the proving message), `BitmapText` (render once into an indexed `gfx.Bitmap`, scroll via `TileGrid.x`, attach via `add_layer`, documented `max_width_px`) and a minimal `RainbowChase` palette effect — the proving consumer for `gfx`/`add_layer`/palette (depends on T038–T041).
- [X] T046 [US3] Run `make test-unit` + `make lint-errors` and the quickstart Phase 3 validations; confirm green and that both proving spikes pass strict at 20 fps (depends on T027–T045).

**Checkpoint**: US3 complete — the foundation API is proven by real consumers and
frozen; Phases 4–6 can build on it.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verify invariants and wrap up the committed scope.

- [X] T047 [P] Confirm `scrollkit.dev` import-safety: `test/unit/dev/test_dev_import_safety.py` still green, and the top-level `scrollkit/__init__` + `app/` + core `display/` import path never pulls in `numpy`/`pygame`/the simulator `bitmaptools` (effects subsystem stays optional).
- [X] T048 [P] Update `docs/guide/effects.md` (and add a short foundation note) describing the strict feasibility gate, easing, painters, the overlay-mask, and the `gfx`/layer model, each with its hardware-budget framing.
- [X] T049 Run the full quickstart.md Phases 1–3 validation end-to-end (including the negative control and the isolated-rebuild-passes case) and the whole suite: `make test-unit` + `make lint-errors` green.

---

## Phase 7: User Story 4 - Class 1 Characterful scrolling (Priority: P2)

**Goal**: Scrolling text with personality, built on the easing engine + fixed-point
ScrollingText. **Independent test**: each renders, advances frame-to-frame, has no
per-frame allocation, and `run_headless(app, frames=120, hardware=True, strict=True).ok`.

- [ ] T050 [P] [US4] Write `test/unit/effects/test_scrolling_effects.py`: `KineticMarquee` dwells at punctuation/keywords and overshoots; `WaveRider` realizes only the visible-window characters; `SplitFlap` is deterministic given `seed`. Each asserts lit pixels advance, no per-frame allocation, and strict-feasible at 20 fps.
- [ ] T051 [US4] Implement `KineticMarquee(DisplayContent)` in `src/scrollkit/effects/scrolling.py`: easing-driven accelerate-in / coast / dwell at `pause_chars` / overshoot, using the 1/16-px fixed-point position (`LOOP_FPS`) and `display.measure_text`; only a reused Label's `.x` changes per frame.
- [ ] T052 [US4] Implement `WaveRider(DisplayContent)` in `src/scrollkit/effects/scrolling.py`: a precomputed 256-entry integer wave table; a small pool of single-char Labels for the visible window only; `y = baseline + wave_table[(x + phase) & 255]`; rebuild a char only when it enters the viewport.
- [ ] T053 [US4] Implement `SplitFlap(DisplayContent)` in `src/scrollkit/effects/scrolling.py`: entering characters flip through 2–4 deterministic intermediate glyphs via a seeded PRNG (no per-frame random allocation) before landing.
- [ ] T054 [US4] `make test-unit` + `make lint-errors` green; confirm all three Class 1 effects pass strict at 20 fps.

---

## Phase 8: User Story 5 - Class 2 Theatrical transition pack (Priority: P2)

**Goal**: The full transition pack on the overlay-mask primitive (extends the
existing `Transition` base + `IrisSnap`). **Independent test**: correct cover →
swap-while-covered → reveal, bounded per-frame mask writes, strict-feasible.

- [ ] T055 [P] [US5] Write `test/unit/effects/test_transitions.py`: for each transition assert content is hidden at peak cover then revealed, per-frame mask writes are bounded (no full repaint), and strict-feasible at 20 fps.
- [ ] T056 [US5] Add `VenetianShutters` to `src/scrollkit/effects/transitions.py` (Transition base): 8 coarse horizontal bands, staggered open/close via the easing tables.
- [ ] T057 [US5] Add `MosaicResolve`: 4×4 / 8×4 blocks covered/revealed in a fixed pseudo-random order (~4–12 blocks/frame), deterministic.
- [ ] T058 [US5] Add `CRTCollapse`: a brightness ramp + a few horizontal bars collapsing to / expanding from a center line.
- [ ] T059 [US5] Add `LightSlitRewrite`: a 2–4 px bright vertical scanner that swaps content at mid-sweep.
- [ ] T060 [US5] `make test-unit` + `make lint-errors` green; confirm each transition passes strict at 20 fps.

---

## Phase 9: User Story 6 - Class 3 Palette-animated bitmap text (Priority: P2)

**Goal**: The full palette-animation set + a complete font (extends the existing
`BitmapText` + `RainbowChase`). **Independent test**: each effect changes output
with no glyph rebuild; strict-feasible.

- [ ] T061 [P] [US6] Write `test/unit/display/test_bitmap_text.py`: each palette effect changes rendered output with the glyph bitmap object identity unchanged (no rebuild); the expanded font renders all needed glyphs; strict-feasible at 20 fps.
- [ ] T062 [US6] Expand `FONT_5x7` in `src/scrollkit/display/bitmap_text.py` to the full printable ASCII set (A–Z, 0–9, space, common punctuation) as compact `bytes` glyph tables.
- [ ] T063 [US6] Implement `NeonTubeCrawl` palette effect in `bitmap_text.py`: a bright pulse travels through the letters via rotating palette entries (no glyph rebuild).
- [ ] T064 [US6] Implement `ChromeSheen` palette effect: a metallic light gradient sweeps across the ramp.
- [ ] T065 [US6] Implement `HazardStripes` palette effect: alternating warning-stripe colors that march.
- [ ] T066 [US6] Migrate `demos/medium/rainbow.py` and `demos/hard/crypto_dashboard.py` off `EffectsEngine.get_rainbow_color()` to the palette system (so the legacy animation layer can be retired).
- [ ] T067 [US6] `make test-unit` + `make lint-errors` green; confirm each palette effect passes strict at 20 fps.

---

## Phase 10: User Story 7 - Showcase reel + feasibility-tagged docs (Priority: P3)

**Goal**: A scripted reel chaining the signatures + docs that advertise each
effect's hardware budget. **Independent test**: the reel runs strict end-to-end.

- [ ] T068 [US7] Upgrade `demos/hard/showcase.py` to chain the full signature set at readable pacing (e.g. CRT-collapse intro → neon `BitmapText` title → `KineticMarquee` → `IrisSnap` → `WaveRider` → `SplitFlap` → `MosaicResolve` exit), strict-on.
- [ ] T069 [US7] Add advertised feasibility metadata (`hardware_safe`, `allocates_per_frame`, `max_pixel_writes_per_frame`, `modeled_frame_ms`) per showcase effect, and write `docs/guide/{scrolling,transitions,bitmap-text}.md` describing each with its hardware budget.
- [ ] T070 [US7] Verify the whole reel: `run_headless(ShowcaseApp(), frames=600, hardware=True, strict=True).ok is True` end to end; `make test-unit` + `make lint-errors` green.

---

## Deferred (genuinely out of scope)

- **Calibration TODO**: capture `fill_region`/`blit` at 2–3 sizes in `test/claude/device_benchmarks.py` to *fit* `bulk_base_us`/slope rather than estimate (research D6).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)** → no deps.
- **Foundational (T002–T003)** → after Setup; blocks US2/US3 (needs `FeasibilityError`).
- **US1 (T004–T014)** → after Setup. *Independent of US2/US3 code-wise but mandated first by build order.*
- **US2 (T015–T026)** → after Foundational; the strict gate is needed to validate US3's proving spikes.
- **US3 (T027–T046)** → after US2 (proving spikes run under `strict=True`) and after US1 (US3 recreates `effects/transitions.py`, deleted in US1/T006).
- **Polish (T047–T049)** → after US1–US3.

### Critical chain (build order is linear here)

```
T001 → T002 → T003 → US1(T004–T014) → US2(T015–T026) → US3(T027–T046) → Polish(T047–T049)
```

### Within User Story 3 (sub-dependencies)

```
easing (T034) ─────────────┐
shim (T035) → golden fixture (T036, finalized before T030/T046)
gfx+layers: T037 → {T038, T039} → painters/measure_text {T040, T041}
                                   ├→ OverlayMask (T042) → IrisSnap spike (T044, also needs T034)
                                   ├→ ScrollingText (T043)
                                   └→ BitmapText spike (T045)
all impl → verify (T046);  tests T027–T033 written alongside their targets, run at T046
```

### Parallel Opportunities

- US1: T004,T005 (tests) ∥; T006,T007,T008 (deletes, different files) ∥; T010,T011,T012 ∥ (T009 prune and T013 sweep depend on the deletes).
- US2: T015,T016 (tests, different files) ∥; impl T017–T022 are same-file (`performance_manager.py`) except T019 (`hardware_profile.py`) and T022 (`feasibility.py`) → keep the `performance_manager.py` edits sequential; T023,T024,T025 touch different files → ∥ after T017–T022.
- US3: T027–T033 (tests, different files) ∥; T034 (easing) ∥ with the gfx track; T035 (shim) + T036 (golden tool) ∥ with easing (T036 may be authored in parallel, but the committed `bitmaptools_golden.json` fixture must exist before T030/T046 run); T038 (unified) ∥ T039 (simulator) only if different authors — both then feed T040/T041.
- Polish: T047,T048 ∥.

---

## Parallel Example: User Story 1

```bash
# Tests first (different files):
Task: "Write test/unit/effects/test_removal.py"            # T004
Task: "Update test/unit/dev/test_capabilities.py"          # T005

# Then the three file deletions together:
Task: "Delete src/scrollkit/effects/transitions.py"        # T006
Task: "Delete src/scrollkit/effects/reveal.py"             # T007
Task: "Delete src/scrollkit/effects/basic_transitions.py"  # T008
```

## Parallel Example: User Story 3 (tests fan-out)

```bash
Task: "Write test/unit/effects/test_easing.py"             # T027
Task: "Write test/unit/display/test_painters.py"           # T028
Task: "Write test/unit/display/test_layers.py"             # T029
Task: "Write test/unit/display/test_bitmaptools_shim.py"   # T030
Task: "Write test/unit/effects/test_overlay.py"            # T031
Task: "Write test/unit/display/test_scrolling_text.py"     # T032
Task: "Write test/unit/effects/test_proving_spikes.py"     # T033
```

---

## Implementation Strategy

### MVP scope

The MVP for this feature is **US1 + US2 + US3** together — the cohesive foundation
the roadmap mandates be built and reviewed as one piece. US1 alone (an honest
catalog) is the smallest shippable increment, but the strict gate (US2) and the
proven primitives (US3) are what make the foundation usable by the deferred
classes.

### Incremental delivery & checkpoints

1. Setup + Foundational → `FeasibilityError` exists, suite green.
2. US1 → honest catalog, removal asserted + swept → **checkpoint, suite green**.
3. US2 → strict gate bites correctly, breakdown surfaces bulk cost, warning path intact → **checkpoint**.
4. US3 → primitives + proving spikes green under strict → **checkpoint, foundation frozen**.
5. Polish → invariants verified, docs updated, full quickstart green.
6. (Later) US4 → US5 → US6 → US7 as separate features on the frozen foundation.

### Per-task discipline

- After each task or logical group, run `make test-unit` + `make lint-errors`.
- Keep effect hot paths allocation-free and bounded (no full-2048 Python loop).
- If the simulator diverges from device behavior, fix the **simulator** (and the
  shim against the golden corpus), never the shared display logic.

---

## Notes

- `[P]` = different files, no dependency on an incomplete task.
- `[Story]` traces a task to US1/US2/US3.
- Tests are included by project policy (FR-033 + green-every-phase); pin behavior
  from the contracts. `measure_text` tests (T028/T032) use a controlled fake font
  with unequal advances so they cannot pass falsely against a uniform-6px font.
- The two `effects/transitions.py` references are intentional: **deleted in US1
  (T006)**, **recreated fresh in US3 (T044)** — order T006 before T044.
- `bitmaptools_golden.json` is a committed CI fixture; the raw-REPL capture tool
  (T036) is manual calibration, not part of normal test runs.
- Commit after each task or logical group.
