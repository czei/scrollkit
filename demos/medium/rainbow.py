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

# Run directly from the repo (no PYTHONPATH) and pull in the shared demo helpers
# (CLI flags + display factory). None of this exists on CircuitPython, where the
# device runs the app with defaults.
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    import _demo_support as _support
except (AttributeError, ImportError):
    _support = None

import asyncio

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import DisplayContent
from scrollkit.effects.effects import EffectsEngine

# A tall, bold font that fills most of the 32px height while leaving clear
# margins. (Junction_regular_24 was even taller but its ascent == cap height,
# so it had zero padding above the caps and looked clipped at the top.)
_FONT_NAME = "LibreBodoniv2002-Bold-27.bdf"


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

    BASELINE_Y = 22   # default; calibrate() replaces this with a centered value
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

    async def calibrate(self, display):
        """Center the text vertically by measuring its real rendered extent.

        A bitmap font's glyph boxes include padding/ascenders that don't match
        the inked pixels, so a hardcoded baseline is fragile. Instead we draw
        each letter once, read back the lit rows, and pick the baseline that
        centers the actual ink. On platforms without pixel read-back (real
        hardware) this quietly keeps the default baseline.
        """
        try:
            ref = 24
            top, bottom = 99, -1
            for ch in set(self.text.replace(" ", "")):
                await display.clear()
                await display.draw_text(ch, 2, ref, 0xFFFFFF, font=BIG_FONT)
                display.display.refresh(minimum_frames_per_second=0)
                buf = display.matrix.pixel_buffer.get_buffer()
                lit = [y for y in range(display.height)
                       for x in range(display.width) if tuple(buf[y, x]) != (0, 0, 0)]
                if lit:
                    top, bottom = min(top, min(lit)), max(bottom, max(lit))
            await display.clear()
            if bottom >= 0:
                block = (bottom - top) + 1
                top_margin = max(0, (display.height - block + 1) // 2)
                self.BASELINE_Y = top_margin - (top - ref)
        except Exception:
            pass  # no pixel read-back (hardware) -> keep the default baseline

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
        if _support is not None:
            return _support.simulator_display(getattr(self, "opts", None))
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
        # Center the tall font vertically based on its real rendered extent.
        await self.content.calibrate(self.display)


if __name__ == "__main__":
    if _support is not None:
        _support.main(RainbowApp(), "ScrollKit big-rainbow demo (medium)")
    else:
        asyncio.run(RainbowApp().run())
