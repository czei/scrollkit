# Performance

ScrollKit runs the same code in two places that could not be more different. On
your desktop the simulator renders in pygame at whatever speed your laptop can
manage, which is to say instantly. On the actual hardware, an Adafruit
MatrixPortal S3, that same code runs as interpreted CircuitPython on an ESP32-S3:
roughly 100 times slower, with a few megabytes of RAM and no second thread to
hide behind. The trap is obvious in hindsight and catches everyone anyway. Your
app looks gorgeous in the simulator, you flash it, and the scrolling text moves
like a slideshow.

That gap is the price of writing in Python. Python instead of C++ is a deliberate
trade: you give up raw speed and get back code one person can write, read, and run
unchanged on a desktop. The library spends most of its design budget buying that
speed back where it counts. This page is the cost model behind those decisions,
measured on real hardware, plus the one war story that explains why the rules
exist.

!!! info "These numbers are measured, not guessed"
    Every figure on this page comes from a microbenchmark suite run on a real
    MatrixPortal S3 (CircuitPython 9.1.0). `scrollkit.dev.performance_guide()`
    returns the live table; `device_benchmarks.json` and
    `matrixportal_s3_baseline.json` hold the raw captures. They can't drift from
    the prose, because they aren't prose.

## The frame budget

The device targets 20 frames per second. That is your whole allowance: 50
milliseconds per frame, and not a millisecond more if you want the motion to stay
smooth.

Some of that is already spent before your code does anything. Every single frame
pays for one `display.refresh()`, which pushes the framebuffer out to the panel.
At the default `bit_depth=4` that costs about 4.5 ms. It is a floor you cannot get
under, a tax on simply being powered on. Whatever your app actually does (move
text, paint a transition, fly a swarm of birds across the screen) has to fit in
what's left.

The strict feasibility gate enforces this for you. Run an app through
`run_headless(app, strict=True)` and any effect that busts the 50 ms budget raises
`FeasibilityError` before it ever reaches a board. More on that at the end.

## Where the time goes

The entire performance story is one comparison: a call that runs in C versus a
loop that runs in interpreted Python. The spread is not subtle.

Writing a single pixel, three ways:

| Operation | Cost per pixel | |
|---|---|---|
| `bitmap[x, y] = 1` (interpreted) | ~7,000 ns | the trap |
| `bitmaptools.blit` (C) | ~620 ns | ~11× faster |
| `bitmap.fill` (C) | ~4.4 ns | ~1,600× faster |

Read that bottom row again. Filling a region with a C call is about **1,600 times**
faster per pixel than setting pixels one at a time in a Python loop. Clearing the
whole 64×32 panel (2,048 pixels) is one `bitmap.fill` at roughly 9 microseconds.
The same clear written as a nested Python loop is about 14 milliseconds, which is
most of your frame gone before you've drawn anything.

Refresh cost depends on color depth, and the cliff is steep:

| `display.refresh()` | Frame time | FPS ceiling |
|---|---|---|
| `bit_depth` ≤ 4 | ~4.5 ms | ~220 |
| `bit_depth` 6 | ~13.7 ms | ~73 |

Two extra bits of color triple the refresh cost. That is why the library defaults
to `bit_depth=4` and tells you to leave it there unless you genuinely need smooth
gradients.

Compute is the quiet budget killer. CircuitPython manages roughly **500,000 simple
Python operations per second**, so a thousand-operation calculation costs about
1.5 ms straight out of your frame. There is no background thread to hide it in; the
runtime is cooperative, so any math you do is math the display loop is not doing. A
few hundred lines of arithmetic per frame and you are competing with the rendering
you are trying to feed.

Allocation carries a tax of its own. A Bitmap costs ~120 µs to create, a TileGrid
~48 µs, a small bytearray ~74 µs, and every object you allocate is an object the
garbage collector will later walk, a pause that runs from 0.3 to 0.9 ms depending
on how much you've churned. Do any of that once per frame and you've signed up for
a recurring bill.

RAM, for once, is rarely the thing that bites. The ESP32-S3's PSRAM leaves roughly
1.5 MB free to your app, which swallows the web server and the data updates without
complaint. On this board, time is the scarce resource, not memory.

## How the library works around it

Every rule below is just one of those numbers turned into a habit.

- **Reuse a `Label`; change `.text` only when the value changes.** Rebuilding a
  glyph bitmap means setting its pixels one at a time, the 7,000-ns-per-pixel path,
  and it is the single largest per-frame cost in a busy app. To scroll, move the
  label's `.x` and leave `.text` alone. `UnifiedDisplay` keeps a label pool and
  does this for you, so don't allocate your own Label every frame.
