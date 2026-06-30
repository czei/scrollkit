"""SwarmReveal: a flock captures target pixels into the assembled image.

Correctness is checked by running to completion and confirming the captured-text
layer equals the target exactly, with bounded per-frame work and clean teardown.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.simulator import SimulatorDisplay
from scrollkit.effects import SwarmReveal, show_swarm_splash, pixels_from_text


def test_feasibility_lives_on_the_class_not_the_function():
    # CircuitPython/MicroPython can't set attributes on function objects, so
    # FEASIBILITY must live on the class. Attaching it to the wrapper function
    # crashes `import scrollkit.effects` on-device (passes on desktop CPython,
    # which is why this guard exists).
    assert isinstance(SwarmReveal.FEASIBILITY, dict)
    assert not hasattr(show_swarm_splash, "FEASIBILITY")


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
async def test_assembles_exactly_the_target():
    d = await _make()
    px = pixels_from_text("BEE", x=23, y=13)
    target = set(px)
    sw = SwarmReveal(px, num_birds=20, bird_speed=2.2)
    sw.start(d)
    steps = _run(sw)
    assert sw.is_complete and steps < 6000
    lit = {(x, y) for x in range(64) for y in range(32) if sw._text_bmp[x, y] == 1}
    assert lit == target            # captured image == target, exactly


@pytest.mark.asyncio
async def test_two_overlay_layers_transparent_then_cleaned_up():
    d = await _make()
    sw = SwarmReveal(pixels_from_text("7", x=30, y=13), num_birds=12)
    sw.start(d)
    assert len(d._layer_group) == 2                     # text + birds
    assert sw._text_tile.pixel_shader.is_transparent(0)
    assert sw._birds_tile.pixel_shader.is_transparent(0)
    _run(sw)
    sw.detach()
    assert len(d._layer_group) == 0


@pytest.mark.asyncio
async def test_birds_layer_pixels_bounded_by_bird_count():
    d = await _make()
    nb = 16
    sw = SwarmReveal(pixels_from_text("AB", x=26, y=13), num_birds=nb)
    sw.start(d)
    # Sample a handful of mid-animation frames; birds layer never lights more
    # than num_birds pixels (one per bird), so per-frame work stays bounded.
    for _ in range(20):
        if sw.is_complete:
            break
        sw.step()
        lit = sum(1 for x in range(64) for y in range(32) if sw._birds_bmp[x, y] == 1)
        assert lit <= nb
    sw.detach()


@pytest.mark.asyncio
async def test_empty_pixels_is_safe():
    d = await _make()
    sw = SwarmReveal([], num_birds=8)
    sw.start(d)
    # No targets -> dispersal begins immediately; completes without error.
    steps = _run(sw, max_steps=200)
    assert sw.is_complete and steps < 200
    sw.detach()


def _rect_pixels(x0, y0, w, h):
    """A solid w×h rectangle of cells with a guaranteed pixel at every bbox edge."""
    return [(x, y) for x in range(x0, x0 + w) for y in range(y0, y0 + h)]


@pytest.mark.asyncio
async def test_text_colors_builds_n_plus_one_entry_palette():
    # A ramp of N colors -> a palette of N+1 entries (index 0 transparent + the
    # ramp at 1..N). The single-color default stays a 2-entry palette.
    d = await _make()
    ramp = (0xFFFF00, 0xFFAA00, 0xFF5500, 0xFF0000)  # 4 yellows -> reds
    sw = SwarmReveal(_rect_pixels(10, 5, 5, 7), text_colors=ramp)
    sw.start(d)
    pal = sw._text_tile.pixel_shader
    assert len(pal) == len(ramp) + 1
    assert pal.is_transparent(0)
    sw.detach()


@pytest.mark.asyncio
async def test_vertical_ramp_top_is_low_bottom_is_high():
    d = await _make()
    ramp = (0x110000, 0x220000, 0x330000, 0x440000, 0x550000)  # N = 5
    n = len(ramp)
    px = _rect_pixels(10, 5, 5, 7)                  # bbox y: 5 (top) .. 11 (bottom)
    sw = SwarmReveal(px, text_colors=ramp, color_axis="vertical")
    sw.start(d)
    assert all(sw._index_map[(x, 5)] == 1 for x in range(10, 15))   # top -> colors[0]
    assert all(sw._index_map[(x, 11)] == n for x in range(10, 15))  # bottom -> colors[-1]
    sw.detach()


@pytest.mark.asyncio
async def test_horizontal_ramp_left_is_low_right_is_high():
    d = await _make()
    ramp = (0x001100, 0x002200, 0x003300, 0x004400)  # N = 4
    n = len(ramp)
    px = _rect_pixels(10, 5, 5, 7)                  # bbox x: 10 (left) .. 14 (right)
    sw = SwarmReveal(px, text_colors=ramp, color_axis="horizontal")
    sw.start(d)
    assert all(sw._index_map[(10, y)] == 1 for y in range(5, 12))   # left -> colors[0]
    assert all(sw._index_map[(14, y)] == n for y in range(5, 12))   # right -> colors[-1]
    sw.detach()


@pytest.mark.asyncio
async def test_diagonal_ramp_corner_to_corner():
    d = await _make()
    ramp = (0x000011, 0x000022, 0x000033, 0x000044, 0x000055, 0x000066)  # N = 6
    n = len(ramp)
    px = _rect_pixels(10, 5, 5, 7)
    sw = SwarmReveal(px, text_colors=ramp, color_axis="diagonal")
    sw.start(d)
    assert sw._index_map[(10, 5)] == 1     # top-left corner  -> colors[0]
    assert sw._index_map[(14, 11)] == n    # bottom-right corner -> colors[-1]
    sw.detach()


@pytest.mark.asyncio
async def test_gradient_capture_writes_the_precomputed_index():
    # End-to-end: step() must paint each captured pixel with its precomputed ramp
    # index (not the constant 1), and the full ramp must actually appear.
    d = await _make()
    ramp = (0x110000, 0x330000, 0x550000)  # N = 3
    px = _rect_pixels(12, 6, 5, 7)
    sw = SwarmReveal(px, text_colors=ramp, color_axis="vertical", num_birds=18)
    sw.start(d)
    _run(sw)
    assert sw.is_complete
    for cell in px:
        assert sw._text_bmp[cell[0], cell[1]] == sw._index_map[cell]
    painted = {sw._index_map[cell] for cell in px}
    assert painted == {1, 2, 3}            # whole ramp spans the glyph extent
    sw.detach()


@pytest.mark.asyncio
async def test_default_path_unchanged_without_text_colors():
    # Omitting text_colors must leave the original 2-color path intact: no index
    # map, a 2-entry palette, and every capture writes the constant index 1.
    d = await _make()
    px = _rect_pixels(10, 5, 5, 7)
    sw = SwarmReveal(px, num_birds=18)
    sw.start(d)
    assert sw._index_map is None
    assert len(sw._text_tile.pixel_shader) == 2
    _run(sw)
    assert sw.is_complete
    assert {sw._text_bmp[x, y] for (x, y) in px} == {1}
    sw.detach()


@pytest.mark.asyncio
async def test_captured_pixels_only_land_on_targets():
    d = await _make()
    px = pixels_from_text("XY", x=26, y=13)
    target = set(px)
    sw = SwarmReveal(px, num_birds=18)
    sw.start(d)
    # At every step, no lit text pixel may be outside the target set (deliberate
    # capture lights only assigned target pixels).
    for _ in range(400):
        if sw.is_complete:
            break
        sw.step()
        lit = {(x, y) for x in range(64) for y in range(32) if sw._text_bmp[x, y] == 1}
        assert lit <= target
    sw.detach()
