# Easy: Hello World

The simplest ScrollKit app — scroll some text across the simulated LED matrix.
No network, no data sources.

![Hello World demo](../assets/demos/hello_world.gif){ width="480" }

Full source: [`demos/easy/hello_world.py`](https://github.com/Czeiszperger/scrollkit/blob/main/demos/easy/hello_world.py)

```python
import asyncio
from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import ScrollingText, StaticText


class HelloWorldApp(ScrollKitApp):
    def __init__(self):
        super().__init__(enable_web=False, update_interval=10)

    async def create_display(self):
        from scrollkit.display.simulator import SimulatorDisplay
        display = SimulatorDisplay(width=64, height=32)
        await display.create_window("ScrollKit - Hello World")
        return display

    async def setup(self):
        # Content added here is cycled by the display loop.
        self.content_queue.add(StaticText("Hi!", x=20, y=12, color=0x00FF88, duration=2))
        self.content_queue.add(ScrollingText("Hello, World! Welcome to ScrollKit.",
                                              y=12, color=0x00AAFF))


if __name__ == "__main__":
    asyncio.run(HelloWorldApp().run())
```

Run it:

```bash
PYTHONPATH=src python demos/easy/hello_world.py
```

## What's happening

- **`ScrollKitApp`** runs an async loop. Its display process repeatedly asks for
  content and renders it at ~20 FPS.
- **`setup()`** runs once at startup. We push two pieces of content into
  `self.content_queue`: a static "Hi!" for 2 seconds, then a scrolling greeting.
- **`StaticText` / `ScrollingText`** are `DisplayContent` types. `StaticText`
  with a `duration` expires after that many seconds; `ScrollingText` scrolls
  until it leaves the screen.
- **`create_display()`** opens the simulator window. Omit this override and
  `UnifiedDisplay` auto-selects hardware vs simulator for you.

Next: [Medium — live data](medium.md).
