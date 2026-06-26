"""DripReveal assembles its target pixels entering from any edge (default top)."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import asyncio

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.effects.drip_splash import DripReveal

TARGET = {(2, 3), (3, 3), (4, 4), (10, 5), (11, 20), (30, 15), (5, 28)}


def _run(direction):
    """Run a DripReveal to completion; return (final lit pixels, first-frame pixels)."""
    async def go():
        from scrollkit.display.simulator import SimulatorDisplay
        d = SimulatorDisplay(width=64, height=32)
        await d.initialize()
        r = DripReveal(list(TARGET), direction=direction, stagger=1)
        r.start(d)
        first = None
        steps = 0
        while not r.is_complete and steps < 500:
            r.step()
            if first is None:
                first = {(x, y) for x in range(64) for y in range(32) if r._bitmap[x, y]}
            steps += 1
        final = {(x, y) for x in range(64) for y in range(32) if r._bitmap[x, y]}
        r.detach()
        return final, first
    return asyncio.run(go())


@pytest.mark.parametrize("direction", ["top", "bottom", "left", "right"])
def test_drip_assembles_exactly_from_each_edge(direction):
    final, _ = _run(direction)
    assert final == TARGET


def test_drops_first_appear_at_the_named_entry_edge():
    _, first_bottom = _run("bottom")
    assert any(y == 31 for (x, y) in first_bottom)   # enters from the bottom row
    _, first_right = _run("right")
    assert any(x == 63 for (x, y) in first_right)     # enters from the right column


def test_unknown_direction_falls_back_to_top():
    assert DripReveal([(1, 1)], direction="sideways").direction == "top"
