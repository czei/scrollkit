#!/usr/bin/env python3
"""ScrollKit demo (MEDIUM): animated rainbow scroll.

Scrolls a message where every letter is a different, flowing color — driven by
the effects engine's rainbow helper. No network; the "medium" part is the
per-character animation. Shows how a custom DisplayContent can animate using a
frame counter.

    PYTHONPATH=src python demos/medium/rainbow.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import asyncio

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import DisplayContent
from scrollkit.effects.effects import EffectsEngine


class RainbowScroll(DisplayContent):
    """Scrolls text with a flowing per-letter rainbow."""

    def __init__(self, text="SCROLLKIT  *  RAINBOW  *  "):
        super().__init__(duration=None)
        self.text = text
        self.effects = EffectsEngine()
        self.frame = 0
        self.x = 64

    async def render(self, display):
        self.frame += 1
        self.x -= 1
        if self.x < -len(self.text) * 6:
            self.x = display.width
        for i, ch in enumerate(self.text):
            cx = self.x + i * 6
            if -6 <= cx <= display.width:          # only draw visible chars
                color = self.effects.get_rainbow_color(((i * 2 + self.frame) % 30) / 30.0)
                await display.draw_text(ch, cx, 12, color)


class RainbowApp(ScrollKitApp):
    def __init__(self):
        super().__init__(enable_web=False, update_interval=10)
        self.content = RainbowScroll()

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
            await self.display.create_window("ScrollKit - Rainbow (medium)")


if __name__ == "__main__":
    asyncio.run(RainbowApp().run())
