# Getting Started

## Install

ScrollKit lives in `src/scrollkit/`. For desktop development you need the
simulator extras (pygame + numpy + Pillow):

```bash
pip install "scrollkit[simulator]"
```

Run anything from the repo root with `src` on the path:

```bash
PYTHONPATH=src python demos/easy/hello_world.py
```

!!! note "Running the tests"
    Use `PYTHONSAFEPATH=1 PYTHONPATH=src python -m pytest test/unit/...`.
    `PYTHONSAFEPATH=1` keeps the repo root off `sys.path` (see `make test-unit`).

## Your first app

```python
import asyncio
import sys
sys.path.insert(0, "src")

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import ScrollingText
from scrollkit.display.simulator import SimulatorDisplay

class HelloWorldApp(ScrollKitApp):
    async def create_display(self):
        return SimulatorDisplay(width=64, height=32)

    async def setup(self):
        self.content_queue.add(
            ScrollingText("Hello, World!", y=12, color=(0, 255, 128)))

asyncio.run(HelloWorldApp().run())
```

On desktop this opens a window showing the simulated 64×32 matrix (the
`create_display()` override above is what opens it — omit it and the app still
runs, just headless, since plain `UnifiedDisplay` stays headless on desktop
unless a window is explicitly asked for). On a supported
CircuitPython board (the MatrixPortal S3 or the Interstate 75 W) the identical
code drives the physical panel.

## Writing an app

Subclass `ScrollKitApp` and override the hooks you need; the framework runs
them as cooperative async tasks.

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
2. Copy `src/` to the device, or run `make copy-to-circuitpy`.
3. Add a `secrets.py` on the device with your WiFi credentials:
   `secrets = {"ssid": "your-network", "password": "your-password"}` (the
   standard CircuitPython convention — see `scrollkit.utils.url_utils.load_credentials`).

The same app code runs unchanged: `UnifiedDisplay` auto-selects the hardware
backend on CircuitPython and auto-detects which board it's on (pass `board="..."`
to force one). See [Adding New Hardware](guide/hardware.md).

### CircuitPython dependencies (circup)

The device also needs the Adafruit libraries ScrollKit uses (e.g.
`adafruit_requests`, `adafruit_httpserver`, `adafruit_display_text`,
`adafruit_bitmap_font`, and — on the MatrixPortal S3 — `adafruit_matrixportal`).
Manage them with [circup](https://github.com/adafruit/circup):

```bash
pip install circup
circup install adafruit_requests adafruit_httpserver adafruit_display_text adafruit_bitmap_font adafruit_matrixportal
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
