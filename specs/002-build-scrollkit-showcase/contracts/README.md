# API Contracts — ScrollKit Showcase Effects

ScrollKit is a **library**, so its "contracts" are the public Python APIs it
exposes to app authors and to the dev/verification harness, plus the behavior
each guarantees. Every signature below must be importable and behave identically
on the CircuitPython MatrixPortal S3 and the desktop pygame simulator (the
platform difference is isolated to which `displayio`/`bitmaptools` modules the
display resolves).

Contracts are grouped by build phase:

- **[feasibility-gate.md](./feasibility-gate.md)** — Phases 1–2: the effects
  removal (what disappears from the public surface) and the strict
  hardware-feasibility gate (`FeasibilityError`, `PerformanceManager` strict
  params, `SCROLLKIT_HW_STRICT`, `run_headless(strict=)`).
- **[foundation-primitives.md](./foundation-primitives.md)** — Phase 3: integer
  easing, the display span/rect painters + `measure_text` + `gfx`/`add_layer`, the
  simulator `bitmaptools` shim, the `OverlayMask`, and the fixed-point
  `ScrollingText`.
- **[showcase-effects.md](./showcase-effects.md)** — Phases 4–6 class APIs
  (characterful scrolling, theatrical transitions, palette-animated bitmap text)
  + Phase 7 demo/docs feasibility metadata.

**Contract test rule**: each public surface below gets a unit test that (a)
imports it, (b) exercises its documented behavior, and (c) for any effect, proves
no per-frame allocation and strict feasibility at 20 fps. The Phases 1–3 contracts
are committed scope for this feature; the Phases 4–6 contracts fix the interfaces
the per-class sub-features will implement.
