"""SwarmReveal true-color and reverse modes (0.9.0)."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.simulator import SimulatorDisplay
from scrollkit.effects.reveal_splash import pixels_from_text
from scrollkit.effects.swarm_reveal import SwarmReveal
from scrollkit.simulator.core.color_utils import rgb888_to_rgb565


def _p565(c):
    """The sim Palette stores RGB565; compare through the same conversion."""
    return rgb888_to_rgb565((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF)


async def _make():
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    return d


def _run(sw, max_steps=6000):
    steps = 0
    while not sw.is_complete and steps < max_steps:
        sw.step()
        steps += 1
    return steps


@pytest.mark.asyncio
async def test_index_map_paints_exact_indices():
    d = await _make()
    px = list(pixels_from_text("OWL", x=14, y=13))
    colors = (0xB02318, 0xFFB030, 0xFFF1D8)
    imap = {p: 1 + (i % 3) for i, p in enumerate(px)}
    sw = SwarmReveal(px, text_colors=colors, index_map=imap, num_birds=20)
    sw.start(d)
    assert _run(sw) < 6000 and sw.is_complete
    for p, want in imap.items():
        assert sw._text_bmp[p[0], p[1]] == want
    sw.detach()


@pytest.mark.asyncio
async def test_pixel_colors_builds_palette_and_paints_true_color():
    d = await _make()
    px = list(pixels_from_text("7", x=28, y=13))
    pixel_colors = {p: (0xB02318 if i % 2 else 0xFFB030)
                    for i, p in enumerate(px)}
    sw = SwarmReveal(px, pixel_colors=pixel_colors, num_birds=16)
    sw.start(d)
    assert _run(sw) < 6000 and sw.is_complete
    pal = sw._text_tile.pixel_shader
    for p, want in pixel_colors.items():
        assert pal[sw._text_bmp[p[0], p[1]]] == _p565(want)
    sw.detach()


def test_pixel_colors_is_exclusive_and_index_map_needs_ramp():
    with pytest.raises(ValueError):
        SwarmReveal([(1, 1)], pixel_colors={(1, 1): 0xFF0000},
                    text_colors=(0xFF0000,))
    with pytest.raises(ValueError):
        SwarmReveal([(1, 1)], index_map={(1, 1): 1})


@pytest.mark.asyncio
async def test_reverse_prelights_then_carries_everything_away():
    d = await _make()
    px = list(pixels_from_text("GO", x=22, y=13))
    sw = SwarmReveal(px, reverse=True, num_birds=20)
    sw.start(d)
    lit = {p for p in px if sw._text_bmp[p[0], p[1]] == 1}
    assert lit == set(px)                       # fully lit at start
    assert _run(sw) < 6000 and sw.is_complete
    assert all(sw._text_bmp[x, y] == 0
               for x in range(64) for y in range(32))
    layers = len(d._layer_group)
    sw.detach()
    assert len(d._layer_group) == layers - 2
