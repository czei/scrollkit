"""Palette treatments: every class runs to completion painting palette
only, ends at the theme's flat color, and blinks on EXACTLY the frames
the source choreography did (the timing-fidelity lock: these totals and
blink indices are the DarkOwl app's originals, frame for frame)."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.simulator import SimulatorDisplay
from scrollkit.display.unified import displayio
from scrollkit.effects.palette_partition import (
    PalettePartition,
    bfs_paths,
    map_diagonal,
    map_exposure,
    map_route,
    map_topology,
)
from scrollkit.effects.palette_treatments import (
    TREATMENT_CLASSES,
    AnchorWake,
    CipherRain,
    EclipseCross,
    GradientDwell,
    HaloPulse,
    HeatmapDrift,
    InkShimmer,
    PacketTrace,
    RimLight,
    RouteCircuit,
    SonarSweep,
    StrokeAnatomy,
    VelvetSweep,
    treatments_for,
)
from scrollkit.effects.reveal_splash import pixels_from_text
from scrollkit.simulator.core.color_utils import rgb888_to_rgb565

THEME = (0x70140E, 0x8F1B12, 0xB02318, 0xC93A1E, 0xE65A28)
FLAT = THEME[2]
FLAT565 = rgb888_to_rgb565((FLAT >> 16) & 0xFF, (FLAT >> 8) & 0xFF,
                           FLAT & 0xFF)


def _slots():
    return {p: 1 for p in pixels_from_text("OWL", x=10, y=12)}


def _fx(n=10, builder=map_diagonal):
    group_map, groups = builder(_slots(), n) if builder is map_diagonal \
        else builder(_slots())
    return PalettePartition(displayio, _slots(), group_map, groups,
                            identity_colors=(0xFFB030,))


def _route_fx():
    body = sorted(_slots())
    third = len(body) // 3
    paths = [set(body[:third]), set(body[third:2 * third])]
    terminus = set(body[2 * third:])
    group_map, n = map_route(_slots(), paths, terminus, sections=3)
    fx = PalettePartition(displayio, _slots(), group_map, n)
    return fx, paths


def _drive(t, max_steps=1000):
    """Step to completion; return (total steps, 0-based blink indices)."""
    blinks = []
    steps = 0
    while not t.is_complete and steps < max_steps:
        t.step()
        if t.is_complete:
            break
        if t.blink_now:
            blinks.append(steps)
        steps += 1
    return steps, blinks


def _groups(fx):
    base = fx._group_base
    return [fx.palette[base + i] for i in range(fx.n_groups)]


# (class factory, expected total steps, expected blink indices) — the
# originals' frame math with n_groups=10 (5 for the fixed partitions).
CASES = [
    (lambda fx: VelvetSweep(fx, THEME), 96, [48]),
    (lambda fx: AnchorWake(fx, THEME), 87, [78]),
    (lambda fx: HaloPulse(fx, THEME), 113, [72]),
    (lambda fx: SonarSweep(fx, THEME), 78, [39]),
    (lambda fx: CipherRain(fx, THEME), 156, [78]),
    (lambda fx: InkShimmer(fx, THEME), 128, [60]),
    (lambda fx: HeatmapDrift(fx, THEME), 136, [68]),
    (lambda fx: EclipseCross(fx, THEME), 93, [45]),
    (lambda fx: GradientDwell(fx, THEME, 0x70140E, 0x8F1B12), 57, [32]),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("make,total,blinks", CASES)
async def test_timing_fidelity_and_flat_ending(make, total, blinks):
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    t = make(_fx())
    steps, seen = _drive(t)
    assert steps == total
    assert seen == blinks
    assert all(c == FLAT565 for c in _groups(t.fx))


@pytest.mark.asyncio
async def test_five_group_treatments():
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    rim = RimLight(_fx(builder=map_exposure), THEME)
    steps, seen = _drive(rim)
    assert steps == 113 and seen == [56]
    assert all(c == FLAT565 for c in _groups(rim.fx))

    anatomy = StrokeAnatomy(_fx(builder=map_topology), THEME)
    steps, seen = _drive(anatomy)
    assert steps == 85 and seen == [50]
    assert all(c == FLAT565 for c in _groups(anatomy.fx))


@pytest.mark.asyncio
async def test_route_circuit():
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    fx, _paths = _route_fx()
    n = fx.n_groups                       # 7 (2 paths x 3 sections + terminus)
    routes = (tuple(range(0, 3)), tuple(range(5, 6)))
    t = RouteCircuit(fx, THEME, routes)
    # steps = fade 8 + 2 passes x (2*(max_len+2) + 8) + blink 1 + fade 8
    expected = 8 + 2 * (2 * (3 + 2) + 8) + 1 + 8
    steps, seen = _drive(t)
    assert steps == expected and seen == [expected - 9]
    assert all(c == FLAT565 for c in _groups(fx))
    assert n == 7


@pytest.mark.asyncio
async def test_packet_trace_layers_and_paths():
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    fx, path_sets = _route_fx()
    paths = bfs_paths(path_sets)
    runs = (((0,), 0), ((1,), -2))
    t = PacketTrace(fx, THEME, paths, runs)
    layers_before = len(d._layer_group)
    t.start(d)
    assert len(d._layer_group) == layers_before + len(runs)
    all_path_pixels = set(paths[0]) | set(paths[1])
    while not t.is_complete:
        t.step()
        for tile in t._tiles:
            if not tile.hidden:
                assert (tile.x, tile.y) in all_path_pixels
    assert all(c == FLAT565 for c in _groups(fx))
    t.detach()
    assert len(d._layer_group) == layers_before


def test_registry_and_selector():
    assert len(TREATMENT_CLASSES) == 13
    for cls in TREATMENT_CLASSES:
        assert isinstance(cls.FEASIBILITY, dict)
        assert isinstance(cls.PARTITION, str)
    assert VelvetSweep in treatments_for("diagonal")
    assert RimLight in treatments_for("exposure")
    assert treatments_for("nope") == ()
