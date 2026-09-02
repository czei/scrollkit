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


# ---------------------------------------------------------------------------
# From hand-authored art
# ---------------------------------------------------------------------------

ART = (
    ".##.",
    "#oo#",
    "#ww#",
    ".##.",
)
ART_CHARS = {"#": 0xB02318, "o": 0xFFB030, "w": 0xFFF1D8}


def test_from_art_lights_exactly_the_mapped_characters():
    async def go():
        d = await _display()
        mark = PixelMark.from_art(ART, ART_CHARS, x=10, y=5).attach(d)
        return _lit(mark), mark.colors

    lit, colors = asyncio.run(go())
    # Eight '#', two 'o', two 'w'; the four '.' are holes.
    assert len(lit) == 12
    assert (10, 5) not in lit, "a dot is background, not a colour"
    assert (11, 5) in lit
    assert set(colors) == set(ART_CHARS.values())


def test_an_unmapped_character_is_a_hole_not_a_guess():
    """A character nobody defined is missing information, and inventing a colour for
    it would put a shape on the panel that the author never drew."""
    async def go():
        d = await _display()
        mark = PixelMark.from_art(("#?#",), {"#": 0xB02318}).attach(d)
        return _lit(mark)

    assert asyncio.run(go()) == {(0, 0), (2, 0)}


def test_the_palette_holds_only_what_the_art_uses():
    mark = PixelMark.from_art(ART, dict(ART_CHARS, z=0x00FF00))
    assert len(mark.colors) == 3, "the unused colour is not in the ramp"


def test_art_plays_through_an_act():
    """The whole path: hand-authored art, on the panel, revealed by a library act."""
    async def go():
        d = await _display()
        mark = PixelMark.from_art(ART, ART_CHARS, x=20, y=10).attach(d)

        async def frame():
            await d.show()
            return True

        ok = await drip_in(mark.context(d, frame=frame))
        return ok, mark._tile.hidden, _lit(mark)

    ok, hidden, lit = asyncio.run(go())
    assert ok is True
    assert hidden is False
    assert len(lit) == 12


@pytest.mark.asyncio
async def test_a_mark_exposes_its_layer_so_an_animator_can_move_it():
    """A mark is a thing that MOVES. The image animators take a TileGrid, and without
    this a host driving a mark along a path had to reach into a private attribute."""
    d = await _display()
    mark = PixelMark.from_art(("##", "##"), {"#": 0xFF8800}, x=3, y=4)
    assert mark.tile is None                      # nothing to move before it is attached
    mark.attach(d)
    assert mark.tile is not None
    mark.tile.x, mark.tile.y = 7, 2               # what an animator does every frame
    assert (mark.tile.x, mark.tile.y) == (7, 2)
    mark.detach()
    assert mark.tile is None


# -- off-panel cells leave the mark entirely ---------------------------------
#
# attach() always dropped an off-panel cell from the BITMAP, but kept it in `slots`,
# so the mark went on describing pixels it never drew. Six of the seven acts survived
# that; `treatment_dwell` did not, because it hands `ctx.slots` straight to a
# panel-sized PalettePartition. A wordmark one column too wide therefore raised
# IndexError on its first dwell -- the exact failure the drop was there to prevent.


@pytest.mark.asyncio
async def test_attach_drops_off_panel_cells_from_the_slots_too():
    d = await _display()
    cells = {(60, 5): 1, (63, 5): 1, (64, 5): 1, (99, 5): 1, (10, 40): 1, (-2, 5): 1}
    mark = PixelMark(cells, colors=RAMP).attach(d)
    assert set(mark.slots) == {(60, 5), (63, 5)}
    assert mark.slots[(60, 5)] == 1, "a mapping stays a mapping, indices intact"


@pytest.mark.asyncio
async def test_a_bare_iterable_of_cells_keeps_its_shape():
    d = await _display()
    mark = PixelMark([(1, 1), (2, 2), (70, 2)]).attach(d)
    assert list(mark.slots) == [(1, 1), (2, 2)]
    assert not hasattr(mark.slots, "items"), "an iterable must not become a mapping"


@pytest.mark.asyncio
async def test_a_wordmark_wider_than_the_panel_still_dwells():
    """The regression: this raised IndexError from inside PalettePartition."""
    from scrollkit.effects.acts import treatment_dwell

    d = await _display()
    mark = PixelMark.from_text(d, "BLUE RIDGE COFFEE", y=12).attach(d)
    assert max(x for (x, _y) in mark.slots) < d.width

    async def frame():
        await d.show()
        return True

    assert await treatment_dwell(mark.context(d, frame=frame)) is True
