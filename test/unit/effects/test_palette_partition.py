"""PalettePartition: partition builders cover every body pixel and the
layer's palette layout keeps identity slots out of reach of paint()."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.simulator import SimulatorDisplay
from scrollkit.display.unified import displayio
from scrollkit.effects.palette_partition import (
    PalettePartition,
    bfs_paths,
    map_anchor_distance,
    map_angle,
    map_checker,
    map_diagonal,
    map_exposure,
    map_radial,
    map_rain,
    map_regions,
    map_route,
    map_topology,
)
from scrollkit.effects.reveal_splash import pixels_from_text
from scrollkit.simulator.core.color_utils import rgb888_to_rgb565


def _p565(c):
    """The sim Palette stores RGB565; compare through the same conversion."""
    return rgb888_to_rgb565((c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF)


def _slots():
    """A synthetic mark: text body pixels (slot 1) + two identity pixels."""
    slots = {p: 1 for p in pixels_from_text("OWL", x=10, y=12)}
    body = sorted(slots)
    slots[body[0]] = 2                  # identity pixel (e.g. an eye)
    slots[body[1]] = 3
    return slots


def _body(slots):
    return {p for p, s in slots.items() if s == 1}


@pytest.mark.parametrize("build", [
    lambda s: map_diagonal(s, 10),
    lambda s: map_anchor_distance(s, 32, 10),
    lambda s: map_radial(s, 32, 15, 10),
    lambda s: map_angle(s, 32, 15, 14),
    lambda s: map_rain(s, 10),
    lambda s: map_checker(s, 4),
    lambda s: map_checker(s, 2),
    lambda s: map_exposure(s),
    lambda s: map_regions(s, 10),
    lambda s: map_topology(s),
])
def test_builders_cover_every_body_pixel_with_groups_in_range(build):
    slots = _slots()
    group_map, n = build(slots)
    assert set(group_map) == _body(slots)          # exactly the body pixels
    assert all(0 <= g < n for g in group_map.values())


def test_route_terminus_is_the_last_group():
    slots = _slots()
    body = sorted(_body(slots))
    third = len(body) // 3
    paths = [set(body[:third]), set(body[third:2 * third])]
    terminus = set(body[2 * third:])
    group_map, n = map_route(slots, paths, terminus, sections=3)
    assert n == 2 * 3 + 1
    assert all(group_map[p] == n - 1 for p in terminus)
    assert all(group_map[p] < n - 1 for p in paths[0] | paths[1])


def test_bfs_paths_are_depth_ordered_and_complete():
    strokes = [{(x, 5) for x in range(10, 20)}]        # one horizontal run
    (path,) = bfs_paths(strokes)
    assert set(path) == strokes[0]
    assert path[0] == (10, 5)                          # top-left seed first
    assert path[-1] == (19, 5)


@pytest.mark.asyncio
async def test_palette_layout_and_identity_isolation():
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    slots = _slots()
    group_map, n = map_diagonal(slots, 10)
    fx = PalettePartition(displayio, slots, group_map, n,
                          identity_colors=(0xFFB030, 0xFFF1D8))
    assert fx.n_groups == n
    amber, white = _p565(0xFFB030), _p565(0xFFF1D8)
    assert fx.palette[1] == amber and fx.palette[2] == white
    fx.paint([0x111111] * n)                           # groups only
    assert fx.palette[1] == amber and fx.palette[2] == white
    assert fx.palette[3] == _p565(0x111111)
    fx.fill(0x222222)
    assert fx.palette[1] == amber                      # identity untouched
    assert all(fx.palette[3 + i] == _p565(0x222222) for i in range(n))
    fx.set_identity(0x101010, 0x202020)
    assert fx.palette[1] == _p565(0x101010)
    assert fx.palette[2] == _p565(0x202020)
    assert fx.tile.hidden                              # starts hidden


def test_feasibility_on_class():
    assert isinstance(PalettePartition.FEASIBILITY, dict)
    assert PalettePartition.FEASIBILITY["max_pixel_writes_per_frame"] == 0
