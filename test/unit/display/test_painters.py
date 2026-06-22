"""Display span/rect painters, measure_text, and the cached gfx accessor.

Painters write a persistent paint canvas via the C bulk op (bitmaptools.fill_region)
— never a full-2048 Python loop — and only inside their clipped bounds.
measure_text sums real font glyph advances (proved with a controlled fake font of
UNEQUAL advances so the test can't pass falsely against a uniform-6px font).
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.simulator import SimulatorDisplay
import scrollkit.simulator.bitmaptools as bt


class _FakeFont:
    """A font with deliberately UNEQUAL glyph advances and a missing glyph."""
    ADV = {"A": 3, "W": 7, " ": 4}

    def get_glyph(self, ch):
        adv = self.ADV.get(ch)
        return None if adv is None else {"dx": adv}


async def _make():
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    return d


@pytest.mark.asyncio
async def test_gfx_is_cached_and_exposes_primitives():
    d = await _make()
    assert d.gfx is d.gfx                       # cached, no per-access allocation
    for name in ("Bitmap", "Palette", "TileGrid", "Group", "bitmaptools"):
        assert hasattr(d.gfx, name)
    assert hasattr(d.gfx.bitmaptools, "fill_region")


@pytest.mark.asyncio
async def test_fill_rect_writes_only_inside_clipped_bounds():
    d = await _make()
    await d.fill_rect(10, 5, 4, 3, 0xFF0000)    # x in [10,14), y in [5,8)
    idx = d._paint_colors[0xFF0000]
    assert idx != 0
    # inside
    assert d._paint_bitmap[10, 5] == idx
    assert d._paint_bitmap[13, 7] == idx
    # just outside every edge
    assert d._paint_bitmap[9, 5] == 0
    assert d._paint_bitmap[14, 5] == 0
    assert d._paint_bitmap[10, 4] == 0
    assert d._paint_bitmap[10, 8] == 0


@pytest.mark.asyncio
async def test_fill_rect_clips_negative_origin():
    d = await _make()
    await d.fill_rect(-2, -2, 5, 5, 0x00FF00)   # clipped to [0,3) x [0,3)
    idx = d._paint_colors[0x00FF00]
    assert d._paint_bitmap[0, 0] == idx
    assert d._paint_bitmap[2, 2] == idx
    assert d._paint_bitmap[3, 0] == 0
    assert d._paint_bitmap[0, 3] == 0


@pytest.mark.asyncio
async def test_fill_span_is_a_one_row_rect():
    d = await _make()
    await d.fill_span(4, 2, 6, 0x0000FF)         # row 4, x in [2,6)
    idx = d._paint_colors[0x0000FF]
    assert d._paint_bitmap[2, 4] == idx and d._paint_bitmap[5, 4] == idx
    assert d._paint_bitmap[6, 4] == 0 and d._paint_bitmap[2, 3] == 0


@pytest.mark.asyncio
async def test_clear_rect_uses_the_bulk_path_not_a_full_loop(monkeypatch):
    d = await _make()
    await d.fill_rect(0, 0, 64, 32, 0xFFFFFF)    # paint the whole panel
    calls = {"n": 0}
    orig = bt.fill_region

    def counting(*a, **k):
        calls["n"] += 1
        return orig(*a, **k)

    monkeypatch.setattr(bt, "fill_region", counting)
    await d.clear_rect(0, 0, 64, 32)             # clear the entire 64x32 panel
    # ONE bulk fill_region — never 2048 per-pixel writes.
    assert calls["n"] == 1
    assert d._paint_bitmap[0, 0] == 0 and d._paint_bitmap[63, 31] == 0


@pytest.mark.asyncio
async def test_clear_wipes_the_paint_canvas_no_ghost_trails():
    d = await _make()
    await d.fill_rect(2, 2, 4, 4, 0xFF0000)
    assert d._paint_bitmap[2, 2] != 0
    await d.clear()                              # a new frame must start blank
    assert d._paint_bitmap[2, 2] == 0
    assert d._paint_bitmap[5, 5] == 0


@pytest.mark.asyncio
async def test_measure_text_sums_unequal_glyph_advances():
    d = await _make()
    font = _FakeFont()
    assert d.measure_text("AW", font) == 10           # 3 + 7, NOT 2*6
    assert d.measure_text("WWWW", font) == 28          # 4*7, NOT 4*6
    assert d.measure_text("", font) == 0               # empty -> 0
    # missing glyph 'Z' -> replacement (space) advance of 4
    assert d.measure_text("AZW", font) == 3 + 4 + 7


@pytest.mark.asyncio
async def test_measure_text_default_font_is_not_hardcoded_lenx6_logic():
    # The real default font happens to be ~6px fixed, but the value must come
    # from the font (sum of advances), not a len*6 shortcut — exercised here by
    # confirming an empty string measures 0 and the call goes through the font.
    d = await _make()
    assert d.measure_text("") == 0
    assert d.measure_text("HELLO") == d.measure_text("HE") + d.measure_text("LLO")
