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

**Organization**: Tasks are grouped by user story. Per the plan's *Scope &
sequencing*, this file fully implements **US1, US2, US3 (Phases 1–3)** plus the
per-primitive **proving spikes**. **US4, US5, US6, US7 (Phases 4–7) are deferred**
to their own `/specify` → `/plan` → `/tasks` cycles (see *Deferred work* below) —
they are committed deliverables of the feature, not dropped.

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

- [ ] T001 Confirm clean baseline on branch `002-build-scrollkit-showcase`: run `make test-unit` and `make lint-errors` (Makefile targets at repo root); both MUST be green before any change.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The one shared primitive that US2 and US3 (and their tests) all import.

**⚠️ CRITICAL**: Complete before US2/US3 work begins.

- [ ] T002 Add `class FeasibilityError(SLDKError)` to `src/scrollkit/exceptions.py` (CP-safe class def; imported by the strict gate, the harness, and all strict tests).

**Checkpoint**: `from scrollkit.exceptions import FeasibilityError` works; suite still green.

---

## Phase 3: User Story 1 - Honest effects catalog: remove broken effects (Priority: P1) 🎯 MVP

**Goal**: Delete the broken/fake transition effects and prune the public surface,
leaving an honest catalog while keeping the suite green.

**Independent Test**: Removed names are unimportable and absent from
`capabilities()`; retained `particles` + `EffectsEngine.get_rainbow_color()` still
pass; `make test-unit` + `make lint-errors` green.

### Tests for User Story 1

- [ ] T003 [P] [US1] Write `test/unit/effects/test_removal.py` asserting every FR-001 name (`TransitionEngine`, `BaseTransition`, `FadeTransition`, `WipeTransition`, `SlideTransition`, `RevealEffect`, `RevealCenterEffect`, `FadeInEffect`, `SlideInEffect`, `WipeEffect`, `FlashEffect`, the duplicate `PulseEffect`) raises `ImportError`/`AttributeError` from its old module, is absent from `scrollkit.effects.__all__`, and is absent from `capabilities()`.
- [ ] T004 [P] [US1] Update `test/unit/dev/test_capabilities.py` to drop the `FadeInEffect` (and any other removed-name) expectation.

### Implementation for User Story 1

- [ ] T005 [P] [US1] Delete `src/scrollkit/effects/transitions.py` (the broken `TransitionEngine`/`BaseTransition`/`FadeTransition`/`WipeTransition`/`SlideTransition`). NOTE: a brand-new, unrelated `transitions.py` is created later in US3/Phase 5 — this delete MUST come first.
- [ ] T006 [P] [US1] Delete `src/scrollkit/effects/reveal.py` (`RevealEffect`, `RevealCenterEffect`).
- [ ] T007 [P] [US1] Delete `src/scrollkit/effects/basic_transitions.py` in full (`FadeInEffect`, `SlideInEffect`, `WipeEffect`, `FlashEffect`, duplicate `PulseEffect`).
- [ ] T008 [US1] Prune `src/scrollkit/effects/__init__.py`: remove the `from .basic_transitions import …` and `from .reveal import …` lines and drop `FadeInEffect`, `SlideInEffect`, `WipeEffect`, `RevealEffect` from `__all__` (depends on T005–T007).
- [ ] T009 [P] [US1] Fix `src/scrollkit/content_classes.py` `example_usage()` (≈lines 295–316): remove the import and uses of `RevealEffect`, `FadeInEffect`, and the basic-transitions `PulseEffect`.
- [ ] T010 [P] [US1] Fix the docstring example in `src/scrollkit/display/strategy.py` (≈line 213) that references `RevealEffect`.
- [ ] T011 [P] [US1] Rewrite the "what's available" section of `docs/guide/effects.md` to match the pruned catalog (keep `particles`, `get_rainbow_color()`).
- [ ] T012 [US1] Run `make test-unit` + `make lint-errors`; confirm green, including the retained `test/unit/effects/test_effects_engine.py` and `test/unit/effects/test_particles.py` (depends on T003–T011).

**Checkpoint**: US1 complete — honest catalog, suite green, removal asserted.

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

