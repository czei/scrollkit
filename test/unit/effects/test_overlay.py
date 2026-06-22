"""OverlayMask: allocate once, transparent index 0, bounded dirty-span writes."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.simulator import SimulatorDisplay
from scrollkit.effects.overlay import OverlayMask


async def _make():
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    return d


@pytest.mark.asyncio
async def test_allocates_once_and_reuses_the_same_objects():
    d = await _make()
    m = OverlayMask(d)
    bm, pal, tg = m.bitmap, m.palette, m.tilegrid
    for i in range(20):
        await m.fill_rect(i % 8, 0, 3, 3, 1)
        await m.clear()
    # No reallocation across many mutations.
    assert m.bitmap is bm and m.palette is pal and m.tilegrid is tg
    assert len(d._layer_group) == 1            # exactly one layer added


@pytest.mark.asyncio
async def test_index_zero_is_transparent():
    d = await _make()
    m = OverlayMask(d)
    assert m.palette.is_transparent(0)


@pytest.mark.asyncio
async def test_cover_and_reveal_only_touch_their_region():
    d = await _make()
    m = OverlayMask(d)
    await m.fill_rect(3, 3, 2, 2, 1)           # cover [3,5) x [3,5)
    assert m.bitmap[3, 3] == 1 and m.bitmap[4, 4] == 1
    assert m.bitmap[2, 3] == 0 and m.bitmap[5, 3] == 0 and m.bitmap[3, 5] == 0
    await m.clear_rect(3, 3, 2, 2)             # reveal it again
    assert m.bitmap[3, 3] == 0 and m.bitmap[4, 4] == 0


@pytest.mark.asyncio
async def test_clear_resets_whole_mask_and_detach_removes_layer():
    d = await _make()
    m = OverlayMask(d)
    await m.fill_rect(0, 0, 10, 10, 1)
    await m.clear()
    assert m.bitmap[0, 0] == 0 and m.bitmap[9, 9] == 0
    m.detach()
    assert len(d._layer_group) == 0
