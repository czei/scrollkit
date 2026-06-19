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

On desktop this opens a window showing the simulated 64×32 matrix. On a
MatrixPortal S3 the identical code drives the physical panel.

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

1. Connect the MatrixPortal S3 over USB (it mounts as `CIRCUITPY`).
2. Copy `src/` to the device, or run `make copy_to_circuitpy`.
3. Set WiFi credentials in `settings.json`.

The same app code runs unchanged — `UnifiedDisplay` auto-selects the hardware
backend on CircuitPython.

Next: the [Easy tutorial](tutorials/easy.md).