- [ ] T013 [P] [US2] Add strict-gate cases to `test/unit/simulator/test_hardware_realism.py`: sustained over-budget raises `FeasibilityError`; an isolated single spike does NOT (median tolerates); a catastrophic frame raises (transient ceiling); a RAM breach raises; the `warmup_frames` grace exempts the first frames; and ALL existing warning-path assertions still pass with `strict=False`.
- [ ] T014 [P] [US2] Add strict cases to `test/unit/dev/test_harness.py`: `run_headless(app, hardware=True, strict=True)` over-budget ⇒ `result.ok is False` and an error containing `feasibility`; cheap ⇒ `ok True`; a one-isolated-rebuild app ⇒ `ok True`; `strict=False` behaves exactly as today.

### Implementation for User Story 2

- [ ] T015 [US2] Extend `PerformanceManager.__init__` in `src/scrollkit/simulator/core/performance_manager.py` with `strict=False`, `target_fps=20.0`, `warmup_frames=2`, `gate_window=8`, `transient_factor=2.0`; derive `frame_budget_us = 1_000_000/target_fps` and `transient_budget_us = frame_budget_us*transient_factor`.
- [ ] T016 [US2] Add a `bulk_ops_us` slot to `FrameCost` (`__slots__`, `total_us`, `as_dict()`) in `src/scrollkit/simulator/core/performance_manager.py`.
- [ ] T017 [US2] Add bulk-cost fields to `src/scrollkit/simulator/core/hardware_profile.py`: `bulk_base_us=12.0`, `fill_region_us_per_px=0.287`, `blit_us_per_px=0.623` (defaulted; seeded from `device_benchmarks.json`); load them in the calibrated factory.
- [ ] T018 [US2] Add `account_bulk_op(kind, px)` to `PerformanceManager` in `src/scrollkit/simulator/core/performance_manager.py` (cost `= bulk_base_us + px*slope(kind)`, `px` = clipped pixels) writing to `bulk_ops_us`.
- [ ] T019 [US2] Implement strict enforcement in `PerformanceManager._end_frame()` (`src/scrollkit/simulator/core/performance_manager.py`): after computing `total_us`, when `strict` and `_frame_index >= warmup_frames` → (1) transient ceiling, (2) steady-state median over the last `gate_window` totals vs `frame_budget_us`, (3) RAM vs `usable_ram_bytes`, raising `FeasibilityError` with a descriptive message (frame/window, ms, fps, budget, dominant component). Leave the ambient-warning path untouched when `strict=False`.
- [ ] T020 [US2] Plumb strict into `src/scrollkit/display/simulator.py`: add a `strict=False` keyword to `SimulatorDisplay.__init__` (implies hardware timing) and read `SCROLLKIT_HW_STRICT=1` in `_maybe_enable_hardware_timing()`; pass `strict` into `PerformanceManager`.
- [ ] T021 [US2] Plumb strict into the desktop branch of `UnifiedDisplay._maybe_enable_hardware_timing()` in `src/scrollkit/display/unified.py` (read `SCROLLKIT_HW_STRICT`; document it as a no-op on CircuitPython).
- [ ] T022 [US2] Add `strict=False` to `run_headless` and `run_headless_async` in `src/scrollkit/dev/harness.py`: set/restore `SCROLLKIT_HW_STRICT`, and ensure a `FeasibilityError` raised mid-loop is caught by the existing per-frame `except Exception`, appended to `RunResult.errors` tagged `feasibility:` (so `result.ok` is False; harness does not crash).
- [ ] T023 [US2] Run `make test-unit` + `make lint-errors`; confirm green, including the unchanged warning-path assertions (depends on T013–T022).

**Checkpoint**: US2 complete — the gate bites on sustained/catastrophic frames,
tolerates isolated rebuilds, and the legacy warning path is intact.

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

