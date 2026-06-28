# Getting Started

## Install

ScrollKit lives in `src/scrollkit/`. For desktop development you need the
simulator dependency (pygame):

```bash
pip install pygame
```

Run anything from the repo root with `src` on the path:

```bash
PYTHONPATH=src python demos/easy/hello_world.py
```

!!! note "Running the tests"
    Use `PYTHONSAFEPATH=1 PYTHONPATH=src python -m pytest test/unit/...`.
    The repo's frozen `code.py` (the CircuitPython entry point) shadows the
    stdlib `code` module; `PYTHONSAFEPATH=1` keeps the repo root off `sys.path`
    so pytest's debugger import resolves the real stdlib module.

## Your first app

```python
import asyncio
import sys
sys.path.insert(0, "src")

from scrollkit.app.minimal import MinimalLEDApp

MinimalLEDApp().scroll_text("Hello, World!", color=(0, 255, 128))
```

On desktop this opens a window showing the simulated 64×32 matrix. On a supported
CircuitPython board (the MatrixPortal S3 or the Interstate 75 W) the identical
code drives the physical panel.

## Two ways to write an app

=== "MinimalLEDApp (simple)"

    Best for quick scripts and the lowest memory footprint.

    ```python
    from scrollkit.app.minimal import MinimalLEDApp

    app = MinimalLEDApp()
    app.show_text("Ready", color="green")
    app.scroll_text("Live in 3... 2... 1...")
    ```

=== "ScrollKitApp (full)"

    Subclass it for real applications. Override the hooks you need; the
    framework runs them as cooperative async tasks.

    ```python
    import asyncio
    from scrollkit.app.base import ScrollKitApp
    from scrollkit.display.content import ScrollingText

    class MyApp(ScrollKitApp):
        def __init__(self):
            super().__init__(enable_web=False, update_interval=60)

        async def setup(self):
            self.content_queue.add(ScrollingText("Hello from ScrollKit"))

        async def update_data(self):
            ...  # fetch fresh data every update_interval seconds

    asyncio.run(MyApp().run())
    ```

## Deploying to hardware

1. Connect a supported board (MatrixPortal S3 or Interstate 75 W) over USB (it
   mounts as `CIRCUITPY`).
2. Copy `src/` to the device, or run `make copy_to_circuitpy`.
3. Set WiFi credentials in `settings.json`.

The same app code runs unchanged: `UnifiedDisplay` auto-selects the hardware
backend on CircuitPython and auto-detects which board it's on (pass `board="..."`
to force one). See [Adding New Hardware](guide/hardware.md).

### CircuitPython dependencies (circup)

The device also needs the Adafruit libraries ScrollKit uses (e.g.
`adafruit_requests`, `adafruit_httpserver`, `adafruit_display_text`,
`adafruit_bitmap_font`). Manage them with [circup](https://github.com/adafruit/circup):

```bash
pip install circup
circup install adafruit_requests adafruit_httpserver adafruit_display_text adafruit_bitmap_font
```

### Saving RAM with .mpy (optional)

These boards are memory-constrained (the RP2350 Interstate 75 W especially, with
no PSRAM). Cross-compiling the library to `.mpy`
loads faster and uses less RAM than shipping raw `.py`. With `mpy-cross` installed
(matching your CircuitPython version):

```bash
pip install mpy-cross        # match your CircuitPython version
make mpy                     # -> build/scrollkit/*.mpy
```

Then copy `build/scrollkit/` to the device (e.g. `CIRCUITPY/lib/scrollkit/`)
instead of the raw `src/scrollkit/`.

Next: the [Easy tutorial](tutorials/easy.md).
