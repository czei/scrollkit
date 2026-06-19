#!/usr/bin/env python3
"""ScrollKit demo (EASY): colors.

Cycles a word through the colors of the rainbow, centered on the matrix. No
network — just shows how color works.

    PYTHONPATH=src python demos/easy/colors.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import asyncio

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import DisplayContent


class ColorsContent(DisplayContent):
    """Shows one named color at a time, switching every ~1.5s."""

    COLORS = [
        ("RED", 0xFF0000), ("GREEN", 0x00FF00), ("BLUE", 0x0000FF),
        ("YELLOW", 0xFFFF00), ("CYAN", 0x00FFFF), ("PURPLE", 0xFF00FF),
        ("ORANGE", 0xFF8000), ("PINK", 0xFF66CC),
    ]

    def __init__(self):
        super().__init__(duration=None)   # never completes; cycles forever
        self.frame = 0

    async def render(self, display):
        self.frame += 1
        word, color = self.COLORS[(self.frame // 30) % len(self.COLORS)]
        x = max(0, (display.width - len(word) * 6) // 2)
        await display.draw_text(word, x, 12, color)


class ColorsApp(ScrollKitApp):
    def __init__(self):
        super().__init__(enable_web=False, update_interval=10)
        self.content = ColorsContent()

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
            await self.display.create_window("ScrollKit - Colors (easy)")


if __name__ == "__main__":
    asyncio.run(ColorsApp().run())
