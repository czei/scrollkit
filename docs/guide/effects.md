# Effects

`scrollkit.effects` adds visual polish: transitions between content, particle
effects, and reveal animations — all built to respect the device's memory and
frame budget.

## EffectsEngine

`scrollkit.effects.effects.EffectsEngine` coordinates active effects. It caps the
number of concurrent effects (default 2) and uses pre-allocated colour tables to
avoid per-frame allocation on CircuitPython.

```python
from scrollkit.effects.effects import EffectsEngine

effects = EffectsEngine(display)
```

## What's available

| Module | Effects |
|--------|---------|
| `scrollkit.effects.transitions` | fades, slides between content |
| `scrollkit.effects.basic_transitions` | simple cut / wipe transitions |
| `scrollkit.effects.particles` | particle systems (sparkles, bursts) |
| `scrollkit.effects.reveal` | progressive uncover / reveal animations |
| `scrollkit.effects.base` | the `Effect` base class for writing your own |

Effects run with functionally equivalent behaviour on hardware and in the
simulator — same effect types and sequencing, though exact pixel timing differs.

!!! tip "Memory ladder"
    Effects are the first thing to disable on a memory-starved device. Keep the
    concurrent-effect cap low and prefer the lighter transitions when targeting
    the MatrixPortal S3.
