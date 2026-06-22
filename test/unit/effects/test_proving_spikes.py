"""Proving spikes: a minimal IrisSnap transition and a minimal palette-animated
BitmapText, each a thin vertical consumer of the Phase-3 foundation. They validate
gfx / add_layer / OverlayMask / easing / palette before the API is frozen, and
must pass the strict feasibility gate at 20 fps.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import DisplayContent
from scrollkit.display.bitmap_text import BitmapText, RainbowChase
from scrollkit.effects.transitions import IrisSnap
from scrollkit.dev import run_headless
import scrollkit.simulator.bitmaptools as bt


async def _make_display():
    from scrollkit.display.simulator import SimulatorDisplay
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    return d


# --- IrisSnap: cover -> swap-while-covered -> reveal, bounded writes ----------

@pytest.mark.asyncio
async def test_iris_snap_covers_then_swaps_then_reveals():
    d = await _make_display()
    t = IrisSnap(duration_frames=5)
    swaps = []
    await t.start(d, lambda: swaps.append(1))
    for _ in range(5):                       # cover phase
        await t.render(d)
    bm = t._mask.bitmap
    # at peak cover the mask hides ALL content (fully opaque), and the swap has
    # NOT happened yet — it must run while covered.
    assert all(bm[x, y] == 1 for x in range(d.width) for y in range(d.height))
    assert swaps == []
    await t.render(d)                        # first reveal frame: swap fires here
    assert swaps == [1]
    for _ in range(10):                      # finish the reveal
        await t.render(d)
    assert t.is_complete
    assert all(bm[x, y] == 0 for x in range(d.width) for y in range(d.height))


@pytest.mark.asyncio
async def test_iris_snap_per_frame_writes_are_bounded(monkeypatch):
    d = await _make_display()
    t = IrisSnap(duration_frames=6)
    await t.start(d, lambda: None)
    orig = bt.fill_region

    def counting(*a, **k):
        counting.n += 1
        return orig(*a, **k)
    counting.n = 0
    monkeypatch.setattr(bt, "fill_region", counting)

    peak = 0
    for _ in range(12):
        counting.n = 0
        await t.render(d)
        peak = max(peak, counting.n)
    # at most ~one span per row plus a couple — never a 2048-pixel repaint.
    assert peak <= 2 * d.height + 4


# --- BitmapText: palette animates with NO glyph rebuild ----------------------

@pytest.mark.asyncio
async def test_bitmap_text_palette_rotates_without_glyph_rebuild():
    d = await _make_display()
    text = BitmapText("RAINBOW", y=12, palette_effect=RainbowChase(), scroll_speed=30)
    await text.render(d)                     # builds the indexed bitmap once
    bitmap0 = text._bitmap
    color_before = text._palette[1]
    for _ in range(5):
        await text.render(d)
    assert text._bitmap is bitmap0           # same bitmap object -> no rebuild
    assert text._palette[1] != color_before  # palette rotated -> output changed


@pytest.mark.asyncio
async def test_bitmap_text_renders_lit_pixels():
    d = await _make_display()
    text = BitmapText("RAINBOW", y=12)
    await text.render(d)
    lit = sum(1 for x in range(text._width) for y in range(7) if text._bitmap[x, y] != 0)
    assert lit > 0


@pytest.mark.asyncio
async def test_bitmap_text_stop_detaches_its_layer():
    d = await _make_display()
    text = BitmapText("RAINBOW", y=12)
    await text.render(d)                     # builds + adds its layer
    assert len(d._layer_group) == 1
    await text.stop()                        # leaving the queue must remove it
    assert len(d._layer_group) == 0


@pytest.mark.asyncio
async def test_repeated_transitions_do_not_leak_layers():
    d = await _make_display()
    # Run several full transitions back to back; the mask layer must not pile up.
    for _ in range(4):
        t = IrisSnap(duration_frames=4)
        await t.start(d, lambda: None)
        for _ in range(20):                  # well past completion (2*4 frames)
            await t.render(d)
        assert t.is_complete
    assert len(d._layer_group) == 0          # every mask detached on completion


# --- strict feasibility: both spikes pass the gate at 20 fps ------------------

class _IrisContent(DisplayContent):
    def __init__(self):
        super().__init__(duration=None, priority=2)
        self.label = "ALPHA"
        self.t = IrisSnap(duration_frames=6, cover_color=0x303030)
        self._started = False

    async def render(self, display):
        if not self._started:
            await self.t.start(display, self._swap)
            self._started = True
        await display.draw_text(self.label, 6, 12, 0xFFFFFF)
        await self.t.render(display)
        if self.t.is_complete:
            self.t = IrisSnap(duration_frames=6, cover_color=0x303030)
            await self.t.start(display, self._swap)

    def _swap(self):
        self.label = "BETA" if self.label == "ALPHA" else "ALPHA"

    @property
    def is_complete(self):
        return False


class _ProvingApp(ScrollKitApp):
    CONTENT = None

    def __init__(self):
        super().__init__(enable_web=False, update_interval=10)
        self._content = None

    async def create_display(self):
        from scrollkit.display.simulator import SimulatorDisplay
        return SimulatorDisplay(width=64, height=32)

    async def prepare_display_content(self):
        return self._content

    async def setup(self):
        self._content = self.CONTENT()


class _IrisApp(_ProvingApp):
    CONTENT = _IrisContent


class _BitmapContent(DisplayContent):
    def __init__(self):
        super().__init__(duration=None, priority=2)
        self.text = BitmapText("RAINBOW", y=12, palette_effect=RainbowChase())

    async def render(self, display):
        await display.draw_text("*", 30, 26, 0xFFFFFF)   # a guaranteed-lit marker
        await self.text.render(display)

    @property
    def is_complete(self):
        return False


class _BitmapApp(_ProvingApp):
    CONTENT = _BitmapContent


def test_iris_snap_passes_strict_at_20fps():
    result = run_headless(_IrisApp(), frames=120, hardware=True, strict=True)
    assert result.errors == [], result.errors
    assert result.ok is True
    assert result.advanced is True


def test_bitmap_text_passes_strict_at_20fps():
    result = run_headless(_BitmapApp(), frames=120, hardware=True, strict=True)
    assert result.errors == [], result.errors
    assert result.ok is True
    assert result.advanced is True
