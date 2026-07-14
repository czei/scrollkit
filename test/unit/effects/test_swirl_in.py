"""SwirlIn: sprites spiral in and land EXACTLY on their targets."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.simulator import SimulatorDisplay
from scrollkit.display.unified import displayio
from scrollkit.effects.swirl_in import SwirlIn


def _tile(w=7, h=11):
    bmp = displayio.Bitmap(w, h, 2)
    pal = displayio.Palette(2)
    tile = displayio.TileGrid(bmp, pixel_shader=pal)
    tile.hidden = True
    return tile


@pytest.mark.asyncio
async def test_lands_exactly_on_targets():
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    targets = [(2, 10), (12, 10), (22, 10), (48, 10)]
    entries = [(_tile(), x, y, 7, 11) for (x, y) in targets]
    sw = SwirlIn(entries)
    steps = 0
    while not sw.is_complete and steps < 500:
        sw.step()
        steps += 1
    assert sw.is_complete
    expected_total = 34 + (len(entries) - 1) * 6 + 1     # final snap frame
    assert steps == expected_total
    for (tile, tx, ty, _w, _h) in entries:
        assert (tile.x, tile.y) == (tx, ty)
        assert not tile.hidden


def test_stagger_keeps_later_sprites_hidden_at_first():
    entries = [(_tile(), 2, 10, 7, 11), (_tile(), 40, 10, 7, 11)]
    sw = SwirlIn(entries, stagger=6)
    sw.step()                                # frame 0
    assert not entries[0][0].hidden          # first sprite is flying
    assert entries[1][0].hidden              # second not started yet
    for _ in range(6):
        sw.step()
    assert not entries[1][0].hidden          # onset reached


def test_empty_and_feasibility():
    assert SwirlIn(()).is_complete
    assert isinstance(SwirlIn.FEASIBILITY, dict)
    assert SwirlIn.FEASIBILITY["max_pixel_writes_per_frame"] == 0
