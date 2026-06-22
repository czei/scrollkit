# Feature Specification: ScrollKit Showcase Effects

**Feature Branch**: `002-build-scrollkit-showcase`

**Created**: 2026-06-20

**Status**: Draft

**Input**: User description: "Build the ScrollKit Showcase Effects feature: turn ScrollKit from a thin wrapper over displayio into a 'zero-allocation micro-show engine' for the 64×32 LED panel. Same code must run unchanged on the CircuitPython MatrixPortal S3 and the desktop pygame simulator. Remove old/broken effects; add a strict hardware-feasibility gate; build shared foundational primitives; Class 1 characterful scrolling; Class 2 theatrical transitions; Class 3 palette-animated bitmap text; showcase demo reel + docs."

> **Source of truth**: the detailed roadmap (rationale, file-level targets, dependency
> maps) lives at `/Users/czei/.claude/plans/this-library-needs-to-serene-parasol.md`.
> This specification captures the *what* and *why* and the testable acceptance
> criteria; the roadmap and the forthcoming `/plan` carry the *how*.

## Overview

ScrollKit today is essentially a convenience wrapper over `displayio` +
`adafruit_display_text`. Several of its "showcase" effects are broken or fake
(wipe/slide loop over all 2048 pixels in Python and only render a placeholder
gradient; fade sets a `brightness` attribute that does not exist on
`UnifiedDisplay`; `ScrollingText` ignores its `speed` parameter and estimates
text width as `len(text) * 6`).

This feature reframes ScrollKit as a **zero-allocation micro-show engine for
64×32 panels**: motion that *looks* expensive but costs almost nothing per
frame — move objects, swap palettes, paint tiny masks; never repaint all 2048
pixels in Python and never allocate per frame. It delivers three "wow" classes
of effects (characterful scrolling, theatrical transitions, palette-animated
bitmap text) on top of a small set of shared primitives, all gated by a strict
hardware-feasibility mode so every showcase effect is provably real-device-safe.

The single most important constraint: **the same source must run unchanged on
the CircuitPython MatrixPortal S3 and on the desktop pygame simulator.**

## User Scenarios & Testing *(mandatory)*

> Stories are ordered to match the mandated build sequence (each phase builds on
> the previous). Priority reflects both delivery dependency and value: the
> foundation and safety net (P1) must land before the payoff classes (P2), and
> the demo reel (P3) is the final advertisement. Class 3 (palette-animated bitmap
> text) is called out as the headline differentiator even though it ships last.

### User Story 1 - Honest effects catalog: remove broken/fake effects (Priority: P1)

A developer browsing ScrollKit's effects expects every advertised effect to
actually work on the real device. Today the catalog lists transitions that loop
over all pixels in Python, render placeholder rectangles, or rely on a missing
`brightness` attribute. This story removes the broken/dead/untested
message-to-message effects that the new system replaces, leaving a smaller,
honest catalog.

**Why this priority**: Mandated as the first build step. The effects subsystem
is entirely optional (the core library has no dependency on it), so the broken
effects can be removed without touching core behavior — and shipping the new
system on top of dead code would be misleading. Must be green before any later
work begins.

**Independent Test**: Confirm the removed classes are no longer importable, no
longer appear in the `capabilities()` catalog, and that `make test-unit` and
`make lint-errors` stay green. The retained items (`particles`,
`EffectsEngine.get_rainbow_color()`) still import and pass their existing tests.

**Acceptance Scenarios**:

1. **Given** the effects subsystem, **When** the broken transition effects
   (wipe, slide, reveal, fade, the basic-transition pack, and the dead duplicate
   pulse) are removed, **Then** importing the package and running the full unit
   suite both succeed with no references to the removed names.
2. **Given** the `capabilities()` introspection catalog, **When** an effect is
   removed from `effects.__all__`, **Then** that effect no longer appears in the
   catalog (no manual catalog edit needed).
3. **Given** demos and tests that still use `EffectsEngine.get_rainbow_color()`
   and the particle engine, **When** removal is complete, **Then** those demos
   and tests still pass unchanged (these are retired later, after Class 3 lands).

---

### User Story 2 - Strict hardware-feasibility gate (Priority: P1)

