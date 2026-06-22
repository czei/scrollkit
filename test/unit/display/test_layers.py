"""Layer ownership & z-order (D11): persistent effect layers survive the per-frame
content clear() and always composite above content."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.simulator import SimulatorDisplay


async def _make():
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    return d


def _layer(d, w=4, h=4):
    bm = d.gfx.Bitmap(w, h, 2)
    pal = d.gfx.Palette(2)
    pal[1] = 0xFF0000
    return d.gfx.TileGrid(bm, pixel_shader=pal)


@pytest.mark.asyncio
async def test_layer_survives_clear_and_stays_above_content():
    d = await _make()
    tg = _layer(d)
    d.add_layer(tg)
    for _ in range(5):
        await d.clear()                       # empties content, must NOT touch layers
        await d.draw_text("HI", 0, 0, 0xFFFFFF)
        await d.show()
    assert tg in list(d._layer_group)         # survived 5 clears
    assert len(d._layer_group) == 1
    # main_group order pins z: content below (index 0), layers above (index 1).
    assert d.main_group[0] is d._content_group
    assert d.main_group[1] is d._layer_group


@pytest.mark.asyncio
async def test_layer_stays_above_even_after_label_pool_grows():
    d = await _make()
    tg = _layer(d)
    d.add_layer(tg)
    # Draw several labels (pool grows) across frames; layer must remain on top.
    for n in range(1, 6):
        await d.clear()
        for k in range(n):
            await d.draw_text("L%d" % k, 0, k * 5, 0xFFFFFF)
        await d.show()
    assert d.main_group[-1] is d._layer_group  # layers are last == top
    assert tg in list(d._layer_group)


@pytest.mark.asyncio
async def test_add_and_remove_layer_are_idempotent():
    d = await _make()
    tg = _layer(d)
    d.add_layer(tg)
    d.add_layer(tg)                           # re-add is a no-op
    assert len(d._layer_group) == 1
    d.remove_layer(tg)
    d.remove_layer(tg)                        # removing absent is a no-op
    assert len(d._layer_group) == 0
