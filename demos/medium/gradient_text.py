#!/usr/bin/env python3
"""ScrollKit demo (MEDIUM): gradient / multi-colour text fill.

Normal ``StaticText`` / ``ScrollingText`` is one flat colour. Pass a ``palette``
(two colours, or several stops) plus a ``direction`` and the text is filled with a
gradient instead — a subtle way to add depth without it looking garish. The
gradient is *locked to the letters*, so it scrolls with the text.

The colours come from the continuous generators in ``scrollkit.display.colors``
(no named palettes): ``depth_palette(color)`` derives a tasteful close shade from a
single base colour, while ``gradient`` / ``multi_gradient`` build any ramp you like.

Note on hardware: the panel is RGB444 (16 levels per channel) at the default
``bit_depth=4``, so very close colours can band into a step or two — the simulator
previews finer than the panel shows. Keep stops far enough apart to survive that,
and prefer ``"vertical"`` for a "lit from above" depth look.

Run on desktop:

    PYTHONPATH=src python demos/medium/gradient_text.py
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
from scrollkit.display.content import ScrollingText, StaticText
from scrollkit.display.colors import depth_palette, multi_gradient


class GradientTextApp(ScrollKitApp):
    """Cycles a few gradient text fills next to a flat-colour control line."""

    def __init__(self):
        super().__init__(enable_web=False, update_interval=3600)

    async def create_display(self):
        if _support is not None:
            return _support.simulator_display(getattr(self, "opts", None))
        try:
            from scrollkit.display.simulator import SimulatorDisplay
            return SimulatorDisplay(width=64, height=32)
        except ImportError:
            return await super().create_display()

    async def setup(self):
        if hasattr(self.display, "create_window"):
            await self.display.create_window("ScrollKit - Gradient Text (medium)")

        q = self.content_queue

        # 1) Subtle vertical depth from ONE base colour (the common case) — on
        #    mixed-case prose with descenders, which baseline-aligns correctly.
        q.add(ScrollingText("Jungle Cruise", y=12, speed=22,
                            palette=depth_palette(0x66CCFF, strength=0.45)))

        # 2) Two-colour vertical gradient (highlight -> shadow) held static.
        q.add(StaticText("ON TIME", x=8, y=12, duration=3.0,
                         palette=(0xA0FFC0, 0x205038), direction="vertical"))

        # 3) Multi-stop horizontal sweep across the whole phrase.
        q.add(ScrollingText("SCROLLKIT", y=12, speed=22, direction="horizontal",
                            palette=multi_gradient((0x102840, 0x2060A0, 0x66CCFF), 12)))

        # 4) Flat-colour control line, for comparison with the gradients above.
        q.add(ScrollingText("flat colour", y=12, speed=22, color=0x66CCFF))


if __name__ == "__main__":
    if _support is not None:
        _support.main(GradientTextApp(), "ScrollKit gradient-text demo (medium)")
    else:
        asyncio.run(GradientTextApp().run())