- [ ] T024 [P] [US3] Write `test/unit/effects/test_easing.py`: pinned endpoints (`ease(c,0)==0`, `ease(c,255)==255`), LUTs are `bytes`, integer returns, determinism, no per-call allocation.
- [ ] T025 [P] [US3] Write `test/unit/display/test_painters.py`: `fill_rect`/`fill_span`/`clear_rect` write only in (clipped) bounds; a 64×32 `clear_rect` takes the bulk path (no full Python loop); `measure_text("HELLO")` matches a rendered Label width (not `5*6`); `measure_text("")==0`; missing-glyph uses the replacement advance; `display.gfx is display.gfx`.
- [ ] T026 [P] [US3] Write `test/unit/display/test_layers.py`: a TileGrid added via `add_layer` survives N `clear()` calls and stays above Labels after the pool grows; `add_layer`/`remove_layer` idempotent.
- [ ] T027 [P] [US3] Write `test/unit/display/test_bitmaptools_shim.py`: replay the golden battery through the shim and assert byte-identical output vs `test/unit/display/bitmaptools_golden.json` (edge clip, negative offset, `skip_index`, zero-area, full-fill).
- [ ] T028 [P] [US3] Write `test/unit/effects/test_overlay.py`: `OverlayMask` allocates once (bitmap/palette object identity stable across many mutations), index 0 transparent, bounded writes.
- [ ] T029 [P] [US3] Write `test/unit/display/test_scrolling_text.py`: at `speed=60` it advances ~2× the px of `speed=30` over equal frames; measured width matches a rendered Label width (not `len*6`); width measured once (not per frame); completes when fully scrolled off; no per-frame allocation.
- [ ] T030 [P] [US3] Write `test/unit/effects/test_proving_spikes.py`: a minimal-`IrisSnap` app and a minimal-`BitmapText`+`RainbowChase` app each pass `run_headless(frames=120, hardware=True, strict=True)` with `ok is True`/`advanced is True`; assert `IrisSnap` follows cover→swap-while-covered→reveal (content hidden at peak cover); assert `BitmapText` palette rotation changes output with the glyph bitmap object identity unchanged (no rebuild).

### Implementation for User Story 3