A developer wants a guarantee that an effect that looks great at desktop speed
will not crawl on the ~100×-slower device. With hardware simulation enabled in
**strict** mode, any effect whose modeled per-frame cost exceeds the real-device
budget (~20 fps / 50 ms per frame, calibrated from the device baseline) *fails
loudly* instead of silently warning.

**Why this priority**: This is the safety net that makes every later "showcase"
claim provable. Without it, "real-device-safe" is an unverifiable promise. It is
self-contained and testable in isolation, before any new effect exists.

**Independent Test**: Run an intentionally over-budget effect through the
headless verification harness with hardware simulation + strict mode and confirm
it surfaces a feasibility failure (run is not OK); run a cheap effect and confirm
it passes; confirm existing warning-only tests are unaffected.

**Acceptance Scenarios**:

1. **Given** hardware simulation is on and strict mode is enabled, **When** a
   frame's modeled cost exceeds the per-frame budget (or peak RAM exceeds the
   device's usable RAM), **Then** a `FeasibilityError` is raised at frame end.
2. **Given** strict mode is enabled via the environment toggle, **When** a
   `SimulatorDisplay`/`UnifiedDisplay` is constructed, **Then** it honors that
   toggle without any code change to the app.
3. **Given** the existing warning-based hardware-realism tests, **When** strict
   mode defaults to off at the low level, **Then** those tests pass unchanged.
4. **Given** the new showcase entry points (demo reel and new effect tests),
   **When** they construct the display/harness, **Then** strict mode is on by
   default.
5. **Given** the headless harness runs a strict effect that busts the budget,
   **When** the run completes, **Then** the failure is surfaced in the run result
   (run reports not-OK) rather than crashing the harness.

---

### User Story 3 - Foundational primitives & working scroll speed (Priority: P1)

A developer building any new effect needs cheap, bounded building blocks and a
scroll engine whose `speed` actually controls motion. This story delivers the
shared substrate: integer easing/tween lookup tables, bounded span/rect painters
backed by C bulk operations, a preallocated reusable overlay-mask layer, and a
fix so `ScrollingText` speed drives sub-pixel motion and text width is measured
rather than estimated.

**Why this priority**: All three "wow" classes depend on these primitives, and
the scroll fix is a user-visible bug fix on its own. Designing them once here
prevents each class from reinventing masks/easing inconsistently.

**Independent Test**: Unit-test each primitive in isolation — easing returns
expected integer values across curves; span/rect painters write only inside
their bounds and use bulk ops; the overlay mask is allocated once and reused; a
`ScrollingText` at speed N advances N× faster than at speed 1, and its measured
width matches the rendered glyph width (not `len(text) * 6`).

**Acceptance Scenarios**:

1. **Given** the easing engine, **When** an effect requests `ease(curve,
   progress)` on the hot path, **Then** it returns a precomputed integer (0–255)
   with no floating-point math and no per-call allocation.
2. **Given** the span/rect painters, **When** an effect fills a bounded region,
   **Then** only pixels inside that region change and the implementation uses a
   bulk fill/blit (never a full 2048-pixel Python loop).
3. **Given** the overlay-mask layer, **When** an effect updates the mask across
   many frames, **Then** the underlying bitmap is allocated exactly once and only
   dirty spans are rewritten.
4. **Given** a `ScrollingText` with a configurable speed, **When** speed is
   increased, **Then** the rendered horizontal position advances proportionally
   faster (via a fixed-point sub-pixel accumulator), and the scroll extent is
   based on measured text width.

---

### User Story 4 - Class 1: Characterful scrolling (Priority: P2)

A developer wants scrolling text that feels alive rather than a constant
1 px/frame crawl: a **kinetic marquee** with mass/inertia (accelerate in, coast,
pause at punctuation/keywords, overshoot then spring off), a **wave-rider** that
ripples characters along a sine path, and a **split-flap** scroller where
entering characters flip through intermediate glyphs before landing.

**Why this priority**: Scrolling is ScrollKit's core use case; these effects are
the most immediately useful payoff and need only the easing engine and the scroll
fix from Story 3.

**Independent Test**: In the simulator, render each effect headless and assert
lit pixels advance frame-to-frame, that no heap is allocated per frame, and that
each passes the strict feasibility gate at 20 fps on the modeled device.

**Acceptance Scenarios**:

