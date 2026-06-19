#!/usr/bin/env python3
"""ScrollKit demo (MEDIUM): big-font animated rainbow scroll.

Unlike the other demos (which use the small built-in 8px font), this one loads a
*tall* bitmap font so the letters fill the vertical height of the 64x32 matrix,
and scrolls them with a flowing per-letter rainbow. It shows two things:

  - how to load and use a custom BDF font (font= on draw_text), and
  - spacing text by each glyph's real advance width (this font is wide).

    PYTHONPATH=src python demos/medium/rainbow.py
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import asyncio

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import DisplayContent
from scrollkit.effects.effects import EffectsEngine

# A tall font (~20px caps) so the text fills the 32px display height.
_FONT_NAME = "Junction_regular_24.bdf"


def _load_big_font():
    if getattr(sys.implementation, "name", "") == "circuitpython":
        # On hardware, copy the .bdf onto the device under /fonts/.
        from adafruit_bitmap_font import bitmap_font
        return bitmap_font.load_font("/fonts/" + _FONT_NAME)
    # Desktop simulator: use the font bundled with scrollkit.
    from scrollkit.simulator.adafruit_bitmap_font import bitmap_font
    path = os.path.join(os.path.dirname(__file__), "..", "..", "src",
                        "scrollkit", "simulator", "fonts", _FONT_NAME)
    return bitmap_font.load_font(path)


BIG_FONT = _load_big_font()


class BigRainbowScroll(DisplayContent):
    """Scrolls big-font text with a flowing per-letter rainbow."""

    BASELINE_Y = 24   # places the ~20px caps around rows 4..23 (with descender room)
    SCROLL_STEP = 2

    def __init__(self, text="SCROLLKIT  "):
        super().__init__(duration=None)
        self.text = text
        self.effects = EffectsEngine()
        self.frame = 0
        self.x = 64
        # Pre-measure each glyph's advance width (this font is variable-width).
        self.widths = [self._advance(ch) for ch in text]
        self.total = sum(self.widths)

    def _advance(self, ch):
        glyph = BIG_FONT.get_glyph(ch) if BIG_FONT else None
        return glyph["dx"] if glyph else 12

    async def render(self, display):
        self.frame += 1
        self.x -= self.SCROLL_STEP
        if self.x < -self.total:
            self.x = display.width

        x = self.x
        for i, ch in enumerate(self.text):
            w = self.widths[i]
            if ch != " " and -w <= x <= display.width:   # skip spaces / off-screen
                color = self.effects.get_rainbow_color(((i * 2 + self.frame) % 30) / 30.0)
                await display.draw_text(ch, x, self.BASELINE_Y, color, font=BIG_FONT)
            x += w


class RainbowApp(ScrollKitApp):
    def __init__(self):
        super().__init__(enable_web=False, update_interval=10)
        self.content = BigRainbowScroll()

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
            await self.display.create_window("ScrollKit - Big Rainbow (medium)")


if __name__ == "__main__":
    asyncio.run(RainbowApp().run())