- [ ] T031 [P] [US3] Implement `src/scrollkit/effects/easing.py`: curve ids (`LINEAR`, `EASE_OUT_QUAD`, `EASE_IN_OUT`, `OVERSHOOT`, `BOUNCE`, `ELASTIC`), six length-256 `bytes` LUTs built once at import, `ease(curve, p)->int`, `interp(curve, a, b, p)->int`; CP-safe (no `typing`, no numpy).
- [ ] T032 [US3] Implement the simulator shim `src/scrollkit/simulator/bitmaptools.py`: `fill_region(bitmap, x1, y1, x2, y2, value)` (half-open `[x1,x2)×[y1,y2)`, clipped) and `blit(dest, source, x, y, *, x1=0, y1=0, x2=None, y2=None, skip_index=None)` (sub-rect, `skip_index` transparency, four-edge + negative-offset clipping, empty/clipped ⇒ no-op) on the numpy-backed sim `Bitmap`.
- [ ] T033 [P] [US3] Add the host-side capture tool `test/claude/bitmaptools_golden.py` (raw-REPL via `test/claude/cpy_repl.py`; writes nothing to the board) that runs the fixed battery on real CircuitPython and emits `test/unit/display/bitmaptools_golden.json`; commit a once-captured golden file (recapture is the calibration step).
- [ ] T034 [US3] Add to `src/scrollkit/display/interface.py` the abstract surface: `fill_rect`/`fill_span`/`clear_rect` (async), `measure_text(text, font=None)` (sync), the cached `gfx` property contract, and `add_layer`/`remove_layer` (a plain attribute-holder for `gfx`, no `typing`/`SimpleNamespace`).
- [ ] T035 [US3] Restructure `main_group` in `src/scrollkit/display/unified.py` into `_content_group` (below) + `_layer_group` (above); build a cached `gfx` (real `displayio`/`bitmaptools`) once in `initialize()`; implement `add_layer`/`remove_layer`; route the label pool + `fill()` background into `_content_group[0]`; make `clear()` reset the pool in `_content_group` only and never touch `_layer_group`.
- [ ] T036 [US3] Apply the identical `_content_group`/`_layer_group` restructure + cached `gfx` (sim `displayio` + the shim) + `add_layer`/`remove_layer` in `src/scrollkit/display/simulator.py` (dev==hardware parity; fix the simulator, not shared logic).
- [ ] T037 [US3] Implement the painters + `measure_text` in `src/scrollkit/display/unified.py`: `fill_rect`/`fill_span`/`clear_rect` via `gfx.bitmaptools.fill_region` (clipped bounds; call `account_bulk_op`; tiny-region fallback only, never a full loop); `measure_text` summing font glyph advances (empty ⇒ 0; missing glyph ⇒ replacement advance), no hot-path fallback (depends on T034, T035).
- [ ] T038 [US3] Implement the same painters + `measure_text` in `src/scrollkit/display/simulator.py` using the shim (depends on T032, T036).
- [ ] T039 [US3] Implement `src/scrollkit/effects/overlay.py` `OverlayMask`: allocate-once indexed `gfx.Bitmap` + `gfx.Palette` (index 0 transparent) + `gfx.TileGrid` added via `display.add_layer`; bounded mutators (`fill_rect`/`fill_span`/`clear`/`clear_rect`/`blit_pattern`) via `gfx.bitmaptools`; `set_cover_color`/`detach` (depends on T035–T038).
- [ ] T040 [US3] Rewrite `ScrollingText` in `src/scrollkit/display/content.py`: module `LOOP_FPS = 20`; fixed-point `_pos_q` (1/16 px), `_pos_q -= round(speed*16/LOOP_FPS)`, render `x = _pos_q >> 4`; `_measured_width` via `display.measure_text` computed once at `start()`/first render and cached; complete when `(_pos_q>>4) < -_measured_width`; keep the ctor signature and `describe()` keys (depends on T037/T038).
- [ ] T041 [US3] Create the FRESH `src/scrollkit/effects/transitions.py` with a `Transition` base (cover → `swap_callback` while covered → reveal, `progress` via `easing`, `is_complete`) and a minimal `IrisSnap` — the proving consumer for `gfx`/`add_layer`/`OverlayMask`/`easing` (depends on T031, T039). NOTE: this is the new file; the old one was deleted in T005.
- [ ] T042 [US3] Create `src/scrollkit/display/bitmap_text.py` with a compact 5×7 `bytes` glyph subset (enough for the proving message), `BitmapText` (render once into an indexed `gfx.Bitmap`, scroll via `TileGrid.x`, attach via `add_layer`, documented `max_width_px`) and a minimal `RainbowChase` palette effect — the proving consumer for `gfx`/`add_layer`/palette (depends on T035–T038).
- [ ] T043 [US3] Run `make test-unit` + `make lint-errors` and the quickstart Phase 3 validations; confirm green and that both proving spikes pass strict at 20 fps (depends on T024–T042).

**Checkpoint**: US3 complete — the foundation API is proven by real consumers and
frozen; Phases 4–6 can build on it.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Verify invariants and wrap up the committed scope.

- [ ] T044 [P] Confirm `scrollkit.dev` import-safety: `test/unit/dev/test_dev_import_safety.py` still green, and the top-level `scrollkit/__init__` + `app/` + core `display/` import path never pulls in `numpy`/`pygame`/the simulator `bitmaptools` (effects subsystem stays optional).
- [ ] T045 [P] Update `docs/guide/effects.md` (and add a short foundation note) describing the strict feasibility gate, easing, painters, the overlay-mask, and the `gfx`/layer model, each with its hardware-budget framing.
- [ ] T046 Run the full quickstart.md Phases 1–3 validation end-to-end (including the negative control and the isolated-rebuild-passes case) and the whole suite: `make test-unit` + `make lint-errors` green.

---

## Deferred work (own spec-kit features — NOT in this tasks.md)

Per the plan's *Scope & sequencing*, these remain committed deliverables of the
feature but get their own `/specify` → `/plan` → `/tasks`, building on the proven
foundation:

