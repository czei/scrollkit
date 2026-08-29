"""A mark an act can reveal, without an app to own it.

The failure this exists to prevent is quiet: `drip_in` completes, the overlay detaches,
`ctx.show()` is called, and nothing appears — because there was never anything under the
overlay. Every test here therefore checks LIT PIXELS after the act, not just that it
returned True.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import asyncio

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.effects.acts import drip_in, swarm_build, swarm_unbuild  # noqa: E402
from scrollkit.effects.mark import PixelMark  # noqa: E402

CELLS = {(10, 12): 1, (11, 12): 1, (12, 12): 2, (13, 12): 2,
         (10, 13): 1, (13, 13): 3, (11, 14): 1, (12, 14): 2}
RAMP = (0xB02318, 0xFFB030, 0xFFF1D8)


async def _display():
    from scrollkit.display.simulator import SimulatorDisplay

    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    return d


def _lit(mark):
    """Cells set in the mark's own bitmap — what would be on screen when shown."""
    b = mark._bitmap
    return {(x, y) for x in range(64) for y in range(32) if b[x, y]}


def test_a_mapping_of_cells_becomes_a_palette_indexed_layer():
    async def go():
        d = await _display()
        mark = PixelMark(CELLS, colors=RAMP).attach(d)
        return _lit(mark), mark._tile.hidden

    lit, hidden = asyncio.run(go())
    assert lit == set(CELLS), "every lit cell reached the bitmap"
    assert hidden is True, "attached hidden, so the mark does not flash before its act"


def test_a_bare_iterable_becomes_one_flat_tone():
    """A mark with no palette is still a mark. Most first drafts are one colour."""
    async def go():
        d = await _display()
        mark = PixelMark(set(CELLS), color=0x00FF00).attach(d)
        return _lit(mark)

    assert asyncio.run(go()) == set(CELLS)


def test_index_zero_is_not_lit():
    """0 means "no ink here" in the source art, and the built palette reserves 0 for
    transparency — so a cell carrying 0 must not light, or the mark grows a background."""
    async def go():
        d = await _display()
        cells = dict(CELLS)
        cells[(20, 20)] = 0
        mark = PixelMark(cells, colors=RAMP).attach(d)
        return _lit(mark)

    assert (20, 20) not in asyncio.run(go())


def test_cells_off_the_panel_are_dropped_rather_than_raising():
    async def go():
        d = await _display()
        cells = dict(CELLS)
        cells[(999, 999)] = 1
        cells[(-4, 3)] = 1
        mark = PixelMark(cells, colors=RAMP).attach(d)
        return _lit(mark)

    assert asyncio.run(go()) == set(CELLS)


def test_from_text_builds_a_wordmark_with_no_art_at_all():
    """The reason a deck of acts can be judged before anything is drawn."""
    async def go():
        d = await _display()
        mark = PixelMark.from_text(d, "HELLO", x=2, y=10)
        mark.attach(d)
        return _lit(mark)

    lit = asyncio.run(go())
    assert len(lit) > 20, "the text lit a plausible number of cells"


@pytest.mark.parametrize("act,kw,visible_after", [
    (drip_in, {"direction": "top"}, True),
    (swarm_build, {"num_birds": 12}, True),
    (swarm_unbuild, {"num_birds": 12}, False),
])
def test_an_act_hands_the_mark_back_at_the_end(act, kw, visible_after):
    """The whole point: after a build the mark is ON SCREEN, not merely 'ok'.

    Before PixelMark this passed its return value and left a black panel, because
    ctx.show() had nothing to show.
    """
    async def go():
        d = await _display()
        mark = PixelMark(CELLS, colors=RAMP).attach(d)

        async def frame():
            await d.show()
            return True

        ok = await act(mark.context(d, frame=frame), **kw)
        return ok, mark._tile.hidden, _lit(mark)

    ok, hidden, lit = asyncio.run(go())
    assert ok is True
    assert hidden is not visible_after, (
        "a build ends with the mark shown; an exit ends with it gone"
    )
    assert lit == set(CELLS), "and the mark itself is unchanged by the act"


def test_detach_is_safe_twice_and_before_attach():
    mark = PixelMark(CELLS, colors=RAMP)
    mark.detach()

    async def go():
        d = await _display()
        m = PixelMark(CELLS, colors=RAMP).attach(d)
        m.detach()
        m.detach()

    asyncio.run(go())
