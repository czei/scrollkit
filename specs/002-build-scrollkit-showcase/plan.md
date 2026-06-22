# Implementation Plan: ScrollKit Showcase Effects

**Branch**: `002-build-scrollkit-showcase` | **Date**: 2026-06-20 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `specs/002-build-scrollkit-showcase/spec.md`

**Roadmap (provenance)**: `/Users/czei/.claude/plans/this-library-needs-to-serene-parasol.md`
— a local, non-repo-tracked file. Its normative constraints have been **mirrored
into this repo-tracked spec/plan/research/data-model/contracts**, which are
self-contained; the absolute path is kept only as the idea's provenance, not as a
build-time dependency (PAL N2).

## Summary

Turn ScrollKit from a thin `displayio` wrapper into a **zero-allocation micro-show
engine** for the 64×32 LED panel. Remove the broken/fake effects, add a **strict
hardware-feasibility gate** (sustained over-budget ⇒ `FeasibilityError`: a
steady-state **median** over a rolling window must hold ~20 fps / 50 ms, plus a
single-frame **transient ceiling** at ~10 fps so a legitimate isolated glyph
rebuild doesn't false-trip — see [research.md](./research.md) D1), build a small
set of **shared primitives** (integer easing LUTs, bounded span/rect painters over
C bulk ops, a preallocated overlay-mask layer, and a fixed-point `ScrollingText`),
then deliver three signature effect classes (characterful scrolling, theatrical
transitions, palette-animated bitmap text) and a showcase demo reel +
feasibility-tagged docs. The single hard rule
overriding everything: the *same source runs unchanged* on the CircuitPython
MatrixPortal S3 and the desktop pygame simulator, with no per-frame heap
allocation and no per-pixel Python loop over all 2048 pixels.

**Technical approach**: the per-frame cost/RAM model already exists
(`PerformanceManager` + the calibrated `matrixportal_s3_baseline.json`); we add a
`strict` flag that raises in `_end_frame()`. The simulator already emulates
`displayio` (Bitmap/Palette/TileGrid/Group) but **not** `bitmaptools` — so the
foundation adds a faithful simulator `bitmaptools` shim (`fill_region`, `blit`)
and a tiny platform-resolving graphics accessor on the display, so painters,
overlay-mask, and bitmap-text express bulk C work through one code path on both
platforms. The three classes then build on that foundation.

## Scope & sequencing (umbrella feature)

The roadmap recommends Phases 1–3 (removal + strict gate + shared primitives) be
built and reviewed **together** as one cohesive deliverable, and that Phases 4–6
(the three classes) each become their **own** spec-kit feature on top of that
shared base. This plan honors that:

- **Designed in full here**: Phase 1 (removal), Phase 2 (strict gate), Phase 3
  (foundation). These are the binding decisions — the gate everything is
  validated against and the primitives the classes share. `/tasks` for this
  feature fully implements Phases 1–3.
- **Foundation must be PROVEN, not just shipped (addresses PAL B4)**: the spec
  marks Class 1/2/3 + demo/docs as **MUST** (FR-016…FR-026, SC-002/008). Those
  remain committed deliverables of the feature, delivered via per-class
  sub-features — they are **deferred, not dropped** (tracked in
  [research.md](./research.md) Open risks). To stop Phase 3 from freezing an
  unproven, abstract API, Phase 3 is **not "done" until one thin vertical proving
  consumer per primitive is green under strict**:
  - `measure_text` + `easing` → exercised by the fixed-point `ScrollingText` (D8).
  - `gfx` + `add_layer` + `OverlayMask` → one minimal Class 2 transition
    (`IrisSnap`) doing a real cover→swap→reveal.
  - `gfx` + `add_layer` + palette → one minimal `BitmapText` (single message, one
    palette effect, e.g. `RainbowChase`).
  These "proving spikes" are the smallest real consumers that validate the
  `gfx`/`add_layer`/`OverlayMask`/`measure_text` contracts before they are frozen;
  the **full** Class 1/2/3 effect sets land in their sub-features. If a spike
  surfaces a missing affordance, the foundation API is fixed here (cheap) rather
  than via a breaking change later.
- **Specified at the contract level here**: Phases 4–6 public APIs and feasibility
  budgets, plus Phase 7 (demo reel + docs). The contracts/ here fix the
  interfaces so the three classes don't reinvent masks/easing; each class then
  gets its own `/specify` → `/plan` → `/tasks` cycle for the remaining per-effect
  work.

## Technical Context

**Language/Version**: Python 3.11 (desktop) **and** CircuitPython 8.x/9.x (device).
All new library code must live in the *intersection* — no `typing` at runtime, no
`enum.auto()`, `ValueError` (not `json.JSONDecodeError`), `OSError` (not
`FileNotFoundError`), `time.monotonic()` (not `time.time()`), no `match`/`case`,
no f-string `=` debug. (CLAUDE.md compatibility table.)

**Primary Dependencies**:
- Device: `displayio`, `bitmaptools`, `adafruit_display_text.label`, `terminalio`,
  `adafruit_matrixportal.matrix`, `asyncio` (CircuitPython subset).
- Simulator (desktop-only, under `scrollkit/simulator/`): `pygame`, `numpy`, an
  emulated `displayio` package, and a **new** emulated `bitmaptools` module.
- Dev/verification (`scrollkit.dev`, desktop-only): numpy/pygame; raises
  `ImportError` on CircuitPython.

**Storage**: JSON calibration files shipped in-tree —
`simulator/core/matrixportal_s3_baseline.json` (device profile) and
`device_benchmarks.json` (per-op microbenchmarks). No DB. Read-only here.

**Testing**: `pytest`, headless/simulator-based. Gates: `make test-unit` and
`make lint-errors` (ruff critical-errors). Run with
`PYTHONSAFEPATH=1 PYTHONPATH=src`. Per-effect tests assert lit pixels advance,
animation advances frame-to-frame, no per-frame allocation, and strict feasibility.

**Target Platform**: Adafruit MatrixPortal S3, 64×32 RGB LED matrix
(CircuitPython 9.x), plus desktop pygame simulator (macOS/Linux).

**Project Type**: Single library (`src/scrollkit/`). No web/mobile split.

**Performance Goals** (calibrated, from the baseline + benchmarks):
- Target **20 fps ⇒ 50 ms (50 000 µs) per-frame budget**.
- `display.refresh()` at **bit_depth=4** ≈ **4 492 µs**/frame (≈4.5 ms); bit_depth 6
  ≈ 13 691 µs (~3×) — keep **bit_depth=4**.
- Dominant cost is **Label glyph rebuild ≈ 16.53 µs/px** (a full 64×32 rebuild ≈
  33.9 ms — two per frame busts budget): so reuse Labels, never rebuild per frame.
- Bulk C ops are cheap: `bitmaptools.fill_region` ≈ 147 µs/512 px,
  `bitmaptools.blit` ≈ 160 µs/256 px, `draw_line` ≈ 30 µs — the sanctioned tools.

**Constraints**:
- **No per-frame heap allocation** on any effect hot path.
- **No per-pixel Python loop over all 2048 pixels** — bounded work via the
  C-bulk-backed painters/blit only.
- **bit_depth=4**, **async-only** (cooperative; never block the display loop).
- Usable device RAM ≈ **2 073 536 bytes** (`usable_ram_bytes`); modeled peak RAM
  must stay under it.
- One shared display implementation: if the simulator diverges from reported
  hardware, fix the **simulator**, never the shared display logic.

**Scale/Scope**: ~12 new effects across 3 classes + a 4-piece foundation; roughly
8–12 new modules and edits to ~8 existing files. Removal touches `effects/` plus
a handful of import sites and one capabilities test.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

The project constitution at `.specify/memory/constitution.md` is an **unpopulated
template** (placeholder tokens only) — it has not been ratified. There are
therefore no formal numbered gates to evaluate. Per the spec-kit "ERROR on gate
failure" rule, this is **not** a failure: there are no constraints to violate.

In its place, this plan adopts the project's **working principles from CLAUDE.md**
as the de-facto gates. The design is checked against each:

| De-facto gate (CLAUDE.md) | Status | How the design complies |
|---|---|---|
| CircuitPython 8.x/9.x compatibility | ✅ PASS | All new library code uses only intersection features; `scrollkit.dev` and `scrollkit/simulator/*` stay desktop-only (the new `bitmaptools` shim lives under `simulator/`, never imported on device — device uses the built-in). |
| One display: dev == hardware | ✅ PASS | Painters/overlay/bitmap-text run one code path; platform difference is isolated to *which* `displayio`/`bitmaptools` module the display resolves. Simulator gets a faithful `bitmaptools` shim so behavior matches device; divergences are fixed in the simulator. |
| No per-frame heap allocation | ✅ PASS | Easing LUTs precomputed once; overlay bitmap/palette allocated once and reused; Label pool reused; tests assert no per-frame alloc. |
| Use C bulk ops, not per-pixel Python loops | ✅ PASS | `fill_rect`/`fill_span`/overlay blit back onto `bitmaptools.fill_region`/`blit`; the "no full-2048 loop" rule is encoded as FR-029 and tested. |
| bit_depth=4 | ✅ PASS | Default retained; budget derived from the bit_depth-4 refresh cost. |
| Async-only, cooperative | ✅ PASS | Effects render inside the existing async display loop; no threads. |
| Effects subsystem stays optional | ✅ PASS | Removal only prunes effects; core (`app/`, `display/`, top-level `__init__`) gains no hard dependency on `effects/`. New painters live on the display interface (core), overlay/transitions/easing live under `effects/` (optional). |
| Web server never mutates the queue | ✅ N/A | This feature does not touch the web server or queue ownership. |
| `make test-unit` + `make lint-errors` green every phase | ✅ PASS | Encoded as FR-033 / SC-001; each phase ends on green. |

**Result: formal constitution unavailable** (placeholder template, not ratified);
**evaluated against the CLAUDE.md working principles — PASS on every gate above,
with explicit open risks tracked** (not a clean unconditional PASS). The open
risks are the three the PAL `after_plan` review pressed on and that this plan
mitigates but cannot fully close before implementation — see
[research.md](./research.md) **Open risks**:

1. **Shim fidelity** (D5): the dev==hardware guarantee rests on the simulator
   `bitmaptools` shim matching the device; mitigated by a golden-corpus conformance
   test, residual until the golden is (re)captured on a real board.
2. **Strict false-trips** (D1): the gate's window/ceiling defaults are judgment
   calls; mitigated by the median window + transient ceiling + covered-swap rule,
   tunable via ctor params.
3. **Simulator-first verification**: feasibility is modeled, not measured per
   effect on device (only the BASIC path is device-verified today).

No unjustified *violations* exist (Complexity Tracking left empty); the items above
are tracked risks, not gate failures.

> Recommendation (non-blocking): ratify a real constitution via
> `/speckit.constitution` so future features have explicit gates instead of
> CLAUDE.md-derived ones.

## Project Structure

### Documentation (this feature)

```text
specs/002-build-scrollkit-showcase/
├── plan.md              # This file
├── spec.md              # Feature spec (already written)
├── research.md          # Phase 0 output — design decisions
├── data-model.md        # Phase 1 output — entities & state
├── quickstart.md        # Phase 1 output — how to validate
└── contracts/           # Phase 1 output — public-API contracts
    ├── README.md
    ├── feasibility-gate.md      # Phases 1–2: removal + strict gate
    ├── foundation-primitives.md # Phase 3: easing, painters, overlay, scroll
    └── showcase-effects.md      # Phases 4–6 class APIs + Phase 7 demo/docs
```

### Source Code (repository root)

Concrete layout — files this feature creates (＋) or modifies (~):

```text
src/scrollkit/
├── exceptions.py                       ~ add FeasibilityError(SLDKError)            [P2]
├── effects/
│   ├── __init__.py                     ~ prune __all__ + dead imports              [P1]
│   ├── transitions.py                  ✗ DELETE the broken file                    [P1]
│   │                                     ＋ later a FRESH, unrelated file is
│   │                                       created here for Class 2                [P5]
│   ├── reveal.py                       ✗ delete                                    [P1]
│   ├── basic_transitions.py            ✗ delete whole file (all 5 classes)         [P1]
│   ├── effects.py                      ~ keep EffectsEngine (remove only dead note)[P1]
│   ├── particles.py                    (unchanged — retained)
│   ├── easing.py                       ＋ integer easing LUTs (bytes)              [P3]
│   ├── overlay.py                      ＋ preallocated overlay-mask layer          [P3]
│   ├── scrolling.py                    ＋ Class 1: marquee/wave-rider/split-flap   [P4]
│   └── transitions.py                  ＋ Class 2 (fresh; see DELETE above)        [P5]
├── display/
│   ├── interface.py                    ~ add fill_rect/fill_span/clear_rect/
│   │                                     measure_text + gfx (cached) + add_layer   [P3]
│   ├── unified.py                      ~ painters + cached gfx (device builtins) +
│   │                                     _content_group/_layer_group + HW_STRICT   [P3]
│   ├── simulator.py                    ~ painters + cached gfx (sim modules) +
│   │                                     _content_group/_layer_group + strict      [P3]
│   ├── content.py                      ~ fix ScrollingText (fixed-point + measured)[P3]
│   ├── bitmap_text.py                  ＋ Class 3: BitmapText + 5×7 bytes font      [P6]
│   ├── enhanced_content.py             (unchanged — uses retained classes)
│   └── strategy.py                     ~ fix docstring example (RevealEffect)      [P1]
├── content_classes.py                  ~ remove example_usage imports of deleted   [P1]
└── simulator/
    ├── bitmaptools.py                  ＋ emulated fill_region/blit — desktop only [P3]
    └── core/
        ├── performance_manager.py      ~ strict gate (median+ceiling+RAM) +
        │                                 bulk_ops_us + account_bulk_op             [P2/P3]
        └── hardware_profile.py         ~ bulk_base_us / *_us_per_px fields         [P3]

src/scrollkit/dev/
├── harness.py                          ~ run_headless(strict=...) → FeasibilityError→errors [P2]
└── capabilities.py                     (unchanged — auto-prunes via effects.__all__)

test/unit/
├── simulator/test_hardware_realism.py  ~ add strict-gate cases (warning path unchanged) [P2]
├── dev/test_harness.py                 ~ add strict run_headless cases             [P2]
├── dev/test_capabilities.py            ~ drop removed names; assert FR-001 gone    [P1]
├── effects/test_removal.py             ＋ assert every removed name unimportable   [P1]
├── effects/test_easing.py              ＋ easing LUT tests                         [P3]
├── effects/test_overlay.py             ＋ overlay-mask (single-alloc) tests        [P3]
├── display/test_painters.py            ＋ painters + measure_text + gfx-identity   [P3]
├── display/test_layers.py              ＋ _layer_group survives clear(); z-order   [P3]
├── display/test_bitmaptools_shim.py    ＋ shim vs golden corpus                    [P3]
├── display/bitmaptools_golden.json     ＋ device-captured golden output (corpus)   [P3]
├── display/test_scrolling_text.py      ＋ ScrollingText speed/width tests          [P3]
├── effects/test_proving_spikes.py      ＋ IrisSnap + minimal BitmapText proving    [P3]
├── effects/test_scrolling_effects.py   ＋ Class 1 tests                            [P4]
├── effects/test_transitions.py         ＋ Class 2 tests                            [P5]
└── display/test_bitmap_text.py         ＋ Class 3 tests                            [P6]

test/claude/
└── bitmaptools_golden.py               ＋ host-side device capture (raw-REPL)      [P3]

demos/
└── hard/showcase.py (or demos/showcase/) ＋ scripted demo reel                     [P7]

docs/guide/
├── effects.md                          ~ rewrite "what's available"               [P1/P7]
├── scrolling.md / transitions.md / bitmap-text.md ＋ per-effect pages w/ budgets   [P7]
```

`[P#]` = the phase that does the work. Note the **two** `effects/transitions.py`
lines: Phase 1 deletes the broken file; Phase 5 creates a brand-new unrelated file
at the same path. `/tasks` must order the P1 delete strictly before the P5 create
(they are four phases apart — not a same-phase conflict).

**Structure Decision**: Single-library layout (Option 1). New display-facing
primitives (painters, `gfx`, `add_layer`, `measure_text`) go on the **core**
`DisplayInterface` so any content can use them without importing `effects/`;
visual effects and the overlay-mask live under the **optional** `effects/`
subsystem; the bitmap-text content type lives under `display/` (it is a content
type, not an effect). The simulator `bitmaptools` shim lives under
`simulator/` so it can never load on device. The display's `main_group` gains an
explicit `_content_group` (below) / `_layer_group` (above) split (D11) so
persistent effect layers keep a stable z-order across the per-frame `clear()`.

## Phase 0 — Outline & Research

See [research.md](./research.md). Key decisions resolved there (no open
NEEDS CLARIFICATION); D1/D5/D6/D8/D11 were tightened by the `after_plan` PAL
review and an **Open risks** table carries the residuals:

1. **D1** — strict gate: steady-state **median** over a rolling `gate_window` (8)
   + a single-frame **transient ceiling** (2× budget) + a `warmup_frames` (2)
   grace, raising in `_end_frame()`. Tolerates a legitimate isolated rebuild spike;
   still fails on sustained over-budget. Paired with a **covered-swap rule** (swaps
   that rebuild a Label happen behind the overlay).
2. **D5** — the simulator **`bitmaptools` shim** + a **cached** platform-resolving
   **`gfx`** accessor as the dev==hardware bridge, with a **golden-corpus
   conformance test** pinning the shim to real-device output.
3. **D6** — bulk-op cost = `base + px·slope` (conservative base; clipped px) so
   the gate counts painter work and per-call overhead, biased safe.
4. **D7** — overlay-mask layer (one indexed Bitmap, transparent index 0, TileGrid
   in the layer group, dirty-span updates only).
5. **D8** — fixed-point `ScrollingText` (1/16-px accumulator, `LOOP_FPS=20`) and
   `measure_text` via font glyph advances (not `len*6`), measured once off the hot
   path, with a defined font/empty/missing-glyph contract.
6. **D4 / D3** — `FeasibilityError(SLDKError)` in core `exceptions.py`; strict is a
   sim-only concept; default off at `PerformanceManager`, on at showcase entry
   points / new tests; `SCROLLKIT_HW_STRICT` env toggle (device no-op).
7. **D11** — display group ownership: `_content_group` (Labels/fill) below,
   `_layer_group` (effect layers) above; `clear()` never touches layers — stable
   z-order vs the per-frame label-pool reset.

## Phase 1 — Design & Contracts

- **Data model**: [data-model.md](./data-model.md) — entities, fields, state
  transitions, and feasibility metadata.
- **Contracts**: [contracts/](./contracts/) — public-API contracts for the
  feasibility gate, foundation primitives, and the three classes + demo/docs.
- **Quickstart**: [quickstart.md](./quickstart.md) — runnable validation per phase.
- **Agent context**: the `<!-- SPECKIT START/END -->` block in
  `/Users/czei/Documents/Projects/ScrollKit/ScrollKit Library/CLAUDE.md` is
  updated to point at this plan.

## Complexity Tracking

> No Constitution violations to justify — section intentionally empty.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |
