"""ScrollKit Showcase reel — every signature effect, announced by name.

A scripted loop that ANNOUNCES each effect on a title card ("NOW SHOWING /
<NAME>") and then demonstrates it, covering the whole showcase catalog:

  Class 1 — characterful scrolling : KineticMarquee, WaveRider, SplitFlap
  Class 2 — theatrical transitions : IrisSnap, VenetianShutters, MosaicResolve,
                                      CRTCollapse, LightSlitRewrite, ColumnRain,
                                      DropFromSky (slides in from any edge)
  Class 3 — palette-animated text  : RainbowChase, NeonTubeCrawl, ChromeSheen,
                                      HazardStripes

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
from scrollkit.display.content import DisplayContent
from scrollkit.display.bitmap_text import (
    BitmapText, RainbowChase, NeonTubeCrawl, ChromeSheen, HazardStripes,
)
from scrollkit.effects.scrolling import KineticMarquee, WaveRider, SplitFlap
from scrollkit.effects.transitions import (
    IrisSnap, VenetianShutters, MosaicResolve, CRTCollapse, LightSlitRewrite,
    ColumnRain, DropFromSky,
)


def _center_x(display, text):
    """Left x that centers a default-font (6 px/char) string on the panel."""
    return max(0, (display.width - len(text) * 6) // 2)


# Vertical layout on the 32-px panel: the effect-name header sits at y=4 (rows 1-7);
# the effect content is centered in the area BELOW it rather than jammed under it.
CONTENT_Y = 20      # Label-based content (Labels center on y -> rows ~17-23)
BITMAP_Y = 16       # BitmapText tile TOP (y is the tile top; 7-px glyphs -> rows ~16-22)


class _Scene:
    """One announced segment of the reel: a title card, then the effect."""

    CATEGORY = "DEMO"
    LABEL = "DEMO"
    TITLE_FRAMES = 26           # ~1.3 s readable announcement

    def __init__(self):
        self._tf = 0
        self._phase = 0         # 0 = title card, 1 = effect

    async def enter(self, display):
        await self.setup(display)

    async def render(self, display):
        if self._phase == 0:
            # The app loop already cleared the content group this frame; just draw
            # the two centered title lines (NOW SHOWING / <NAME>).
            await display.draw_text("NOW SHOWING", _center_x(display, "NOW SHOWING"),
                                    6, 0x2A6CA0)
            await display.draw_text(self.LABEL, _center_x(display, self.LABEL),
                                    16, 0xFFCC33)
            self._tf += 1
            if self._tf >= self.TITLE_FRAMES:
                self._phase = 1
            return
        # Phase 1: keep the effect's name pinned at the top the WHOLE time it runs
        # (not just on the intro card), so a glance always identifies the effect.
        # y=4 sits the header at rows 1-7 (fully on-screen; the Label centers on y),
        # clear of the effect content at y=12 (rows 9-15). For transitions it briefly
        # disappears under the cover, which is expected.
        await display.draw_text(self.LABEL, _center_x(display, self.LABEL), 4, 0x8899AA)
        await self.run(display)

    async def exit(self, display):
        """Detach any persistent layers this scene added (the content group is
        cleared by the loop, but effect layers are not)."""
        pass

    @property
    def done(self):
        return self._phase == 1 and self._effect_done

    # --- subclass hooks -------------------------------------------------------
    async def setup(self, display):
        pass

    async def run(self, display):
        pass

    @property
    def _effect_done(self):
        return True


# --- Class 1: characterful scrolling ----------------------------------------

class _ScrollerScene(_Scene):
    """Announce, then run a Class 1 scroller for one full pass."""

    CATEGORY = "SCROLLER"
    FACTORY = None

    async def setup(self, display):
        self._eff = self.FACTORY()
        await self._eff.start()

    async def run(self, display):
        await self._eff.render(display)

    @property
    def _effect_done(self):
        return self._eff.is_complete


class MarqueeScene(_ScrollerScene):
    LABEL = "MARQUEE"
    FACTORY = staticmethod(lambda: KineticMarquee("SCROLLKIT IN MOTION.",
                                                  y=CONTENT_Y, speed=34))


class WaveScene(_ScrollerScene):
    LABEL = "WAVERIDER"
    # amplitude 4 around the CONTENT_Y baseline keeps the wave clear of the y=4
    # header (peaks rise ~4 px) and the bottom edge (troughs fall ~4 px).
    FACTORY = staticmethod(lambda: WaveRider("RIDING THE WAVE",
                                             y=CONTENT_Y, speed=30, amplitude=4))


class FlapScene(_ScrollerScene):
    LABEL = "SPLITFLAP"
    FACTORY = staticmethod(lambda: SplitFlap("SPLIT FLAP", y=CONTENT_Y, seed=4))


# --- Class 2: theatrical transitions ----------------------------------------

class _TransitionScene(_Scene):
    """Announce, then rotate through info screens using a transition (so you SEE
    the cover -> swap -> reveal a couple of times)."""

    CATEGORY = "TRANSITION"
    FACTORY = None
    SCREENS = (("12:34", 0xFFCC22), ("64 F", 0x66FF88), ("READY", 0xFF66AA))
    CYCLES = 2
    DWELL = 26                  # hold each screen ~1.3 s before transitioning

    async def setup(self, display):
        self._i = 0
        self._shown = 0
        self._dwell = self.DWELL
        self._t = self.FACTORY()
        self._active = False

    async def run(self, display):
        label, color = self.SCREENS[self._i]
        await display.draw_text(label, _center_x(display, label), CONTENT_Y, color)
        if self._dwell > 0:
            self._dwell -= 1
            if self._dwell == 0:
                await self._t.start(display, self._swap)
                self._active = True
        elif self._active:
            await self._t.render(display)
            if self._t.is_complete:
                self._shown += 1
                self._active = False
                self._dwell = self.DWELL
                self._t = self.FACTORY()

    def _swap(self):
        self._i = (self._i + 1) % len(self.SCREENS)

    async def exit(self, display):
        if getattr(self, "_t", None) is not None:
            self._t.detach()

    @property
    def _effect_done(self):
        return self._shown >= self.CYCLES


class IrisScene(_TransitionScene):
    LABEL = "IRIS"
    FACTORY = staticmethod(lambda: IrisSnap(duration_frames=8, cover_color=0x101840))


class VenetianScene(_TransitionScene):
    LABEL = "VENETIAN"
    FACTORY = staticmethod(lambda: VenetianShutters(duration_frames=8,
                                                    cover_color=0x101010))


class MosaicScene(_TransitionScene):
    LABEL = "MOSAIC"
    FACTORY = staticmethod(lambda: MosaicResolve(duration_frames=9,
                                                 cover_color=0x101010, seed=5))


class CRTScene(_TransitionScene):
    LABEL = "CRT FOLD"
    FACTORY = staticmethod(lambda: CRTCollapse(duration_frames=8,
                                               cover_color=0x000000))


class LightSlitScene(_TransitionScene):
    LABEL = "LIGHTSLIT"
    FACTORY = staticmethod(lambda: LightSlitRewrite(duration_frames=9,
                                                    cover_color=0x101010,
                                                    slit_color=0xFFFFFF))


class ColumnRainScene(_TransitionScene):
    LABEL = "RAIN"
    FACTORY = staticmethod(lambda: ColumnRain(cover_color=0x102840))


class _Pos:
    """A minimal content stand-in (just x/y) for DropFromSky to animate in a scene."""

    def __init__(self, x, y):
        self.x = x
        self.y = y


class DropScene(_Scene):
    """Announce, then slide a screen of content in from each edge with DropFromSky —
    top, then bottom, left, right — showing the new directional entry. DropFromSky
    is duck-typed (not an OverlayMask transition): it animates the content's own
    x/y via pre_render_hook, so the scene draws the text at that moving position."""

    CATEGORY = "TRANSITION"
    LABEL = "DROP IN"
    STEPS = (("TOP", 0xFFCC22, "top"),
             ("BOTTOM", 0x66FF88, "bottom"),
             ("LEFT", 0xFF66AA, "left"),
             ("RIGHT", 0x66CCFF, "right"))
    HOLD = 16                       # frames to hold each landed screen before the next

    async def setup(self, display):
        self._i = 0
        self._hold = 0
        self._pos = _Pos(0, CONTENT_Y)
        self._t = DropFromSky(direction=self.STEPS[0][2])
        await self._t.start(display, lambda: None)

    async def run(self, display):
        label, color, _dir = self.STEPS[self._i]
        # Reset to the natural centred position, let the transition pull it to the
        # entry edge for this frame, draw the text there, then advance/restore.
        self._pos.x = _center_x(display, label)
        self._pos.y = CONTENT_Y
        self._t.pre_render_hook(self._pos)
        await display.draw_text(label, self._pos.x, self._pos.y, color)
        await self._t.render(display, self._pos)
        if self._t.is_complete:
            if self._hold < self.HOLD:
                self._hold += 1
            else:
                self._hold = 0
                self._i += 1
                if self._i < len(self.STEPS):
                    self._t = DropFromSky(direction=self.STEPS[self._i][2])
                    await self._t.start(display, lambda: None)

    @property
    def _effect_done(self):
        return self._i >= len(self.STEPS)


# --- Class 3: palette-animated bitmap text ----------------------------------

class _PaletteScene(_Scene):
    """Announce, then scroll palette-animated bitmap text for a readable window."""

    CATEGORY = "BITMAP"
    FACTORY = None              # palette-effect factory
    MSG = "SCROLLKIT  "
    FRAMES = 90

    async def setup(self, display):
        self._bt = BitmapText(self.MSG, y=BITMAP_Y, palette_effect=self.FACTORY(),
                              scroll_speed=20, max_width_px=320)
        self._n = 0

    async def run(self, display):
        await self._bt.render(display)
        self._n += 1

    async def exit(self, display):
        self._bt.detach(display)

    @property
    def _effect_done(self):
        return self._n >= self.FRAMES


class RainbowScene(_PaletteScene):
    LABEL = "RAINBOW"
    FACTORY = staticmethod(lambda: RainbowChase(period=3))


class NeonScene(_PaletteScene):
    LABEL = "NEON TUBE"
    FACTORY = staticmethod(lambda: NeonTubeCrawl(period=2))


class ChromeScene(_PaletteScene):
    LABEL = "CHROME"
    FACTORY = staticmethod(lambda: ChromeSheen(period=1))


class HazardScene(_PaletteScene):
    LABEL = "HAZARD"
    FACTORY = staticmethod(lambda: HazardStripes(period=3))


class ShowcaseReel(DisplayContent):
    """Cycles through every announced scene forever."""

    SCENES = [
        MarqueeScene, WaveScene, FlapScene,                       # Class 1
        IrisScene, VenetianScene, MosaicScene, CRTScene, LightSlitScene,
        ColumnRainScene, DropScene,                               # Class 2
        RainbowScene, NeonScene, ChromeScene, HazardScene,        # Class 3
    ]

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
