# Quickstart & Validation: ScrollKit Showcase Effects

How to validate each phase end-to-end. Every phase ends with **both** of these
green (hard rule — FR-033 / SC-001):

```bash
make test-unit
make lint-errors
```

Single test (note the env prefix that keeps CWD off `sys.path`):

```bash
PYTHONSAFEPATH=1 PYTHONPATH=src python -m pytest \
  test/unit/path/test_file.py::TestClass::test_method -v
```

## Prerequisites

- Desktop dev env with `pygame` + `numpy` (the simulator extras).
- A working tree on branch `002-build-scrollkit-showcase`.
- Optional: a MatrixPortal S3 on USB for on-device spot-checks (not a gate; the
  BASIC display path is the only one already device-verified).

---

## The universal showcase gate (used by Phases 4–7)

Every new effect is proven against the calibrated hardware model in **strict**
mode. The canonical check:

```python
from scrollkit.dev import run_headless
from scrollkit.exceptions import FeasibilityError

result = run_headless(MyEffectApp(), frames=120, hardware=True, strict=True,
                      screenshot="/tmp/effect.png")
assert result.ok is True            # no FeasibilityError, not blank
assert result.advanced is True      # animation moved frame-to-frame
print(result.hardware_text)         # budget breakdown (<= 50 ms/frame, 20 fps)
```

Inspect `/tmp/effect.png` for a non-blank, sensible frame. The **negative**
control (proves the gate bites) uses a **sustained** over-budget effect (or a
single catastrophic frame), not an isolated rebuild:

```python
result = run_headless(IntentionallyHeavyApp(), frames=30, hardware=True, strict=True)
assert result.ok is False
assert any("feasibility" in e.lower() for e in result.errors)
```

The gate is steady-state (median over a rolling window) plus a single-frame
transient ceiling, so a cheap effect that does **one** legitimate glyph rebuild
mid-run (visible-string change) must still pass — verify that case too:

```python
result = run_headless(OneRebuildMidRunApp(), frames=120, hardware=True, strict=True)
assert result.ok is True   # isolated rebuild spike absorbed by the median window
```

---

## Phase 1 — Removal

```bash
make test-unit && make lint-errors
PYTHONSAFEPATH=1 PYTHONPATH=src python -m pytest test/unit/effects/test_removal.py -v   # every FR-001 name gone
PYTHONSAFEPATH=1 PYTHONPATH=src python -c "
import scrollkit.effects as fx
for n in ('FadeInEffect','SlideInEffect','WipeEffect','RevealEffect'):
    assert n not in fx.__all__, n
from scrollkit.dev import capabilities
cat = capabilities()
import json; names = json.dumps(cat)
for n in ('FadeTransition','WipeTransition','SlideTransition','RevealEffect','FadeInEffect'):
    assert n not in names, n
# retained:
from scrollkit.effects.effects import EffectsEngine
from scrollkit.effects.particles import ParticleEngine, Sparkle, Snow
assert hasattr(EffectsEngine(), 'get_rainbow_color')
print('Phase 1 OK')
"
```

Expected: prints `Phase 1 OK`; `test_removal.py` green; both make targets green.

---

## Phase 2 — Strict feasibility gate

```bash
PYTHONSAFEPATH=1 PYTHONPATH=src python -m pytest test/unit/simulator/test_hardware_realism.py -v   # all still green (warning path intact)
PYTHONSAFEPATH=1 PYTHONPATH=src python -m pytest test/unit/dev/test_harness.py -v                  # incl. new strict cases
```

Validate behavior:

- `FeasibilityError` importable: `from scrollkit.exceptions import FeasibilityError`.
- Over-budget effect under `strict=True` ⇒ `result.ok is False` with a feasibility
  error string.
- Cheap effect under `strict=True` ⇒ `result.ok is True`.
- `strict=False` (default) ⇒ identical to today (warnings only); existing
  `test_hardware_realism.py` assertions unchanged.
- `SCROLLKIT_HW_STRICT=1 PYTHONPATH=src python demos/...` activates the gate
  without code changes.

---

## Phase 3 — Foundation

```bash
PYTHONSAFEPATH=1 PYTHONPATH=src python -m pytest \
  test/unit/effects/test_easing.py \
  test/unit/effects/test_overlay.py \
  test/unit/display/test_painters.py \
  test/unit/display/test_layers.py \
  test/unit/display/test_bitmaptools_shim.py \
  test/unit/display/test_scrolling_text.py \
  test/unit/effects/test_proving_spikes.py -v
```

Validate:

- **Easing**: `ease(curve, 0)==0`, `ease(curve, 255)==255`; LUTs are `bytes`;
  integers, deterministic.
