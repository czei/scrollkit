#!/usr/bin/env python3
"""ScrollKit demo (EASY): a digital clock.

Shows the current time (HH:MM:SS), updating every second. No network. The time
is formatted from time.localtime() so it works on both desktop and CircuitPython
(CircuitPython has no time.strftime).

    PYTHONPATH=src python demos/easy/clock.py
"""

import sys
import os

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
except AttributeError:
    pass  # CircuitPython has no os.path; scrollkit is already on the path (/lib)

import asyncio
import time

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import DisplayContent


class ClockContent(DisplayContent):
    """Draws the current time, centered; render() runs every frame so it ticks."""

    def __init__(self):
        super().__init__(duration=None)

    async def render(self, display):
        t = time.localtime()
        text = "%02d:%02d:%02d" % (t.tm_hour, t.tm_min, t.tm_sec)
        x = max(0, (display.width - len(text) * 6) // 2)
        await display.draw_text(text, x, 12, 0x00FFCC)


class ClockApp(ScrollKitApp):
    def __init__(self):
        super().__init__(enable_web=False, update_interval=10)
        self.content = ClockContent()

    async def create_display(self):
        try:
            from scrollkit.display.simulator import SimulatorDisplay
            return SimulatorDisplay(width=64, height=32)
        except ImportError:
            return await super().create_display()

    async def prepare_display_content(self):
        return self.content

    async def setup(self):
        if hasattr(self.display, "create_window"):
            await self.display.create_window("ScrollKit - Clock (easy)")


if __name__ == "__main__":
    asyncio.run(ClockApp().run())
