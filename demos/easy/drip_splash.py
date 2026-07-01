#!/usr/bin/env python3
"""ScrollKit demo (EASY): Drip Splash.

Shows the drip-splash effect: the screen starts blank, then every LED of the
logo appears at the top of its column and falls straight down, settling into
its final row — assembling the text drop by drop. The demo loops forever,
replaying the drip at different speeds so you can see the full range of the
effect, from a gentle separated drip to whole columns slamming down at once.

It's the inverse of the reveal-splash demo (all-on → wink off): here it's
all-off → drip on. ``pixels_from_text`` builds the target pixel list from a
string; pass your own ``[(x, y), ...]`` list for custom pixel art instead.

Run on desktop (opens a pygame window):

    PYTHONPATH=src python demos/easy/drip_splash.py

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
from scrollkit.effects.drip_splash import show_drip_splash
from scrollkit.effects.reveal_splash import pixels_from_text


# ---------------------------------------------------------------------------
# Build the target pixel list once (no per-frame cost).
#
# Layout on a 64×32 display, two lines of the built-in 5×7 font:
#   "PIXEL" — 5 chars × 6 px = 30 px wide, centred → x = (64-30)//2 = 17
#   "RAIN"  — 4 chars × 6 px = 24 px wide, centred → x = (64-24)//2 = 20
#   Line 1 occupies rows 8..14, line 2 rows 20..26.
#
# To use a different word, change the strings and recompute x:
#   x = (display_width - len(word) * 6) // 2
# ---------------------------------------------------------------------------
LOGO_PIXELS = (
    pixels_from_text("PIXEL", x=17, y=8)
    + pixels_from_text("RAIN", x=20, y=20)
)


class DripSplashDemo(ScrollKitApp):

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

    async def setup(self):
        if hasattr(self.display, "create_window"):
            await self.display.create_window("ScrollKit - Drip Splash (easy)")

        # Replay the drip forever at different speeds. Each entry is
        # (fall_speed, stagger, color):
        #   fall_speed — rows a drop descends per frame (higher = faster fall)
        #   stagger    — frames between successive drops in a column
        #                (higher = sparser drip; 0 = whole column at once)
        styles = [
            (1, 4, 0x00CCFF),   # gentle, well-separated cyan drops
            (1, 1, 0x00FF66),   # steady green downpour
            (2, 2, 0xFFCC00),   # quick amber fall
            (3, 0, 0xFF3366),   # red — whole columns slam down at once
        ]

        # setup() runs with self.running already True; loop until the window
        # closes. show_drip_splash returns False when the display reports a
        # close, so we stop cleanly. Running the whole show here means the
        # display loop never needs queue content.
        i = 0
        while self.running:
            fall_speed, stagger, color = styles[i % len(styles)]
            ok = await show_drip_splash(
                self.display,
                pixels=LOGO_PIXELS,
                color=color,
                fall_speed=fall_speed,
                stagger=stagger,
                hold_seconds=1.0,
            )
            if ok is False:           # window closed
                self._request_shutdown()
                return
            i += 1


if __name__ == "__main__":
    if _support is not None:
        _support.main(DripSplashDemo(), "ScrollKit drip-splash demo (easy)")
    else:
        asyncio.run(DripSplashDemo().run())