1. **Given** a kinetic marquee, **When** it runs, **Then** the visible text
   accelerates, dwells at punctuation/keywords, and overshoots/springs — with
   only label position changing per frame (no per-frame glyph rebuild except when
   the visible string changes).
2. **Given** a wave-rider, **When** characters cross the viewport, **Then** each
   character's vertical position follows a precomputed wave table and only the
   visible window of characters is realized.
3. **Given** a split-flap scroller, **When** a new character enters, **Then** it
   flips through a small deterministic sequence of intermediate glyphs (no
   per-frame random allocation) before settling.
4. **Given** any Class 1 effect under strict hardware simulation at 20 fps,
   **When** it runs for a sustained window of frames, **Then** no
   `FeasibilityError` is raised and no per-frame allocation occurs.

---

### User Story 5 - Class 2: Theatrical transitions (Priority: P2)

A developer wants cinematic transitions between messages, built on the overlay-
mask primitive: **iris snap** (diamond aperture), **venetian shutters** (coarse
staggered bands), **mosaic resolve** (blocks resolving in pseudo-random order),
**CRT collapse** (brightness ramp + horizontal bars), and **light-slit rewrite**
(a bright scanner that swaps content mid-sweep). These properly replace the
removed wipe/slide.

**Why this priority**: Transitions are valuable polish between content items and
are the intended replacement for the removed broken effects, but they depend on
the overlay-mask primitive from Story 3.

**Independent Test**: Render each transition headless and assert the correct
cover → swap-content-while-hidden → reveal sequence, that pixel writes per frame
are bounded (no full-screen Python loop), and that each passes the strict
feasibility gate at 20 fps.

**Acceptance Scenarios**:

1. **Given** any Class 2 transition, **When** it runs between two messages,
   **Then** the old content is covered, the content swaps while hidden, and the
   new content is revealed — with the swap invisible to the viewer.
2. **Given** a transition driven by the overlay mask, **When** a frame advances,
   **Then** only a bounded set of mask spans/blocks is written (no full 2048-pixel
   repaint) and no per-frame heap allocation occurs.
3. **Given** any Class 2 effect under strict hardware simulation at 20 fps,
   **When** it runs to completion, **Then** no `FeasibilityError` is raised.

---

### User Story 6 - Class 3: Palette-animated bitmap text (Priority: P2, headline differentiator)

A developer wants text effects that are visibly "not just displayio": a ScrollKit-
native fixed-cell (5×7) bitmap font rendered **once** into an indexed bitmap,
scrolled by moving a tile grid, with the **palette** animated each frame — neon-
tube crawl, chrome/metallic sheen, rainbow chase, hazard stripes — at near-zero
per-frame pixel cost.

**Why this priority**: This is the biggest differentiator and the strongest "you
can do *that* on a 64×32 panel?" moment, but it ships last because it needs a new
bitmap/font layer. Once it lands, the two demos using
`EffectsEngine.get_rainbow_color()` can migrate to it and the legacy animation
layer can be retired.

**Independent Test**: Render bitmap text, rotate/rewrite the palette across
frames, and assert the output changes with **no glyph rebuild** and no per-frame
pixel loop; assert tile-grid scrolling moves the text; assert strict feasibility
passes at 20 fps.

**Acceptance Scenarios**:

1. **Given** a message rendered once into an indexed bitmap, **When** the palette
   is rotated or rewritten on a frame, **Then** the visible colors change without
   re-rendering any glyph and without a per-pixel Python loop.
2. **Given** bitmap text on a tile grid, **When** the scroll position changes,
   **Then** the text moves by repositioning the tile grid (not by repainting
   pixels).
3. **Given** the neon-tube crawl, chrome sheen, rainbow chase, and hazard-stripe
   palette effects, **When** each runs under strict hardware simulation at 20 fps,
   **Then** no `FeasibilityError` is raised and per-frame pixel work stays near
   zero.

---

### User Story 7 - Showcase demo reel & feasibility-tagged docs (Priority: P3)

A developer (or prospective adopter) wants to *see* the whole showcase and trust
its hardware budgets. This story delivers a scripted demo reel chaining the
signature effects end-to-end and documentation that advertises each effect's
hardware budget.

**Why this priority**: This is the advertisement and proof, valuable only after
the effects exist. It is the final phase.

