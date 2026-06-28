"""Class 3 — palette-animated bitmap text.

Every palette effect changes the rendered output by rewriting palette entries with
NO glyph rebuild (the indexed bitmap object identity is stable across frames); the
expanded 5x7 font covers the printable set; and each effect is strict-feasible at
20 fps.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import DisplayContent
from scrollkit.dev import run_headless
from scrollkit.display.bitmap_text import (
    BitmapText, RainbowChase, NeonTubeCrawl, ChromeSheen, HazardStripes, MonoChase,
    FONT_5x7, GLYPH_W, GLYPH_H, RAMP,
)

PALETTE_EFFECTS = [RainbowChase, NeonTubeCrawl, ChromeSheen, HazardStripes]


async def _make_display():
    from scrollkit.display.simulator import SimulatorDisplay
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    return d


def _ramp_snapshot(text):
    return tuple(text._palette[1 + i] for i in range(RAMP))


# --- font -------------------------------------------------------------------

def test_font_covers_printable_set_and_is_well_formed():
    for ch in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789":
        assert ch in FONT_5x7, ch
    for ch in " .,!?:;-+/=()<>%#@&$'\"_*\\":
        assert ch in FONT_5x7, ch
    # Every glyph is exactly 7 rows of width 5.
    for ch, rows in FONT_5x7.items():
        assert len(rows) == GLYPH_H, ch
        assert all(len(r) == GLYPH_W for r in rows), ch


@pytest.mark.asyncio
async def test_renders_digits_and_punctuation():
    d = await _make_display()
    bt = BitmapText("12:34 PM!", y=12, scroll_speed=20)
    await bt.render(d)
    lit = sum(1 for x in range(bt._width) for y in range(GLYPH_H)
              if bt._bitmap[x, y] != 0)
    assert lit > 0


# --- palette animates with no glyph rebuild ---------------------------------

@pytest.mark.asyncio
@pytest.mark.parametrize("effect_cls", PALETTE_EFFECTS)
async def test_palette_animates_without_glyph_rebuild(effect_cls):
    d = await _make_display()
    bt = BitmapText("CHROME 88", y=12, palette_effect=effect_cls(), scroll_speed=20)
    await bt.render(d)                       # builds the indexed bitmap once
    bitmap0 = bt._bitmap
    before = _ramp_snapshot(bt)
    changed = False
    for _ in range(2 * RAMP + 2):
        await bt.render(d)
        if _ramp_snapshot(bt) != before:
            changed = True
    assert bt._bitmap is bitmap0, effect_cls.__name__    # same object -> no rebuild
    assert changed, effect_cls.__name__                  # palette actually animated


# --- strict feasibility: each palette effect passes the gate at 20 fps -------

class _PaletteContent(DisplayContent):
    FACTORY = None

    def __init__(self):
        super().__init__(duration=None, priority=2)
        self.text = BitmapText("SCROLLKIT 2026", y=12,
                               palette_effect=self.FACTORY(), scroll_speed=24)

    async def render(self, display):
        await display.draw_text("*", 30, 26, 0xFFFFFF)   # a guaranteed-lit marker
        await self.text.render(display)

    @property
    def is_complete(self):
        return False


def _app(content_cls):
    class _App(ScrollKitApp):
        def __init__(self):
            super().__init__(enable_web=False, update_interval=10)
            self._c = None

        async def create_display(self):
            from scrollkit.display.simulator import SimulatorDisplay
            return SimulatorDisplay(width=64, height=32)

        async def prepare_display_content(self):
            return self._c

        async def setup(self):
            self._c = content_cls()
    return _App()


@pytest.mark.parametrize("effect_cls", PALETTE_EFFECTS)
def test_palette_effect_passes_strict_at_20fps(effect_cls):
    content_cls = type("_C", (_PaletteContent,),
                       {"FACTORY": staticmethod(effect_cls)})
    result = run_headless(_app(content_cls), frames=120, hardware=True, strict=True)
    assert result.errors == [], (effect_cls.__name__, result.errors)
    assert result.ok is True
    assert result.advanced is True


# --- queue-safe completion (complete_after_passes) --------------------------

@pytest.mark.asyncio
async def test_default_banner_never_completes():
    """Default (complete_after_passes=None) keeps the persistent-banner behaviour."""
    d = await _make_display()
    bt = BitmapText("HI", y=12, scroll_speed=30)
    for _ in range(200):
        await bt.render(d)
        assert bt.is_complete is False


@pytest.mark.asyncio
async def test_completes_after_one_full_scroll_pass():
    """complete_after_passes=1 -> completes once the text has fully scrolled off,
    and only AFTER it could actually have scrolled across (not instantly)."""
    d = await _make_display()
    bt = BitmapText("SPACE MOUNTAIN", y=12, scroll_speed=30, complete_after_passes=1)
    await bt.start()
    frame = None
    for f in range(600):
        await bt.render(d)
        if bt.is_complete:
            frame = f
            break
    assert frame is not None, "never completed"
    assert frame > 30, "completed before it could have scrolled across the panel"


@pytest.mark.asyncio
async def test_completion_is_frame_based_not_wallclock():
    """Regression: completion must NOT depend on wall-clock. Starving the clock
    (what a low frame rate accumulates) must not end the pass early — otherwise a
    heavy concurrent effect would cut the text off mid-scroll."""
    async def frames_to_complete(starve_clock):
        d = await _make_display()
        bt = BitmapText("SPACE MOUNTAIN", y=12, palette_effect=MonoChase(0x00AAFF),
                        scroll_speed=30, complete_after_passes=1)
        await bt.start()
        for f in range(600):
            if starve_clock:
                bt._start_time -= 9999      # pretend huge wall-clock elapsed
            await d.clear()
            await bt.render(d)
            await d.show()
            if bt.is_complete:
                return f
        return None

    normal = await frames_to_complete(starve_clock=False)
    starved = await frames_to_complete(starve_clock=True)
    assert normal is not None
    assert normal == starved, "completion depends on wall-clock (the cut-off regression)"


@pytest.mark.asyncio
async def test_start_rebuilds_layer_for_queue_safety():
    """start() resets _built so a re-shown banner re-adds its TileGrid (otherwise it
    would be invisible on the second cycle after stop() detached the layer)."""
    d = await _make_display()
    bt = BitmapText("HI", y=12, scroll_speed=30, complete_after_passes=1)
    await bt.render(d)                       # first build
    assert bt._built is True
    await bt.stop()                          # detaches the tile
    await bt.start()                         # queue cycles it back
    assert bt._built is False                # will rebuild on next render
    assert bt._passes == 0
    await bt.render(d)
    assert bt._built is True
