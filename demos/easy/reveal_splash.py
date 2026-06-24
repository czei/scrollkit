#!/usr/bin/env python3
"""ScrollKit demo (EASY): Reveal Splash.

Shows the reveal-splash effect: all 2048 LEDs light up at once, then wink off
randomly until only the logo text remains, then the display transitions into a
scrolling message.

``pixels_from_text`` converts a string + position into the pixel coordinates
that stay on.  The 5×7 built-in font covers full printable ASCII.  For pixel
art or a custom logo, pass your own ``[(x, y), ...]`` list instead.

Run on desktop (opens a pygame window):

    PYTHONPATH=src python demos/easy/reveal_splash.py

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
from scrollkit.display.content import ScrollingText
from scrollkit.effects import show_reveal_splash, pixels_from_text


# ---------------------------------------------------------------------------
# Build the pixel list for the logo once at import time (no per-frame cost).
#
# Layout on a 64×32 display:
#   "SCROLL" — 6 chars × 6 px = 36 px wide, centred → x = (64-36)//2 = 14
#   "KIT"    — 3 chars × 6 px = 18 px wide, centred → x = (64-18)//2 = 23
#   Each line is 7 px tall; leave ~4 px gap and ~5 px margins top/bottom.
#
# To use a different word, change the strings and recalculate x:
#   x = (display_width - len(word) * 6) // 2
# ---------------------------------------------------------------------------
LOGO_PIXELS = (
    pixels_from_text("SCROLL", x=14, y=8)
    + pixels_from_text("KIT",  x=23, y=20)
)


class RevealSplashDemo(ScrollKitApp):

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
            await self.display.create_window("ScrollKit - Reveal Splash (easy)")

        # --- splash -----------------------------------------------------------
        # All LEDs on → wink off non-logo pixels → hold 2 s → remove overlay.
        # Swap color or off_per_frame to change the feel:
        #   color=0x00AAFF  — blue logo
        #   off_per_frame=6 — slower, more dramatic
        #   off_per_frame=28 — fast, snappy
        await show_reveal_splash(
            self.display,
            pixels=LOGO_PIXELS,
            color=0xFFFF00,       # yellow
            off_per_frame=14,
            hold_seconds=2.0,
        )

        # --- main content after the splash ------------------------------------
        self.content_queue.add(
            ScrollingText(
                "Welcome to ScrollKit — build scrolling LED displays in Python.",
                y=12,
                color=0x00AAFF,
                speed=30,   # explicit px/sec — demos should not depend on settings.json
            )
        )


if __name__ == "__main__":
    if _support is not None:
        _support.main(RevealSplashDemo(), "ScrollKit reveal-splash demo (easy)")
    else:
        asyncio.run(RevealSplashDemo().run())
