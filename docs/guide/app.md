# App Framework

`scrollkit.app` provides the two entry points for building applications.

## MinimalLEDApp

`scrollkit.app.minimal.MinimalLEDApp` — a lightweight, synchronous-feeling
wrapper for simple scripts and the lowest memory footprint. It auto-detects the
environment and delegates to a CircuitPython or desktop implementation.

```python
from scrollkit.app.minimal import MinimalLEDApp

app = MinimalLEDApp()
app.show_text("Ready", color="green")     # static text; color name or (r,g,b)
app.scroll_text("Hello!", color=(0, 170, 255))
app.clear()
```

## ScrollKitApp

`scrollkit.app.base.ScrollKitApp` — the full-featured async base class. Subclass
it and override the hooks you need.

```python
class MyApp(ScrollKitApp):
    def __init__(self):
        super().__init__(enable_web=True, update_interval=300)

    async def setup(self):            # once, at startup
        ...
    async def update_data(self):      # every update_interval seconds
        ...
    async def prepare_display_content(self):   # each display frame
        return await self.content_queue.get_current()   # default behaviour
```

### Three-process architecture

`run()` launches up to three cooperative async tasks, gated by available RAM:

| Process | Runs when | Job |
|---------|-----------|-----|
| **Display** | always | render content at ~20 FPS |
| **Data update** | ≥ ~30 KB free | call `update_data()` every `update_interval` |
| **Web server** | `enable_web` and ≥ ~50 KB free | serve the config UI |

On low-memory devices the data and web processes are skipped automatically so
the display always keeps running — graceful degradation rather than a crash.

!!! note "Naming"
    `ScrollKitApp` is the public name; `SLDKApp` remains as a backward-compatible
    alias.
