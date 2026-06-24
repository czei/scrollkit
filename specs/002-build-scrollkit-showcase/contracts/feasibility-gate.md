# Contract: Effects Removal + Strict Feasibility Gate (Phases 1–2)

## A. Removal — public surface that MUST disappear

After Phase 1, importing these MUST raise `ImportError`/`AttributeError` (they are
deleted and pruned from `effects.__all__`):

| Symbol | Old location |
|---|---|
| `TransitionEngine`, `BaseTransition`, `FadeTransition`, `WipeTransition`, `SlideTransition` | `scrollkit.effects.transitions` (file deleted) |
| `RevealEffect`, `RevealCenterEffect` | `scrollkit.effects.reveal` (file deleted) |
| `FadeInEffect`, `SlideInEffect`, `WipeEffect`, `FlashEffect`, `PulseEffect` (the `Effect` subclass) | `scrollkit.effects.basic_transitions` (file deleted) |

`scrollkit.effects.__all__` MUST no longer contain `FadeInEffect`,
`SlideInEffect`, `WipeEffect`, `RevealEffect`.

### Retained (unchanged public behavior)

!!! note "Superseded by the effects consolidation"
    The base/engine symbols this (002) feature retained were **later removed** by
    the effects-consolidation work (see the repo `CHANGELOG.md`):
    `scrollkit.effects.base` (the `Effect` ABC, `EffectRegistry`, `register_effect`,
    `CompositeEffect`), `scrollkit.effects.effects` (`EffectsEngine`,
    `get_rainbow_color`, `SimpleEffect` and the concrete `SparkleEffect` /
    `EdgeGlowEffect` / `PulseEffect` / `RainbowCycleEffect` / `CornerFlashEffect`),
    and the orphaned `scrollkit.display.enhanced_content`. The standalone particle
    system below is the only one still retained.

| Symbol | Location | Reason |
|---|---|---|
| `ParticleEngine`, `Particle`, `Sparkle`, `RainDrop`, `Ember`, `Snow` | `scrollkit.effects.particles` | standalone particle system (still retained) |

### Catalog behavior

- `scrollkit.dev.capabilities()` MUST NOT list any removed effect. This happens
  **automatically** because `capabilities._effects()` reads `effects.__all__`; no
  catalog code is edited (FR-002).
- `test/unit/dev/test_capabilities.py` MUST be updated to drop the `FadeInEffect`
  expectation.

### Removal is asserted, not assumed (S8)

`test/unit/effects/test_removal.py` MUST assert that **every** FR-001 name —
`TransitionEngine`, `BaseTransition`, `FadeTransition`, `WipeTransition`,
`SlideTransition`, `RevealEffect`, `RevealCenterEffect`, `FadeInEffect`,
`SlideInEffect`, `WipeEffect`, `FlashEffect`, and the duplicate `PulseEffect` —
raises `ImportError`/`AttributeError` from its old location, is absent from
`effects.__all__`, and is absent from the `capabilities()` catalog.

> The fresh `effects/transitions.py` created in Phase 5 (Class 2) is unrelated to
> the deleted file of the same name; Phase 1's delete is ordered strictly before
> Phase 5's create.

### Done-when

`make test-unit` and `make lint-errors` green; no remaining import of a removed
symbol anywhere in `src/`, `test/`, `demos/`, `docs/`.

---

## B. `FeasibilityError`

```python
# scrollkit/exceptions.py
class FeasibilityError(SLDKError):
    """Raised when a modeled frame busts the device time or RAM budget
    under strict hardware simulation."""
```

- **Import contract**: `from scrollkit.exceptions import FeasibilityError` works on
  device and desktop (pure class def; no simulator import).
- **Is-a**: `SLDKError` → `Exception` (catchable by existing broad handlers).
- **Message**: includes frame index, modeled ms/frame, implied fps, the budget,
  and the dominant cost component (time breach) or modeled-peak vs usable RAM
  (RAM breach).

---

## C. `PerformanceManager` strict mode (D1, D6)

```python
# scrollkit/simulator/core/performance_manager.py
class PerformanceManager:
    def __init__(self, profile, enabled=True, throttle=False, history=120,
                 ambient_warnings=None, warn_interval=30, stutter_fps=10.0,
                 strict=False, target_fps=20.0, warmup_frames=2,
                 gate_window=8, transient_factor=2.0):
        ...
    def account_bulk_op(self, kind, px):   # kind in {"fill_region", "blit"}; px = clipped pixels
        ...
```

Behavior — a **two-threshold** gate, not a single-frame budget:

