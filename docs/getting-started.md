# Getting Started

## Install

Choose the release path before installing:

- **Using ScrollKit in a desktop project:** install the stable PyPI release.
  A version tag such as `v0.8.4` corresponds to a released package. Pin the
  version in production/reproducible builds.
- **Contributing or trying unreleased work:** clone `master` and install it
  editable. `master` is a development branch, not the normal consumer path.
- **Deploying to CircuitPython:** copy a tested source or matching `.mpy` build
  into the app's `lib/` payload. Devices should not follow `master` directly.

For a stable desktop install, use the simulator extras (pygame + numpy + Pillow):

```bash
pip install "scrollkit[simulator]"
# Or pin a known release: pip install "scrollkit[simulator]==X.Y.Z"
```

To modify ScrollKit itself or run the bundled demos (what the rest of this page
assumes), clone the repo and install it editable — your edits to `src/scrollkit/`
take effect without reinstalling:

```bash
git clone https://github.com/czei/scrollkit.git
cd scrollkit
pip install -e ".[simulator]"
```

The legacy-looking `release-*` branches and an optional `live` branch described
in [OTA Updates](guide/ota.md) are application deployment channels. They are not
alternative package-install branches.

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
unless a window is explicitly asked for). On a supported CircuitPython board
such as the MatrixPortal S3, the identical code drives the physical panel.

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

1. Connect a supported board such as the MatrixPortal S3 over USB (it mounts
   as `CIRCUITPY`).
2. Copy `src/` to the device, or run `make copy-to-circuitpy`.
3. Configure WiFi — two ways:
    - **On the device itself, no file editing** (the end-user path): wire the
      onboarding portal into your app's `setup()` and the panel walks the user
      through joining the device's own access point and picking a network from
      a phone — see [WiFi onboarding portal](guide/networking.md#wifi-onboarding-portal-no-file-editing).
    - **`secrets.py`** (the developer shortcut): add
      `secrets = {"ssid": "your-network", "password": "your-password"}` on the
      device (the standard CircuitPython convention — see
      `scrollkit.utils.url_utils.load_credentials`). Portal-saved settings take
      precedence over `secrets.py`.

The same app code runs unchanged: `UnifiedDisplay` auto-selects the hardware
backend on CircuitPython and auto-detects which board it's on (pass `board="..."`
to force one). See [Adding New Hardware](guide/hardware.md).

### CircuitPython dependencies (circup)

The device also needs the Adafruit libraries ScrollKit uses (e.g.
`adafruit_requests`, `adafruit_httpserver`, `adafruit_display_text`, and
`adafruit_bitmap_font`). The MatrixPortal S3 additionally needs
`adafruit_matrixportal`. Manage the bundle libraries with
[circup](https://github.com/adafruit/circup):

```bash
pip install circup
circup install adafruit_requests adafruit_httpserver adafruit_display_text adafruit_bitmap_font adafruit_matrixportal
```

### Saving RAM with .mpy (optional)

The MatrixPortal S3 is memory-constrained. Cross-compiling the library to
`.mpy` loads faster and uses less RAM than shipping raw `.py`.

**Do not `pip install mpy-cross`** — that PyPI package is MicroPython's
compiler, and CircuitPython rejects its bytecode with
`ValueError: incompatible .mpy file`. Use the binary Adafruit builds from
CircuitPython itself: download the one matching your board's CircuitPython
version from the
[mpy-cross index](https://adafruit-circuit-python.s3.amazonaws.com/index.html?prefix=bin/mpy-cross/),
`chmod +x` it, and put it on your `PATH` as `mpy-cross` (or pass
`MPY_CROSS=/path/to/it` to make). Then:

```bash
make mpy                     # -> build/scrollkit/*.mpy
```

Then copy `build/scrollkit/` to the device (e.g. `CIRCUITPY/lib/scrollkit/`)
instead of the raw `src/scrollkit/`. The `.mpy` format is stable within a
CircuitPython major family (9.x/10.x share one); recompile with the matching
mpy-cross when the board moves to a new major. Shipping `.mpy` **over OTA**
has more rules — see [OTA Updates](guide/ota.md).

Next: the [Easy tutorial](tutorials/easy.md).
