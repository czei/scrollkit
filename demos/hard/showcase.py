"""ScrollKit Showcase reel — watch the new foundation effects in the simulator.

A scripted loop that cycles through the signature pieces built on the showcase
foundation:

  1. Palette-animated bitmap text   (Class 3: 5x7 font + RainbowChase)
  2. Fixed-point scrolling text     (speed actually drives motion now)
  3. Iris-snap transition           (Class 2: cover -> swap -> reveal overlay)
  4. Painters + integer easing      (fill_rect bars driven by easing LUTs)

Run it::

    python demos/hard/showcase.py

    # watch it crawl at the modeled MatrixPortal S3 speed:
    python demos/hard/showcase.py --throttle

    # enforce the strict feasibility gate (raises if an effect busts the budget):
    python demos/hard/showcase.py --strict

The SAME content runs unchanged on the MatrixPortal S3.
"""

import asyncio
import os
import sys

# Run directly from the repo (no PYTHONPATH) and pull in the shared demo helpers
# (CLI flags + display factory). None of this exists on CircuitPython, where the
# device runs the app with defaults.
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    import _demo_support as _support
except (AttributeError, ImportError):
    _support = None

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import DisplayContent, ScrollingText
from scrollkit.display.bitmap_text import BitmapText, RainbowChase
from scrollkit.effects.transitions import IrisSnap
from scrollkit.effects.easing import interp, EASE_IN_OUT, BOUNCE, OVERSHOOT


class _Scene:
    """One segment of the reel."""

    async def enter(self, display):
        pass

    async def render(self, display):
        pass

    async def exit(self, display):
        pass

    @property
    def done(self):
        return False


# Hardware-realistic pacing: scroll slow enough to actually READ (~18 px/sec, i.e.
# well under 1 px/frame, which the fixed-point accumulator renders smoothly), and
# hold static screens long enough to take in. Same on the device and simulator.

class NeonBitmapScene(_Scene):
    """Class 3 — palette-animated bitmap text, scrolled slowly enough to read."""

    def __init__(self):
        self.bt = BitmapText("SCROLLKIT  RAINBOW   ", y=11,
                             palette_effect=RainbowChase(period=4), scroll_speed=18,
                             max_width_px=320)
        self.n = 0

    async def render(self, display):
        await display.draw_text("bitmap", 1, 0, 0x303030)
        await self.bt.render(display)
        self.n += 1

    async def exit(self, display):
        self.bt.detach(display)

    @property
    def done(self):
        return self.n >= 240            # ~one slow, readable pass


class TickerScene(_Scene):
    """The ScrollingText fix — a realistic ticker scrolled at a readable speed via
    the fixed-point sub-pixel accumulator (smooth even below 1 px/frame)."""

    def __init__(self):
        self.text = ScrollingText("WELCOME TO SCROLLKIT   ", x=64, y=12,
                                  color=0x66CCFF, speed=18)

    async def render(self, display):
        await display.draw_text("scroll", 1, 0, 0x303030)
        await self.text.render(display)

    @property
    def done(self):
        return self.text.is_complete    # one full readable pass, then move on


class IrisScene(_Scene):
    """Class 2 — an iris-snap transition rotating between info screens, each held
    long enough to read (a realistic info-rotation sign)."""

    SCREENS = [("12:34", 0xFFCC22), ("72 F", 0x66FF88), ("SCROLLKIT", 0xFF66AA)]
    DWELL = 45                          # ~2.25 s to read each screen

    def __init__(self):
        self.i = 0
        self.t = None
        self.dwell = self.DWELL         # show the first screen before transitioning
        self.shown = 0

    async def render(self, display):
        await display.draw_text("iris", 1, 0, 0x303030)
        label, color = self.SCREENS[self.i]
        x = max(0, (display.width - len(label) * 6) // 2)
        await display.draw_text(label, x, 12, color)
        if self.dwell > 0:              # holding a screen so it can be read
            self.dwell -= 1
            if self.dwell == 0:
                self.shown += 1
                self.t = IrisSnap(duration_frames=8, cover_color=0x101840)
                await self.t.start(display, self._swap)
        elif self.t is not None and not self.t.is_complete:
            await self.t.render(display)
            if self.t.is_complete:
                self.dwell = self.DWELL

    def _swap(self):
        self.i = (self.i + 1) % len(self.SCREENS)

    async def exit(self, display):
        if self.t is not None:
            self.t.detach()

    @property
    def done(self):
        return self.shown >= len(self.SCREENS)


class EasingScene(_Scene):
    """Foundation — bounded fill_rect 'meters' (C bulk ops, no per-pixel loop)
    whose widths are driven by the integer easing tables; slow enough to watch
    the curves differ."""

    def __init__(self):
        self.n = 0

    async def render(self, display):
        await display.draw_text("easing", 1, 0, 0x303030)
        w, h = display.width, display.height
        await display.clear_rect(0, 9, w, h - 9)         # wipe the meter area
        p = (self.n * 3) % 510                            # one slow up-and-down sweep
        prog = p if p <= 255 else 510 - p
        await display.fill_rect(2, 11, interp(BOUNCE, 1, w - 4, prog), 5, 0x00FFAA)
        await display.fill_rect(2, 18, interp(EASE_IN_OUT, 1, w - 4, 255 - prog), 5, 0xFF4488)
        await display.fill_rect(2, 25, interp(OVERSHOOT, 1, w - 4, prog), 5, 0xFFAA00)
        self.n += 1

    async def exit(self, display):
        await display.clear_rect(0, 0, display.width, display.height)

    @property
    def done(self):
        return self.n >= 180            # ~one full slow sweep


class ShowcaseReel(DisplayContent):
    """Cycles through the scenes forever."""

    SCENES = [NeonBitmapScene, TickerScene, IrisScene, EasingScene]

    def __init__(self):
        super().__init__(duration=None, priority=2)
        self._i = 0
        self._scene = None

    async def render(self, display):
        if self._scene is None:
            self._scene = self.SCENES[self._i]()
            await self._scene.enter(display)
        await self._scene.render(display)
        if self._scene.done:
            await self._scene.exit(display)
            self._i = (self._i + 1) % len(self.SCENES)
            self._scene = None

    @property
    def is_complete(self):
        return False


class ShowcaseApp(ScrollKitApp):
    def __init__(self):
        super().__init__(enable_web=False, update_interval=10)
        self.content = ShowcaseReel()

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
            await self.display.create_window("ScrollKit Showcase")


if __name__ == "__main__":
    if _support is not None:
        _support.main(ShowcaseApp(), "ScrollKit Showcase reel (hard)")
    else:
        asyncio.run(ShowcaseApp().run())
