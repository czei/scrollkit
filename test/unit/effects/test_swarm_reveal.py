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