- **US4 / Phase 4 — Class 1 (full)**: `KineticMarquee`, `WaveRider`, `SplitFlap` in `src/scrollkit/effects/scrolling.py` (+ tests).
- **US5 / Phase 5 — Class 2 (full)**: the remaining transitions (`VenetianShutters`, `MosaicResolve`, `CRTCollapse`, `LightSlitRewrite`) added to `src/scrollkit/effects/transitions.py` beyond the `IrisSnap` spike (+ tests).
- **US6 / Phase 6 — Class 3 (full)**: the full 5×7 font, the remaining palette effects (`NeonTubeCrawl`, `ChromeSheen`, `HazardStripes`) in `src/scrollkit/display/bitmap_text.py`; migrate `demos/medium/rainbow.py` + `demos/hard/crypto_dashboard.py` off `get_rainbow_color()` (+ tests).
- **US7 / Phase 7 — Demo reel + docs**: `demos/hard/showcase.py`, per-effect docs pages with feasibility metadata (`hardware_safe`, `allocates_per_frame`, `max_pixel_writes_per_frame`, `modeled_frame_ms`).
- **Calibration TODO**: capture `fill_region`/`blit` at 2–3 sizes in `test/claude/device_benchmarks.py` to *fit* `bulk_base_us`/slope rather than estimate (research D6).

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (T001)** → no deps.
- **Foundational (T002)** → after Setup; blocks US2/US3.
- **US1 (T003–T012)** → after Setup. *Independent of US2/US3 code-wise but mandated first by build order.*
- **US2 (T013–T023)** → after Foundational (needs `FeasibilityError`); the strict gate is needed to validate US3's proving spikes.
- **US3 (T024–T043)** → after US2 (proving spikes run under `strict=True`) and after US1 (US3 recreates `effects/transitions.py`, deleted in US1).
- **Polish (T044–T046)** → after US1–US3.

### Critical chain (build order is linear here)

```
T001 → T002 → US1(T003–T012) → US2(T013–T023) → US3(T024–T043) → Polish(T044–T046)
```

### Within User Story 3 (sub-dependencies)

```
easing (T031) ─────────────┐
shim (T032) → golden (T033)┤
gfx+layers: T034 → {T035, T036} → painters/measure_text {T037, T038}
                                   ├→ OverlayMask (T039) → IrisSnap spike (T041, also needs T031)
                                   ├→ ScrollingText (T040)
                                   └→ BitmapText spike (T042)
all impl → verify (T043);  tests T024–T030 written alongside their targets, run at T043
```

### Parallel Opportunities

- US1: T003,T004 (tests) ∥; T005,T006,T007 (deletes, different files) ∥; T009,T010,T011 ∥.
- US2: T013,T014 (tests, different files) ∥; impl T015–T019 are same-file (`performance_manager.py`) → sequential; T020,T021,T022 touch different files → ∥ after T015–T019.
- US3: T024–T030 (tests, different files) ∥; T031 (easing) ∥ with the gfx track; T032/T033 ∥ with easing; T035 (unified) ∥ T036 (simulator) only if different authors — both then feed T037/T038.
- Polish: T044,T045 ∥.

---

## Parallel Example: User Story 1

```bash
# Tests first (different files):
Task: "Write test/unit/effects/test_removal.py"            # T003
Task: "Update test/unit/dev/test_capabilities.py"          # T004

# Then the three file deletions together:
Task: "Delete src/scrollkit/effects/transitions.py"        # T005
Task: "Delete src/scrollkit/effects/reveal.py"             # T006
Task: "Delete src/scrollkit/effects/basic_transitions.py"  # T007
```

## Parallel Example: User Story 3 (tests fan-out)

```bash
Task: "Write test/unit/effects/test_easing.py"             # T024
Task: "Write test/unit/display/test_painters.py"           # T025
Task: "Write test/unit/display/test_layers.py"             # T026
Task: "Write test/unit/display/test_bitmaptools_shim.py"   # T027
Task: "Write test/unit/effects/test_overlay.py"            # T028
Task: "Write test/unit/display/test_scrolling_text.py"     # T029
Task: "Write test/unit/effects/test_proving_spikes.py"     # T030
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
2. US1 → honest catalog, removal asserted → **checkpoint, suite green**.
3. US2 → strict gate bites correctly, warning path intact → **checkpoint**.
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
  from the contracts.
- The two `effects/transitions.py` references are intentional: **deleted in US1
  (T005)**, **recreated fresh in US3 (T041)** — order T005 before T041.
- Commit after each task or logical group.