**Independent Test**: Run the demo reel in the simulator with hardware simulation
ON and strict mode, end to end, and confirm it completes without a
`FeasibilityError` and produces non-blank, advancing frames; confirm the docs
list each effect with its feasibility metadata.

**Acceptance Scenarios**:

1. **Given** the showcase demo reel, **When** it runs in the simulator with
   hardware simulation + strict mode, **Then** it completes the full scripted
   sequence (e.g., CRT-collapse intro → neon title → kinetic marquee → iris snap →
   wave-rider → split-flap → mosaic exit) with no feasibility failure.
2. **Given** the same demo source, **When** it is run on device vs. simulator,
   **Then** it runs unchanged (no per-platform code edits).
3. **Given** the effects documentation, **When** a developer reads an effect's
   entry, **Then** it advertises that effect's hardware budget/feasibility
   metadata (e.g., hardware-safe, per-frame allocation, max pixel writes per
   frame).

---

### Edge Cases

- **Empty / very long text**: scrolling and bitmap-text effects must handle empty
  strings and text wider than the documented maximum bitmap width gracefully
  (defined behavior, not a crash).
- **Over-budget effect under strict mode**: must raise `FeasibilityError`
  deterministically at the offending frame, not intermittently.
- **Strict mode without hardware simulation**: strict enforcement is meaningful
  only when the hardware timing/RAM model is active; the toggle combination must
  have well-defined behavior.
- **Retained legacy code**: `particles` and `get_rainbow_color()` must keep
  working until their demos are migrated; their removal is explicitly out of scope
  for this feature.
- **Device vs. simulator divergence**: if the simulator's output disagrees with
  reported hardware behavior, the *simulator* is corrected — never the shared
  display logic.
- **Peak-RAM breach**: an effect that fits the time budget but exceeds usable RAM
  must still fail strict mode.
- **CircuitPython gaps**: any standard-library feature used must exist on
  CircuitPython 8.x/9.x (no `typing` at runtime, `ValueError` for bad JSON,
  `OSError` not `FileNotFoundError`, etc.).

## Requirements *(mandatory)*

### Functional Requirements

**Cleanup (Story 1)**

- **FR-001**: The system MUST remove the broken/fake transition effects
  (`TransitionEngine`, `BaseTransition`, `FadeTransition`, `WipeTransition`,
  `SlideTransition`, the reveal effects, the basic-transition pack —
  fade-in/slide-in/wipe/flash/duplicate-pulse — and the dead duplicate
  `PulseEffect`) and prune them from the effects package exports.
- **FR-002**: Removing an effect from the effects package exports MUST
  automatically remove it from the introspected `capabilities()` catalog (no
  manual catalog edit).
- **FR-003**: The system MUST retain `EffectsEngine.get_rainbow_color()` and the
  particle engine until their demos migrate (Story 6); their final removal is out
  of scope for this feature.
- **FR-004**: All imports and docs referencing removed classes MUST be updated so
  the package imports cleanly and the suite stays green.

**Strict feasibility gate (Story 2)**

- **FR-005**: The system MUST define a `FeasibilityError` exception.
- **FR-006**: The performance model MUST support a `strict` mode that, at frame
  end, raises `FeasibilityError` when the modeled per-frame cost exceeds the
  per-frame budget.
- **FR-007**: The per-frame budget MUST default to a ~20 fps target (≈50 ms /
  frame) derived from the calibrated device baseline.
- **FR-008**: Strict mode MUST also fail when modeled peak RAM exceeds the
  device's usable RAM.
- **FR-009**: Strict mode MUST be reachable via an environment toggle
  (`SCROLLKIT_HW_STRICT`) plumbed through the simulator and unified display, with
  no application code change required.
- **FR-010**: Strict mode MUST default to **off** at the low (performance-model)
  level so existing warning-based tests stay green, and **on** by default for the
  new showcase entry points (demo reel and new effect tests).
- **FR-011**: The headless verification harness MUST accept a strict option,
  catch `FeasibilityError`, stop the run, and surface the failure in the run
  result (run reports not-OK) without crashing.

**Foundational primitives (Story 3)**

- **FR-012**: The system MUST provide an integer easing/tween engine using
  precomputed 0–255 lookup tables for at least: linear, ease-out-quad,
  ease-in-out, overshoot/back, bounce, and elastic-lite — with no floating-point
  math or allocation on the hot path.