- **Painters**: `fill_rect`/`fill_span`/`clear_rect` change only in-bounds pixels;
  a 64×32 `clear_rect` takes the **bulk path** (no full Python loop);
  `measure_text("HELLO")` matches a rendered Label's width (not `5*6`);
  `measure_text("")==0`; a missing glyph uses the replacement advance.
- **`gfx` bridge**: `display.gfx is display.gfx` (cached, no per-access alloc);
  `display.gfx.bitmaptools.fill_region` exists on the simulator (the shim).
- **Shim conformance**: `test_bitmaptools_shim.py` replays the golden battery and
  matches `bitmaptools_golden.json` byte-for-byte (edge clip, negative offset,
  `skip_index`, zero-area, full-fill).
- **Layers (D11)**: a TileGrid added via `add_layer` survives N `clear()` calls and
  stays above Labels even after the pool grows; `add_layer`/`remove_layer`
  idempotent.
- **OverlayMask**: bitmap/palette object identity stable across many mutations
  (single allocation); index 0 transparent.
- **ScrollingText**: at `speed=60` it advances ~2× the px of `speed=30` over the
  same frame count; width measured once at start (not per frame); completes when
  fully scrolled off measured width.
- **Proving spikes**: a minimal `IrisSnap` (real cover→swap→reveal) and a minimal
  `BitmapText` (one message + `RainbowChase`) each pass strict at 20 fps — this is
  the gate that declares the foundation API stable before it's frozen.

Visual smoke (optional): `PYTHONPATH=src python demos/medium/rainbow.py` still
runs; add `SCROLLKIT_HW_THROTTLE=1` to watch at modeled device speed.

---

## Phases 4–6 — The three classes

For each effect, run the universal showcase gate above, plus the per-class tests:

```bash
PYTHONSAFEPATH=1 PYTHONPATH=src python -m pytest test/unit/effects/test_scrolling_effects.py -v   # Class 1
PYTHONSAFEPATH=1 PYTHONPATH=src python -m pytest test/unit/effects/test_transitions.py -v          # Class 2
PYTHONSAFEPATH=1 PYTHONPATH=src python -m pytest test/unit/display/test_bitmap_text.py -v           # Class 3
```

Class-specific checks:

- **Class 1**: marquee dwells at punctuation; wave-rider only realizes the visible
  window; split-flap deterministic given `seed`.
- **Class 2**: assert content is hidden at peak cover, then revealed; bounded mask
  writes.
- **Class 3**: rotating the palette changes rendered output with the glyph bitmap
  object **unchanged** (no rebuild); TileGrid `.x` scroll moves the text.

All three: `no per-frame allocation` assertions and `result.ok is True` under
strict at 20 fps.

---

## Phase 7 — Demo reel + docs

```bash
# End-to-end strict run of the whole reel:
PYTHONSAFEPATH=1 PYTHONPATH=src python -c "
from scrollkit.dev import run_headless
from demos.hard.showcase import ShowcaseApp   # or demos.showcase
r = run_headless(ShowcaseApp(), frames=600, hardware=True, strict=True, screenshot='/tmp/showcase.png')
assert r.ok is True, r.errors
print('Showcase OK:', r.hardware_text.splitlines()[0])
"
# Visual:
PYTHONPATH=src python demos/hard/showcase.py
# Real-device crawl preview:
SCROLLKIT_HW_THROTTLE=1 PYTHONPATH=src python demos/hard/showcase.py
```

Docs check: each effect page in `docs/guide/*` lists its feasibility metadata
(`hardware_safe`, `allocates_per_frame`, `max_pixel_writes_per_frame`,
`modeled_frame_ms`).

---

## Definition of done (whole feature)

- Phases 1–3 fully implemented; `make test-unit` + `make lint-errors` green.
- **Foundation proven**: the per-primitive proving spikes (fixed-point
  `ScrollingText`, a minimal `IrisSnap`, a minimal `BitmapText`) pass strict at
  20 fps, and the shim matches `bitmaptools_golden.json` — the `gfx`/`add_layer`/
  `OverlayMask`/`measure_text` contracts are validated before being frozen.
- Every showcase effect passes the strict gate at 20 fps (`result.ok is True`,
  120+ frames, non-blank, advancing) — SC-002/003.
- The negative control raises `FeasibilityError` under strict — SC-004.
- Per-effect tests prove no per-frame allocation and no full-2048 loop — SC-005.
- Removed effects gone from imports + catalog; particles/rainbow still pass — SC-006.
- `ScrollingText` speed/width fixed — SC-007.
- Showcase reel runs unchanged on simulator (strict) and device — SC-008.
- Every shipped effect carries hardware-budget metadata — SC-009.
