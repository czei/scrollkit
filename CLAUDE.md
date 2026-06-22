# CLAUDE.md

Guidance for Claude Code (claude.ai/code) when working in this repository.

## What this is

**ScrollKit** is a library for building scrolling LED-matrix displays that run
**unchanged** on the Adafruit MatrixPortal S3 (CircuitPython 8.x/9.x) and on a
desktop **pygame simulator**. The library lives entirely in `src/scrollkit/`.

This repo is the **library only**. The ThemeParkWaits application that uses it
lives in its own repository (`../themeparkwaits.release`) — do not add
application code here.

For *building apps with* the library (the imperative API, content types, the
verification loop, and the device-measured performance cheat-sheet), see
**`AGENTS.md`** at the repo root.

## Repository layout

- `src/scrollkit/` — the library:
  - `app/` — `ScrollKitApp` base class, the async run loop, memory helpers
  - `display/` — `UnifiedDisplay` (auto-detects hardware vs simulator), the
    `SimulatorDisplay`, `DisplayInterface`, content classes
  - `effects/`, `network/`, `ota/`, `config/`, `utils/` — supporting subsystems
  - `simulator/` — desktop pygame simulator (displayio emulation, fonts, and the
    `core/` hardware-realism model)
  - `dev/` — **desktop-only** developer/AI verification toolkit (raises
    `ImportError` on CircuitPython by design)
- `test/unit/` — the test suite (headless, simulator-based)
- `test/claude/` — host-side device tooling (raw-REPL driver, calibration,
  microbenchmarks) — not collected as tests
- `demos/` — runnable library demos (`easy/`, `medium/`, `hard/`)
- `docs/` + `mkdocs.yml` — documentation

## Commands

The package lives under `src/`, so tests/scripts run with an env prefix.
`PYTHONSAFEPATH=1` keeps the CWD off `sys.path`.

- `make test-unit` — run the unit suite
- `make test-all` — run all tests
- Single test: `PYTHONSAFEPATH=1 PYTHONPATH=src python -m pytest test/unit/path/test_file.py::TestClass::test_method -v`
- `make lint` — ruff with auto-fix
- `make lint-errors` — critical-error check (undefined names, syntax errors)
- `make test-coverage` — coverage report

**ALWAYS run `make test-unit` and `make lint-errors` after any change; both must
be green before considering work complete.**

## The dev / verification toolkit (`scrollkit.dev` — desktop only)

This is how an app is built and checked against the simulator before flashing:

- `run_headless(app, frames=N, screenshot=path) -> RunResult` — deterministic
  headless render with pixel metrics + a hardware feasibility report
- `capabilities()` — JSON-able catalog (content types, priorities, effects,
  colors, display API), introspected from live code so it can't drift
- `validate(app)` — structured pre-flight issues with concrete fixes
- `performance_guide()` — per-operation costs measured on a real device

`scrollkit.dev` pulls in numpy/pygame and **must never be imported from device
code or from the core library** (`app/`, `display/`, the top-level `__init__`).
It raises `ImportError` immediately on CircuitPython.

## Hardware feasibility + calibration

The simulator can model the real device's speed and RAM so problems surface
before flashing (the classic trap: it looks great at desktop speed but crawls on
the ~100×-slower device). Opt in with `SimulatorDisplay(hardware_timing=True)` or
`SCROLLKIT_HW_SIM=1`; the visceral real-time crawl is `throttle=True` /
`SCROLLKIT_HW_THROTTLE=1`.

The model is **calibrated from a real MatrixPortal S3**. The baseline ships at
`src/scrollkit/simulator/core/matrixportal_s3_baseline.json` and the
per-operation microbenchmark table at `device_benchmarks.json`. Recapture both
with `test/claude/calibrate_device.py` and `test/claude/device_benchmarks.py`
(needs a board on USB serial; uses the raw-REPL driver in `test/claude/cpy_repl.py`,
which writes nothing to the device).

## CircuitPython compatibility (CRITICAL)

The library must run on CircuitPython 8.x/9.x (a subset of MicroPython), not just
desktop Python. **Before using any standard-library feature, exception, or
module, verify it exists in CircuitPython.**

| Standard Python | CircuitPython alternative | Notes |
|-----------------|---------------------------|-------|
| `json.JSONDecodeError` | `ValueError` | `json.loads()` raises `ValueError` on bad JSON |
| `FileNotFoundError` | `OSError` | only `OSError` exists, not the subclasses |
| `pathlib.Path` | `os` operations | no `pathlib` |
| `urllib.parse` | manual string parsing | no `urllib` |
| `threading` | `asyncio` | cooperative multitasking only |
| `subprocess` | not available | cannot spawn processes |
| `typing` (at runtime) | remove / comment hints | no `typing` module on device |
| `enum.auto()` | explicit values | `auto()` not available |
| `time.time()` | `time.monotonic()` | wall clock unreliable |
| `random.choices()` | `random.choice()` in a loop | `choices()` not available |
| f-string `f"{x=}"` | regular f-strings | `=` debug syntax unsupported |
| `match`/`case` | `if`/`elif` | no pattern matching |

Required pattern:

```python
# WRONG (desktop only)            # CORRECT (CircuitPython compatible)
except json.JSONDecodeError:      except ValueError:
except FileNotFoundError:         except OSError:
```

Other device realities to design around:
- HTTP is **synchronous** (`adafruit_requests`), so a fetch blocks the display
  loop. Break long work into chunks and render a "loading" frame before blocking.
- The device is RAM-constrained and ~100× slower than desktop; the top-level
  `scrollkit/__init__.py` does **no eager submodule imports** (every import costs
  RAM) — keep it that way.

## One display, dev == hardware (CRITICAL)

There is a single display implementation used in both the dev simulator and on
CircuitPython. **If the simulator's output doesn't match reported hardware
behavior, fix the simulator code, not the shared display logic. No exceptions.**

Performance follows the device measurements (see `AGENTS.md` for the full
cheat-sheet): reuse `Label`s instead of allocating/rebuilding one per frame, use
C bulk calls (`bitmap.fill`, `bitmaptools.blit`) rather than per-pixel Python
loops, and keep `bit_depth=4` (≈3× faster refresh than 6).

## Thread safety: the web server must never modify the message queue

The web server runs in a separate context and must **never** mutate display/queue
state. It may only update settings the main loop reads and set flags the main
loop checks. The message queue is owned solely by the main display-loop thread.

## Code style

- Find the **root cause** of problems; do not paper over issues (e.g. missing
  data). If intent is ambiguous, ask before acting.
- Imports grouped: stdlib, third-party (Adafruit), then project modules.
- `PascalCase` classes, `snake_case` functions/vars, `UPPERCASE` constants.
- Specific `try`/`except` with the CircuitPython-correct exception types.
- Docstrings on classes and methods.
- Documentation, plans, and design docs go in `plans/`.
- Temporary/scratch programs go in `test/claude/`.
- Include hardware-abstraction fallbacks so code degrades gracefully off-device.

<!-- SPECKIT START -->
For additional context about technologies to be used, project structure,
shell commands, and other important information, read the current plan:
`specs/002-build-scrollkit-showcase/plan.md` (ScrollKit Showcase Effects —
zero-allocation micro-show engine: removal of broken effects, a strict
hardware-feasibility gate, shared primitives, and three signature effect classes).
<!-- SPECKIT END -->