- `frame_budget_us == 1_000_000 / target_fps` (50 000 at 20 fps);
  `transient_budget_us == frame_budget_us * transient_factor` (100 000 ≈ 10 fps).
- In `_end_frame()`, only when `strict` and `_frame_index >= warmup_frames`:
  1. **Transient ceiling** — raise `FeasibilityError` if
     `frame.total_us > transient_budget_us` (catastrophe guard).
  2. **Steady-state** — once the last `gate_window` frame totals exist, raise if
     `median(window) > frame_budget_us` (sustained over-budget; an isolated glyph
     rebuild is absorbed by the median, so it does NOT false-trip — this is the
     fix for the brittle single-frame gate).
  3. **RAM** — raise if `estimated_peak_ram_bytes() > profile.usable_ram_bytes`.
- `account_bulk_op(kind, px)` adds `profile.bulk_base_us + px * slope(kind)` to a
  new `FrameCost.bulk_ops_us` slot (included in `total_us`/`as_dict()`), where
  `slope` is `profile.fill_region_us_per_px` / `profile.blit_us_per_px` and `px`
  is the **clipped** region's scanned pixel count (a fully-clipped call costs only
  `bulk_base_us`). The base is conservative (over-counts slightly ⇒ gate fails
  safe); recalibration of base/slope at multiple sizes is a tracked TODO.
- **Back-compat (MUST hold)**: with `strict=False` (the default), `_end_frame()`,
  the ambient-warning path, rate-limiting, `last_warning`, the no-sleep-unless-
  throttle rule, and the "one show() == one frame" mapping are **unchanged**. All
  existing `test_hardware_realism.py` assertions still pass. (The median window is
  computed in the desktop perf model only — never a device hot path.)

---

## D. Display toggles

```python
# SimulatorDisplay.__init__ (display/simulator.py)
def __init__(self, width=64, height=32, scale=10, *,
             hardware_timing=False, throttle=False, strict=False): ...
```

- `strict=True` implies hardware timing (forces the model on).
- Env var `SCROLLKIT_HW_STRICT=1`, read in `SimulatorDisplay._maybe_enable_
  hardware_timing()` and the **desktop branch** of
  `UnifiedDisplay._maybe_enable_hardware_timing()` (mirroring `SCROLLKIT_HW_SIM` /
  `SCROLLKIT_HW_THROTTLE`); when set with an active model ⇒
  `PerformanceManager(strict=True)`.
- **Device semantics (S2)**: strict feasibility is a **simulator-only** concept.
  The timing model is a no-op on CircuitPython (the device runs at real speed), so
  on-device the env read does nothing and `FeasibilityError` is **never raised on
  hardware**. Strict is meaningful only when the desktop timing model is active.

---

## E. `run_headless(strict=...)`

```python
# scrollkit/dev/harness.py
def run_headless(app, frames=None, seconds=None, screenshot=None,
                 hardware=True, warmup_data=False, strict=False): ...
async def run_headless_async(app, ..., strict=False): ...
```

Behavior:

- `strict=True` sets `SCROLLKIT_HW_STRICT=1` for the run (in addition to the
  `SCROLLKIT_HW_SIM=1` already set when `hardware=True`), and restores the prior
  value afterward.
- A `FeasibilityError` raised mid-run is caught by the existing per-frame
  `except Exception`, recorded in `RunResult.errors` (e.g. prefixed
  `"feasibility: ..."`), and stops the loop. The harness does **not** crash.
- Consequently `RunResult.ok` is `False` for an over-budget effect under
  `strict=True`, and `True` for a cheap effect.
- `RunResult` schema is otherwise unchanged (`ok`, `errors`, `warnings`,
  `hardware`, `hardware_text`, pixel metrics, `advanced`, …).

### Acceptance (maps to spec US2)

| Given | When | Then |
|---|---|---|
| **sustained** over-budget effect | `run_headless(app, hardware=True, strict=True)` | `result.ok is False`; an error mentions feasibility (steady-state median breach) |
| catastrophic single frame (≥2 full rebuilds / runaway) | same | `result.ok is False` (transient-ceiling breach) |
| cheap effect with one **isolated** legitimate glyph rebuild (visible-string change) | same | `result.ok is True` — the median window absorbs the spike (NOT a false-trip) |
| cheap effect | same | `result.ok is True`; no feasibility error |
| any effect | `strict=False` (default) | behaves exactly as today (warnings only) |
| over-budget effect | strict at low level off, showcase test opts in | gate bites only where opted in |