- **Never push pixels in a Python loop.** Use `bitmap.fill` for solid regions and
  `bitmaptools.blit` to copy. The transitions all paint through one preallocated
  `OverlayMask` with bounded, bulk `fill_region` calls, never a 2,048-pixel loop.
- **Keep `bit_depth=4`.** It is the default, and it refreshes three times faster
  than `bit_depth=6`.
- **Don't allocate per frame.** Build your Bitmaps, TileGrids, and Groups once,
  then mutate them. Allocation costs tens of microseconds each and feeds the GC
  pauses you'll pay for later.
- **Chunk heavy compute across frames.** A long calculation belongs in pieces,
  spread over several frames, the same way a slow HTTP fetch (synchronous on this
  device) should render a "loading" frame before it blocks the loop.

None of this is exotic. It is the same advice you'd give for any tight render loop,
made non-negotiable by a chip that punishes the lazy version by a factor of a
thousand.

## Case study: rewriting the swarm

The rules above sound abstract until something violates all of them at once. That
something was the swarm.

The first swarm effect was a boids flock: 150 birds obeying the classic three rules
(separation, alignment, cohesion), assembling text out of captured pixels as they
flew over it. It was beautiful, and it only ever ran on the desktop, off
precomputed paths, because computing it live would have buried the device. The cost
was structural. Each frame ran three separate O(n²) neighbor passes, one per
flocking rule, and then an O(birds × pixels) scan to decide which pixels each bird
had captured. With 150 birds and a few hundred target pixels, that is tens of
thousands of Python operations per frame before a single pixel is drawn. On a chip
that does 500,000 operations a second, you can do that arithmetic yourself.

So it was rewritten from the algorithm up (commit `a152267`). The three neighbor
passes became one combined pass that computes all three rules together, using
squared distances so the radius checks never pay for a `sqrt`. The per-frame capture
scan became O(1): each bird pulls its target from a pre-shuffled queue and lights it
on arrival, no searching. And the drawing dropped its per-pixel loops for bulk
`bitmap.fill`. Same effect, same flocking, completely different cost.

The payoff, measured on an S3 with refresh included:

| Birds | Frame time | Verdict |
|---|---|---|
| 14 | ~25 ms | the safe default |
| 20 | ~34 ms | fine |
| 28 | ~48 ms | right at the 20 fps limit |
| 100 | ~600 ms | about 1.6 fps |

Cost still grows with the square of the bird count (the neighbor pass is
irreducibly pairwise), which is why the on-device default is 14 birds and the
ceiling sits around 28. The desktop simulator has no such limit, so crank it up for
a screenshot. The lesson is the one this whole page keeps making: the right
algorithm plus a C bulk call turned an effect that took 0.6 seconds a frame into
one that takes 25 milliseconds. Nothing about the birds changed. Only the cost did.

## Catch it before you flash

The point of all this is that you don't have to find out on hardware. The simulator
models the device's speed, so you can fail fast on your laptop.

```python
from scrollkit.dev import run_headless, validate

result = run_headless(app, frames=120, strict=True)   # raises FeasibilityError if over budget
print(result.as_text())                               # estimated hardware FPS + warnings

report = validate(app)                                 # structured issues, each with a fix
print(report.ok)
```

`strict=True` turns the 50 ms budget into a hard wall: a sustained over-budget run,
a catastrophic single frame, or a RAM breach all raise `FeasibilityError`. Without
it, the `RunResult` still reports an estimated hardware FPS and any stutter
warnings, so you see the cliff coming even when you don't enforce it.

And when a number won't land, feel it. Build the display with `throttle=True` (or
set `SCROLLKIT_HW_THROTTLE=1`) and the simulator window crawls at the modeled
hardware speed, complete with console nags when a frame would stutter. Watching the
thing limp is more persuasive than any table on this page.

```python
from scrollkit.display.simulator import SimulatorDisplay
SimulatorDisplay(width=64, height=32, throttle=True)   # implies hardware timing
```

## See also

- [Theatrical Transitions](transitions.md#hardware-budget) lists the per-transition
  pixel and frame budgets: the same cost model applied effect by effect.
- [Characterful Scrolling](scrolling.md) covers the fixed-point, no-allocation
  scroller internals.
- [The Simulator](simulator.md) documents hardware-timing mode and how the device
  model is calibrated.
- `AGENTS.md` at the repo root is the condensed version of this page for an AI agent
  building apps, with the same measured numbers.
