# Display

`scrollkit.display` is the heart of the library: the display abstraction, the
content types, and the content queue.

## UnifiedDisplay

`scrollkit.display.unified.UnifiedDisplay` implements `DisplayInterface` and
auto-selects its backend:

- **CircuitPython** → real `displayio` hardware, auto-detecting the board (the
  Adafruit MatrixPortal S3 or the Pimoroni Interstate 75 W). Pass `board="..."`
  to force one. See [Adding New Hardware](hardware.md).
- **Desktop** → the [pygame simulator](simulator.md).

Your app talks to one interface — `set_pixel`, `fill`, `draw_text`, `show`,
`clear`, `set_brightness` — and never branches on platform.

```python
from scrollkit.display.unified import UnifiedDisplay

display = UnifiedDisplay()      # width == 64, height == 32
await display.initialize()
display.fill((0, 0, 0))
display.draw_text("Hi", 0, 12, (0, 255, 128))
await display.show()
```

## Content types

`scrollkit.display.content`:

- **`DisplayContent`** — base class. Tracks `duration`, `priority`, `elapsed`,
  and an `is_complete` property derived from elapsed time.
- **`StaticText(text, x, y, color, duration, priority)`** — fixed text.
- **`ScrollingText(text, y, color, speed, priority)`** — scrolls until it leaves
  the screen. With `speed=0` it holds the text **centred** for `static_duration`
  seconds instead (so a transition can still fire between repeats).

`color` accepts a 24-bit int (`0xFF0000`) or an `(r, g, b)` tuple. For gradient
fills pass a `palette` — see [Gradient Text](gradient-text.md).

<div class="grid" markdown>
<figure markdown="span">![ScrollingText scrolling](../assets/reference/content/scrollingtext-scroll.gif){ width="280" }<figcaption>`ScrollingText(...)` — scrolling</figcaption></figure>
<figure markdown="span">![ScrollingText static](../assets/reference/content/scrollingtext-static.gif){ width="280" }<figcaption>`ScrollingText(..., speed=0)` — centred static</figcaption></figure>
</div>

## ContentQueue

`scrollkit.display.content.ContentQueue` is the queue `ScrollKitApp.content_queue`
uses. It's a simple **looping** queue, not priority-ordered: `add(content)`
appends; the display loop calls `await get_current()` each frame, which shows
the current item until `is_complete`, then advances to the next and loops back
to the start when `loop=True` (the default). `clear()` empties it (and defers
the abandoned item's async `stop()` to the next frame, so any layer it added —
e.g. a transition overlay — gets detached cleanly).

```python
from scrollkit.display.content import ContentQueue, StaticText, ScrollingText

queue = ContentQueue()
queue.add(StaticText("Hi!", x=20, y=12, duration=2))
queue.add(ScrollingText("Rotates after the static message", y=12))
```

Every `DisplayContent` carries a `priority` (`scrollkit.display.content.Priority`:
`IDLE < LOW < NORMAL < HIGH < URGENT < SYSTEM`, default `NORMAL`) — metadata your
app can read to build its own admission/eviction logic on top of the queue;
`ContentQueue` itself doesn't act on it.
