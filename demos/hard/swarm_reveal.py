#!/usr/bin/env python3
"""ScrollKit demo (HARD): Swarm reveal — a flock assembles the text.

A small flock of "birds" (think bees) flies in with classic boids flocking —
separation, alignment, cohesion — and as each bird reaches its assigned target
pixel it delivers it: the pixel lights up permanently. Pixels accumulate into the
logo, then the flock disperses and leaves the finished text. The demo loops,
re-forming the text each time.

This is the device-feasible version of the old 150-bird boids experiment (which
only ran via precomputed paths). The flock is kept small on purpose — the plan's
own note was "fewer birds flock more visibly" — and the per-frame cost is one
combined neighbor pass plus O(1) capture per bird, so it stays within the
~20 fps device budget. Tune ``num_birds`` to trade fill speed for headroom.

Run on desktop (opens a pygame window):

    PYTHONPATH=src python demos/hard/swarm_reveal.py

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
from scrollkit.effects.swarm_reveal import SwarmReveal
from scrollkit.effects.reveal_splash import pixels_from_text

# "SCROLL" / "KIT" on two lines (same layout as the reveal/drip demos).
LOGO_PIXELS = (
    pixels_from_text("SCROLL", x=14, y=8)
    + pixels_from_text("KIT", x=23, y=20)
)


class SwarmRevealDemo(ScrollKitApp):

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
            await self.display.create_window("ScrollKit - Swarm Reveal (hard)")

        # Loop: flock assembles the logo, holds, then re-forms. Driven frame by
        # frame so the window stays responsive and closes cleanly.
        while self.running:
            swarm = SwarmReveal(
                LOGO_PIXELS,
                text_color=0xFFCC00,    # amber text
                bird_color=0xFFE08A,    # pale-yellow "bees"
                num_birds=14,           # device-safe (~25ms/frame on an S3); the
                                        # desktop sim can go higher for a denser flock
                bird_speed=2.4,
            )
            swarm.start(self.display)

            steps = 0
            while not swarm.is_complete and steps < 4000:
                swarm.step()
                steps += 1
                if await self.display.show() is False:   # window closed
                    swarm.detach()
                    self._request_shutdown()
                    return
                await asyncio.sleep(0.05)                 # ~20 fps

            # Hold the finished text, then re-form.
            for _ in range(40):
                if await self.display.show() is False:
                    swarm.detach()
                    self._request_shutdown()
                    return
                await asyncio.sleep(0.05)
            swarm.detach()


if __name__ == "__main__":
    if _support is not None:
        _support.main(SwarmRevealDemo(), "ScrollKit swarm-reveal demo (hard)")
    else:
        asyncio.run(SwarmRevealDemo().run())