- **FR-013**: The display interface MUST provide bounded span/rect painters
  (fill rect, fill span, clear rect) backed by sanctioned C bulk operations where
  available and a looped fallback otherwise; these MUST never perform a full
  2048-pixel Python loop.
- **FR-014**: The system MUST provide a preallocated, reusable overlay-mask layer
  (a single indexed bitmap with a transparent index, composited via a bulk blit)
  that is allocated once and updates only dirty spans.
- **FR-015**: `ScrollingText` MUST make `speed` drive motion via a fixed-point
  sub-pixel position accumulator and MUST compute scroll extent from measured
  text width rather than `len(text) * 6`.

**Class 1 — Characterful scrolling (Story 4)**

- **FR-016**: The system MUST provide a kinetic marquee with mass/inertia,
  punctuation/keyword dwell, and overshoot, changing only label position per
  frame except when the visible string changes.
- **FR-017**: The system MUST provide a wave-rider that positions visible-window
  characters along a precomputed wave table.
- **FR-018**: The system MUST provide a split-flap scroller whose entering
  characters flip through a small deterministic glyph sequence (no per-frame
  random allocation).

**Class 2 — Theatrical transitions (Story 5)**

- **FR-019**: The system MUST provide overlay-mask-based transitions: iris snap,
  venetian shutters, mosaic resolve, CRT collapse, and light-slit rewrite.
- **FR-020**: Each transition MUST follow a cover → swap-while-hidden → reveal
  sequence such that the content swap is invisible to the viewer.
- **FR-021**: Transitions MUST be invokable between content-queue items as the
  replacement for the removed wipe/slide effects.

**Class 3 — Palette-animated bitmap text (Story 6)**

- **FR-022**: The system MUST provide a ScrollKit-native fixed-cell (5×7) bitmap
  font (table-driven, no BDF parsing) rendered once into an indexed bitmap whose
  glyph pixels carry palette indices.
- **FR-023**: The system MUST scroll bitmap text by repositioning a tile grid,
  not by repainting pixels.
- **FR-024**: The system MUST provide palette-animation effects (neon-tube crawl,
  chrome/metallic sheen, rainbow chase, hazard stripes) that change output by
  rotating/rewriting palette entries with no glyph rebuild and near-zero per-frame
  pixel work.

**Showcase & docs (Story 7)**

- **FR-025**: The system MUST provide a scripted showcase demo reel that chains
  the signature effects and runs in the simulator with hardware simulation +
  strict mode, end to end, without a feasibility failure.
- **FR-026**: Documentation MUST advertise each effect's hardware budget /
  feasibility metadata (hardware-safe, per-frame allocation, max pixel writes per
  frame).

**Cross-cutting hard constraints (apply to all new effects)**

- **FR-027**: All new effect code MUST run **unchanged** on the CircuitPython
  MatrixPortal S3 and on the desktop pygame simulator (one shared display
  implementation; if simulator output diverges from hardware, fix the simulator,
  never the shared display logic).
- **FR-028**: No new effect may perform per-frame heap allocation on its hot path.
- **FR-029**: No new effect may use a per-pixel Python loop over all 2048 pixels;
  bounded work expressed through the C-bulk-backed painters/blit only.
- **FR-030**: The display MUST run at `bit_depth=4` (the calibrated baseline; ≈3×
  faster refresh than bit_depth 6).
- **FR-031**: All new effect run loops MUST be async-only (cooperative
  multitasking; no threads, no blocking the display loop).
- **FR-032**: Every showcase effect MUST pass the strict feasibility gate at the
  ~20 fps device budget.
- **FR-033**: Every phase MUST end with `make test-unit` and `make lint-errors`
  green; new effects MUST have unit tests asserting lit pixels advance, animation
  advances frame-to-frame, and no per-frame allocation.
- **FR-034**: Only CircuitPython 8.x/9.x-compatible standard-library features,
  exceptions, and modules may be used (per the project compatibility table).

### Key Entities *(include if feature involves data)*

- **FeasibilityError**: the failure signal raised when a modeled frame busts the
  device time or RAM budget under strict mode.
- **PerformanceManager (strict mode + per-frame budget)**: the per-frame cost/RAM
  model that enforces feasibility; gains a `strict` flag and a budget derived from
  the device baseline.
