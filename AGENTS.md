# AGENTS.md — Building ScrollKit LED apps with an AI agent

This is the entry doc for an AI agent (or a human) writing a **ScrollKit** app: a
scrolling LED-matrix display that runs unchanged on the **Adafruit MatrixPortal
S3** (CircuitPython) and on the desktop **pygame simulator**.

The whole point of the workflow below is to close the gap that bites everyone:
*the simulator runs at full desktop speed and looks fantastic, but the real
device is ~100× slower and RAM-tiny, so apps that look great in the sim can crawl
or fail on hardware.* ScrollKit lets you discover that **in the simulator,
headless, before flashing** — so you can iterate without a human and without a
board.

> Repo-specific rules (don't touch `boot.py`/`code.py`, keep code under `/src`,
> CircuitPython compatibility) live in **CLAUDE.md** — read it too if you're
> editing this repository. This file is about *authoring ScrollKit apps*.

---

## The loop

1. **Write** a `ScrollKitApp` subclass (imperative Python — no config/DSL).
2. **Run it headless**: `scrollkit.dev.run_headless(app, frames=N, screenshot=...)`.
3. **Read** the `RunResult`: did it render? did it advance? would it run on
   hardware (estimated FPS + warnings)?
4. **Validate**: `scrollkit.dev.validate(app)` for structured issues + fixes.
5. **Iterate** until the result is clean, then hand off for flashing.

Everything in step 2-4 is **desktop-only** (`scrollkit.dev` raises `ImportError`
on CircuitPython by design — it pulls in numpy/pygame). The app you write in
step 1 runs on both.

### Running things

The repo's root `code.py` shadows the stdlib `code` module, so run tests/scripts
with:

```bash
PYTHONSAFEPATH=1 PYTHONPATH=src python your_script.py
```

The harness sets `SDL_VIDEODRIVER=dummy` itself, so no window is needed.

---

## A minimal working app

```python
from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import ScrollingText


class HelloApp(ScrollKitApp):
    def __init__(self):
        super().__init__(enable_web=False, update_interval=10)

    async def create_display(self):
        from scrollkit.display.simulator import SimulatorDisplay
        return SimulatorDisplay(width=64, height=32)

    async def setup(self):
        # Add content to the queue; the display loop renders it.
        self.content_queue.add(ScrollingText("HELLO HARDWARE", y=12, color=0x00FF88))
```

Verify it:

```python
from scrollkit.dev import run_headless

result = run_headless(HelloApp(), frames=120, screenshot="frame.png")
print(result.as_text())
```

`run_headless` drives the app's real display loop deterministically (exactly `N`
frames, no inter-frame sleep — same app + same `frames` → same pixels), saves a
PNG, and returns a JSON-able `RunResult`.

---

## The panel and colors

- **Panel:** 64 × 32 pixels (the MatrixPortal S3 standard). `x` is 0-63, `y` is
  0-31. `y=12` vertically centers an ~8px-tall font.
- **Color:** a 24-bit RGB int `0xRRGGBB` (e.g. `0xFF8800`) **or** an `(r, g, b)`
  tuple with each channel 0-255. **Color name *strings* do not work** with the
  content classes below — they'd crash `draw_text`. (Only `MinimalLEDApp`
  understands names.) To use a name programmatically:
  `scrollkit.dev.capabilities()["named_colors"]["orange"]`.

## Content types

Discover these (and their exact parameters) at runtime with
`scrollkit.dev.capabilities()` — it's introspected from the live code so it can't
go stale. The two you'll use most:

- `ScrollingText(text, x=None, y=0, color=0xFFFFFF, speed=30, priority=2)` —
  scrolls right-to-left; ideal for anything wider than 64px.
- `StaticText(text, x=0, y=0, color=0xFFFFFF, duration=None, priority=2)` —
  fixed; keep it short enough to fit 64px (≈10 chars) or it'll be clipped.

**Coordinates:** the origin `(0, 0)` is the **top-left** corner. X grows to the
**right**, Y grows **downward** (standard CircuitPython `displayio`). `y` sets the
text **baseline**, not the top of the glyphs — so `y=0` pushes a line's ascenders
off the top of the panel and renders nothing readable. For the standard 8px font
on the 64×32 panel, `y≈12` vertically centers a single line; valid `y` runs
`0..31`. (Available as `capabilities()["panel"]["coordinates"]`.)

Add content in `setup()` via `self.content_queue.add(...)`. Queue items can carry
a `priority` (see `capabilities()["priorities"]`: IDLE=0 … SYSTEM=5).

---

## Reading the RunResult

`run_headless(...)` returns a `RunResult`. Key fields:

| field | meaning |
|---|---|
| `frames` | frames actually rendered |
| `is_blank` / `bright_pixels` / `coverage` | did anything light up, and how much |
| `advanced` | did the picture change between the first and last frame (e.g. text scrolled) |
| `current_content` | a `describe()` of what was on screen (text, position, …) |
| `estimated_hardware_fps` | modeled FPS on the real device (see below) |
| `hardware` | full feasibility dict; `hardware_text` is the printable version |
| `memory` | estimated free RAM (modeled when hardware timing is on) |
| `errors` / `warnings` | anything that went wrong / advisories |
| `ok` | rendered something with no errors |

`result.advanced is False` for a deliberately static display is fine; for a
`ScrollingText` it means the loop didn't iterate — investigate.

---

## Hardware feasibility — the part that matters

When `hardware=True` (the default), the result includes a report of how the app
would run on the real MatrixPortal S3. The shipped profile is **calibrated from
real measurements** captured on an `adafruit_matrixportal_s3` (CircuitPython
9.1.0), so the report reads `MEASURED on device`:

