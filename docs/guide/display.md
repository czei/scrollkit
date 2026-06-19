# Display

`scrollkit.display` is the heart of the library: the display abstraction, the
content types, and the priority queue.

## UnifiedDisplay

`scrollkit.display.unified.UnifiedDisplay` implements `DisplayInterface` and
auto-selects its backend:

- **CircuitPython** → real `displayio` hardware (MatrixPortal S3, 64×32).
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
  the screen.

`color` accepts a 24-bit int (`0xFF0000`) or an `(r, g, b)` tuple.

## Priority & eviction

`scrollkit.display.queue.DisplayQueue` is a priority-ordered queue with the
high-level API `add`, `peek`, `pop`, `expire`, `len()`. Priorities come from
`scrollkit.display.strategy.Priority`: `IDLE < LOW < NORMAL < HIGH < SYSTEM`.

When the queue is full, `add()` follows this eviction policy:

- **SYSTEM** items are always admitted — they evict the lowest-priority, oldest
  non-SYSTEM item to make room, and are themselves never evicted by `add()`.
- A higher-priority item displaces the lowest-priority item present.
- An item lower-or-equal priority than everything present is rejected
  (`add()` returns `False`).

`expire()` drops items whose `duration` has elapsed and returns how many were
removed.

!!! info "Two queue APIs"
    `DisplayQueue` also exposes a `DisplayItem`/strategy API (`add_item`,
    `process_next`) used internally by `DisplayManager`. Most apps use the
    simple `DisplayContent` queue shown above, or the app's `content_queue`.
