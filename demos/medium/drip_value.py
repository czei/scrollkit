#!/usr/bin/env python3
"""ScrollKit demo (MEDIUM): Drip-in a changing value.

Shows how to use the drip effect for a *dynamic* value (the ThemeParkWaits
"next ride's wait time" pattern): a large 2x number drips into place, holds as
the live display, then the value changes and the new number drips in — over and
over with different numbers.

The key idea is a single source of truth: both the drip and the "live" number
come from one function, ``pixels_from_font_text`` (the display's own font, at
scale 2). So the pixels that drip in ARE the pixels that stay on screen — there
is no font/position mismatch and no visible snap when the drip finishes. The
assembled overlay simply stays up as the live value until the next update.

This uses the frame-driven ``DripReveal`` directly so the animation runs inside
the normal display loop (a scrolling label keeps moving on top the whole time,
proving the drip composites over other content instead of blacking it out).

Run on desktop (opens a pygame window):

    PYTHONPATH=src python demos/medium/drip_value.py

The same code runs unchanged on an Adafruit MatrixPortal S3.
"""

import sys
import os

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    import _demo_support as _support
except (AttributeError, ImportError):
    _support = None

import asyncio

from scrollkit.app.base import ScrollKitApp
from scrollkit.effects.drip_splash import DripReveal
from scrollkit.effects.text_render import pixels_from_font_text, font_text_width

# Values to cycle through (think: successive ride wait times, in minutes).
VALUES = ["5", "25", "60", "120", "15"]

_SCALE = 2          # 2x big number, matching ThemeParkWaits' wait-time zone
_NUMBER_TOP_Y = 16  # top edge of the number (bottom zone of a 64x32 display)
_HOLD_FRAMES = 40   # frames to hold each assembled value before the next (~2 s)


class DripValueDemo(ScrollKitApp):

    def __init__(self):
        super().__init__(enable_web=False, update_interval=30)

    async def create_display(self):
        if _support is not None:
            return _support.simulator_display(getattr(self, "opts", None))
        try:
            from scrollkit.display.simulator import SimulatorDisplay
            return SimulatorDisplay(width=64, height=32)
        except ImportError:
            return await super().create_display()

    def _drip_for(self, value):
        """Build a centered DripReveal for ``value`` using the display's font."""
        font = self.display.font
        w = font_text_width(font, value, scale=_SCALE)
        x = max(0, (self.display.width - w) // 2)
        pixels = pixels_from_font_text(font, value, x=x, y=_NUMBER_TOP_Y, scale=_SCALE)
        return DripReveal(pixels, color=0xFDF5E6, fall_speed=2, stagger=1)

    async def setup(self):
        if hasattr(self.display, "create_window"):
            await self.display.create_window("ScrollKit - Drip Value (medium)")

        i = 0
        reveal = self._drip_for(VALUES[0])
        reveal.start(self.display)
        hold = 0

        # One loop, frame by frame: a label scrolls on top the whole time while
        # the number drips in, holds, then is replaced by the next value's drip.
        name_x = self.display.width
        while self.running:
            await self.display.clear()

            # Top-zone scrolling label (ordinary content, drawn every frame).
            await self.display.draw_text("NEXT RIDE WAIT", int(name_x), 6, 0x0000FF)
            name_x -= 1
            if name_x < -90:
                name_x = self.display.width

            # Advance the drip; once assembled, hold, then swap in the next value.
            if not reveal.is_complete:
                reveal.step()
            else:
                hold += 1
                if hold >= _HOLD_FRAMES:
                    reveal.detach()                 # drop the finished overlay
                    i = (i + 1) % len(VALUES)
                    reveal = self._drip_for(VALUES[i])
                    reveal.start(self.display)
                    hold = 0

            if await self.display.show() is False:  # window closed
                reveal.detach()
                self._request_shutdown()
                return
            await asyncio.sleep(0.05)               # ~20 fps app-loop cadence


if __name__ == "__main__":
    if _support is not None:
        _support.main(DripValueDemo(), "ScrollKit drip-value demo (medium)")
    else:
        asyncio.run(DripValueDemo().run())