```
=== Hardware feasibility: Adafruit MatrixPortal S3 (64x32) ===
  Confidence: MEASURED on device (measured on adafruit_matrixportal_s3, CircuitPython 9.1.0)
  Estimated hardware FPS: ~45.1   (median frame ~22 ms, worst ~23 ms)
  Per-frame cost (avg): refresh 13.7 ms | bitmap_rebuild 7.3 ms | ...
  Estimated peak RAM: 1 KB / 1513 KB budget
  No feasibility warnings.
```

(If the baseline file is absent, it falls back to a clearly-labeled ROUGH
ESTIMATE and rounds FPS to one significant figure.)

How to read it:

- **Every frame pays one `display.refresh()` (~13.7 ms measured).** That's a hard
  ceiling near ~73 FPS no matter how simple the app — refresh dominates light
  apps.
- **The #1 rule on top of that: don't rebuild text every frame.** Re-running
  `draw_text` with changing text rebuilds a glyph bitmap pixel-by-pixel in Python.
  A `ScrollingText` that just moves is cheap; redrawing ~12 changing fields per
  frame stacks ~12 rebuilds on top of the refresh and drops you toward single
  digits. If you see the "cache the Label" warning on a busy app, only change
  `.text` when the value actually changes.
- **RAM is rarely the limit on the S3.** ~1.5 MB is free to an app (the ESP32-S3
  PSRAM), so the web server (~50 KB) and data updates (~20-30 KB) fit easily; the
  report still warns if estimated peak RAM ever approaches budget.

A quick contrast you can reproduce: a single `ScrollingText` is refresh-bound at
~45 FPS; an app that redraws ~12 text fields every frame drops to ~13 FPS (and a
heavier one into single digits, with a "scrolling will stutter" warning) —
**even though both look identical in the simulator.** That's the signal to act on
before flashing.

### Feel it: visceral throttle mode

Numbers are easy to ignore. To watch the simulator window actually **crawl at the
modeled hardware speed**, build the display with `throttle=True`:

```python
SimulatorDisplay(width=64, height=32, throttle=True)   # implies hardware timing
```

or set `SCROLLKIT_HW_THROTTLE=1` in the environment for any simulator run. In this
mode each frame sleeps its modeled time and you'll see periodic console nags like
`[hw-sim] frame 30: ~150 ms/frame (~6 FPS) on the real device — this would
stutter.` This is a **live/interactive** aid — the headless `run_headless`
harness always runs unthrottled and silent, so verification stays fast and
deterministic.

---

## Performance cheat-sheet (measured on the device)

`scrollkit.dev.performance_guide()` returns these numbers (captured by a
microbenchmark suite on a real MatrixPortal S3, so they don't drift). The spread
is huge, and it's all about **C calls vs interpreted Python**:

| writing one pixel | ns/pixel | |
|---|---|---|
| `bitmap[x,y] = 1` (interpreted) | ~7,000 | the trap |
| `bitmaptools.blit` (C) | ~620 | ~11× faster |
| `bitmap.fill` (C) | ~4.4 | ~1,600× faster |

| full `display.refresh()` | time | FPS ceiling |
|---|---|---|
| bit_depth ≤ 4 | ~4.5 ms | ~220 |
| bit_depth 6 | ~13.7 ms | ~73 |

The cardinal rules that follow from the data:

1. **Reuse a `Label`; change `.text` only when the value changes.** A text change
   rebuilds the glyph bitmap pixel-by-pixel — the dominant per-frame cost. For
   scrolling, move `.x` and leave `.text` alone. (The library's `UnifiedDisplay`
   now does this for you via a per-frame label pool — don't allocate your own
   Label every frame.)
2. **Never push pixels in a Python loop** — use `bitmap.fill` / `bitmaptools.blit`.
3. **Keep `bit_depth=4`** unless you need smooth gradients (it's ~3× faster than 6).
   `UnifiedDisplay(bit_depth=...)` exposes it; 4 is the default.
4. **Don't allocate per frame** (Label/Bitmap/TileGrid/Group) — tens of µs each,
   plus GC pressure. Create once, mutate.
5. **Heavy compute competes with rendering** — it's cooperative (~500k Python
   ops/sec, no background thread), so a 1,000-op calc costs ~1.5 ms of your frame.
   Chunk long work across frames (and across the synchronous HTTP fetch).

## Pre-flight validation

```python
from scrollkit.dev import validate

report = validate(app)          # runs headless once, then checks
print(report.as_text())
print(report.ok)                # False if there are any errors
```

`validate()` returns structured `Issue`s (each has `severity`, `code`, `message`,
`fix`) covering: out-of-range RGB, color *name strings* (an error — they crash),
text wider than the panel (clipped), off-panel `y`, a blank render, runtime
exceptions, and the hardware stutter/RAM warnings. Treat `errors` as blockers and
`warnings` as "this will look/run worse on hardware than in the sim."

---

## Discovering the API

```python
from scrollkit.dev import capabilities
cat = capabilities()            # JSON-able dict, introspected from live code
# cat["content_types"], cat["priorities"], cat["effects"],
# cat["named_colors"], cat["display_api"], cat["hardware"]
```

Prefer `capabilities()` over guessing class/parameter names — it reflects the
installed library exactly.

---

## CircuitPython gotchas (for the app you ship)

The app runs on CircuitPython, a subset of MicroPython. In app code: no `typing`
at runtime, catch `ValueError` (not `JSONDecodeError`) and `OSError` (not
`FileNotFoundError`), use `time.monotonic()` (not `time.time()`), cooperative
`asyncio` only (no threads), and remember HTTP (`adafruit_requests`) is
**synchronous** — a fetch pauses the display loop, so break long work into chunks
and show a "loading" frame. See CLAUDE.md for the full list.