- **Easing engine**: integer lookup tables mapping a 0–255 progress to a 0–255
  eased value across named curves.
- **Span/rect painters**: bounded fill/clear operations on the display interface,
  backed by C bulk ops.
- **Overlay-mask layer**: a single preallocated indexed bitmap (transparent
  index) composited via bulk blit; the substrate for all Class 2 transitions.
- **ScrollingText (fixed-point)**: scrolling content whose position is a
  fixed-point sub-pixel accumulator and whose extent comes from measured width.
- **Class 1 effects**: kinetic marquee, wave-rider, split-flap (characterful
  scrolling content types).
- **Class 2 transitions**: iris snap, venetian shutters, mosaic resolve, CRT
  collapse, light-slit rewrite (overlay-mask transitions).
- **BitmapText + 5×7 font**: native fixed-cell font rendered once into an indexed
  bitmap, scrolled via tile grid.
- **Palette-animation effects**: neon-tube crawl, chrome sheen, rainbow chase,
  hazard stripes (palette rewrites over the bitmap text).
- **Showcase demo reel**: a scripted sequence chaining the signatures, with
  feasibility-tagged docs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: After every phase, `make test-unit` and `make lint-errors` are both
  green.
- **SC-002**: 100% of showcase effects pass the strict feasibility gate — running
  each headless for at least 120 frames with hardware simulation + strict mode
  produces a run that is OK (no `FeasibilityError`) with non-blank, advancing
  frames.
- **SC-003**: Every showcase effect's modeled per-frame cost is ≤ the ~50 ms
  (~20 fps) device budget, and modeled peak RAM stays within usable device RAM.
- **SC-004**: An intentionally over-budget effect deterministically raises
  `FeasibilityError` under strict mode (the gate provably bites).
- **SC-005**: Per-effect unit tests demonstrate zero per-frame heap allocation and
  no full-2048-pixel Python loop for every new effect.
- **SC-006**: The removed effects are no longer importable and no longer appear in
  the `capabilities()` catalog, while retained legacy items (`particles`,
  `get_rainbow_color()`) still pass their existing tests.
- **SC-007**: `ScrollingText` motion scales with `speed` (speed N advances ~N×
  faster than speed 1) and measured width matches the actual rendered glyph extent
  (no `len(text) * 6` estimate).
- **SC-008**: The showcase demo reel runs to completion in the simulator with
  hardware simulation + strict mode and runs unchanged on device (identical
  source, no per-platform edits).
- **SC-009**: Every shipped showcase effect carries advertised hardware-budget
  metadata in the docs/catalog.

## Assumptions

- **Delivery order = roadmap phase order**: story priority mirrors the mandated
  build sequence; later stories have hard dependencies on earlier ones
  (foundation → classes → demo). Strict story-by-story independence is not fully
  achievable because of these dependencies; each story is still independently
  *testable* once its predecessors exist.
- **Roadmap is authoritative for implementation**: file-level targets, module
  names, and the dependency map come from
  `/Users/czei/.claude/plans/this-library-needs-to-serene-parasol.md`. Where this
  spec and the roadmap differ on a detail, the roadmap and the `/plan` resolve it.
- **Device baseline is current**: the ~20 fps / 50 ms per-frame budget and the
  ~4.5 ms refresh figure come from the calibrated
  `matrixportal_s3_baseline.json` and `device_benchmarks.json`; recalibration is
  out of scope.
- **Scope split**: only the shared foundation (Phases 1–3) is required to be one
  cohesive deliverable; the three classes (Phases 4–6) and the demo reel
  (Phase 7) may each be tracked as their own spec-kit feature later, but are
  specified here as one umbrella feature.
- **Effects subsystem stays optional**: the core library (`app/`, `display/`,
  top-level `__init__`) must not gain a hard dependency on the effects subsystem,
  and `scrollkit.dev` must never be imported from device/core code.
- **Verification is simulator-first**: feasibility is proven against the
  calibrated hardware model in the simulator; physical-device re-verification of
  every effect is a stretch goal, not a gate, except for the existing
  BASIC-display path already verified on hardware.
- **Out of scope**: rewriting the ThemeParkWaits application (separate repo),
  removing `particles`/`get_rainbow_color()`, BDF font parsing for the bitmap
  font, and a ring-buffer viewport variant of bitmap text (deferred; start with
  the render-whole-message option).
