"""Font/scale text composition + frame-driven DripReveal (single source of truth).

These cover the seamless drip-in-a-value path: the same pixel-composition function
feeds both the drip and the live image, so they are identical by construction.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.simulator import SimulatorDisplay
from scrollkit.effects import (
    DripReveal,
    show_drip_splash,
    pixels_from_font_text,
    font_text_width,
)
from scrollkit.effects.text_render import _glyph_fields


def test_feasibility_lives_on_the_class_not_the_function():
    # CircuitPython can't set attributes on function objects -> FEASIBILITY must
    # live on the class. Attaching it to the wrapper crashes effects import
    # on-device (but not on desktop CPython, hence this guard).
    assert isinstance(DripReveal.FEASIBILITY, dict)
    assert not hasattr(show_drip_splash, "FEASIBILITY")


async def _make():
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    return d


@pytest.mark.asyncio
async def test_compose_produces_lit_pixels_on_screen():
    d = await _make()
    px = pixels_from_font_text(d.font, "45", x=10, y=8, scale=1)
    assert px, "expected some lit pixels"
    # All pixels are integer tuples within the text's region.
    assert all(isinstance(p, tuple) and len(p) == 2 for p in px)
    assert all(x >= 10 and y >= 8 for (x, y) in px)


@pytest.mark.asyncio
async def test_scale_quadruples_pixel_count():
    d = await _make()
    one = pixels_from_font_text(d.font, "45", x=0, y=0, scale=1)
    two = pixels_from_font_text(d.font, "45", x=0, y=0, scale=2)
    # Each lit cell becomes a 2x2 block -> exactly 4x the pixels.
    assert len(two) == 4 * len(one)


@pytest.mark.asyncio
async def test_width_matches_pixel_extent_and_scales():
    d = await _make()
    assert font_text_width(d.font, "45", scale=2) == 2 * font_text_width(d.font, "45", scale=1)
    # The advance width is >= the lit pixels' horizontal extent.
    px = pixels_from_font_text(d.font, "45", x=0, y=0, scale=1)
    max_x = max(x for (x, _y) in px)
    assert font_text_width(d.font, "45", scale=1) >= max_x


def test_glyph_fields_handles_dict_form():
    # Simulator-style glyph dict: 'dx' is the advance, per-glyph bitmap (origin 0).
    g = {"bitmap": None, "width": 5, "height": 7, "x_offset": 0, "dx": 6}
    bmp, gw, gh, xoff, adv, sx, sy = _glyph_fields(g)
    assert (gw, gh, adv, sx, sy) == (5, 7, 6, 0, 0)


def test_glyph_fields_handles_packed_sheet_object():
    # Device-style packed font: one wide sheet shared by all glyphs; the glyph
    # lives at tile_index -> sheet_x = (index % tiles_per_row) * width.
    class _Sheet:
        width = 570

        def __getitem__(self, key):
            return 0

    class _Glyph:
        bitmap = _Sheet()
        width = 6
        height = 12
        dx = 0
        shift_x = 6
        tile_index = 20

    bmp, gw, gh, xoff, adv, sx, sy = _glyph_fields(_Glyph())
    assert gw == 6 and adv == 6
    assert sx == 120 and sy == 0     # 20 * 6, single row (570 // 6 = 95 per row)


@pytest.mark.asyncio
async def test_drip_assembles_exactly_the_target_pixels():
    d = await _make()
    px = pixels_from_font_text(d.font, "60", x=12, y=10, scale=2)
    target = set(px)
    rev = DripReveal(px, color=0xFDF5E6, fall_speed=2, stagger=1)
    rev.start(d)
    assert rev.has_pixels
    guard = 0
    while not rev.is_complete and guard < 1000:
        rev.step()
        guard += 1
    final = {(x, y) for x in range(d.width) for y in range(d.height)
             if rev._bitmap[x, y] == 1}
    assert final == target          # dripped image == live image, by construction
    assert len(d._layer_group) == 1
    rev.detach()
    assert len(d._layer_group) == 0


@pytest.mark.asyncio
async def test_drip_overlay_background_is_transparent():
    d = await _make()
    px = pixels_from_font_text(d.font, "7", x=0, y=0, scale=1)
    rev = DripReveal(px)
    rev.start(d)
    # Index 0 transparent so the drip composites over content below it.
    assert rev._tile.pixel_shader.is_transparent(0)
    rev.detach()


@pytest.mark.asyncio
async def test_empty_pixels_is_safe():
    d = await _make()
    rev = DripReveal([])
    rev.start(d)
    assert not rev.has_pixels
    assert rev.step() is True       # immediately complete, no crash
    rev.detach()
