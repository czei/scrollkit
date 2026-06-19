#!/usr/bin/env python3
"""ScrollKit demo (EASY): Hello World.

Demonstrates the simplest possible ScrollKit app: scroll some text across the
simulated LED matrix. No network, no data sources.

Run on desktop (opens a pygame window showing the simulated 64x32 matrix):

    PYTHONPATH=src python demos/easy/hello_world.py

The same code runs unchanged on an Adafruit MatrixPortal S3.
"""

import sys
import os

# Make `scrollkit` importable when run straight from the repo.
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
except AttributeError:
    pass  # CircuitPython has no os.path; scrollkit is already on the path (/lib)

import asyncio

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import ScrollingText


class HelloWorldApp(ScrollKitApp):
    """Scrolls a greeting across the LED matrix, over and over."""

    def __init__(self):
        # No web server / data updates needed for this trivial demo.
        super().__init__(enable_web=False, update_interval=10)

    async def create_display(self):
        """Use the desktop simulator (falls back to hardware on device)."""
        try:
            from scrollkit.display.simulator import SimulatorDisplay
            return SimulatorDisplay(width=64, height=32)
        except ImportError:
            return await super().create_display()

    async def setup(self):
        """Queue the message to scroll. The display loop repeats it forever."""
        # setup() runs after the display is initialized, so the window opens at
        # the correct size here.
        if hasattr(self.display, "create_window"):
            await self.display.create_window("ScrollKit - Hello World (easy)")
        self.content_queue.add(
            ScrollingText("Hello, World!  Welcome to ScrollKit.", y=12, color=0x00AAFF))


if __name__ == "__main__":
    asyncio.run(HelloWorldApp().run())
