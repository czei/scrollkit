# Copyright (c) 2024-2026 Michael Czeiszperger
"""Tests for scrollkit.effects.image_animators (per-frame image-layer animators).

Synthetic pixels only — a hand-placed silhouette in a gfx.Bitmap; no app assets.
Exercises the start/step/detach contract every animator promises the host:
layers balance after detach, failures raise out of start() without leaking,
pixel-writers settle the image back, and palette pulses restore exactly.
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.simulator import SimulatorDisplay
from scrollkit.effects import image_animators as ia

BASE = [0x000000, 0x336688, 0xAAEEFF, 0xEE4444, 0x88DD55]


async def _make_display():
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    return d


def _scene(gfx):
    """A 24x12 block silhouette, highlight band, red feature, and a green
    "wing" strip standing alone in the sky above (the legal region_shift target:
    the shift rule requires the travel range to hold only the feature + sky)."""
    bmp = gfx.Bitmap(64, 32, len(BASE))
    for y in range(10, 22):
        for x in range(20, 44):
            bmp[x, y] = 1
    for x in range(24, 40):
        bmp[x, 12] = 2
    bmp[30, 16] = 3
    bmp[31, 16] = 3
    for x in range(26, 38):
        bmp[x, 5] = 4                                 # the wing, over open sky
    pal = gfx.Palette(len(BASE))
    for i, c in enumerate(BASE):
        pal[i] = c
    pal.make_transparent(0)
    return bmp, pal


def _attach(d, anim, writable=False):
    gfx = d.gfx
    bmp, pal = _scene(gfx)
    if writable or anim.wants_writable_bitmap:
        bmp = ia.copy_to_writable(gfx, bmp, 64, 32, len(BASE))
    tile = gfx.TileGrid(bmp, pixel_shader=pal)
    d.add_layer(tile)
    anim.start(d, tile, bmp, pal, list(BASE))
    return tile, bmp, pal


ALL_ANIMATORS = [
    lambda: ia.TwinkleAnimator(count=10),
    lambda: ia.MotionAnimator(path="bob", amp=2),
    lambda: ia.MotionAnimator(path="traverse_lr", bob_amp=1),
    lambda: ia.EmitterAnimator(box=(30, 8, 34, 10), vy=-0.5),
    lambda: ia.PalettePulseAnimator(match=(0xEE4444,), tol=8),
    lambda: ia.RegionShiftAnimator(box=(26, 3, 37, 7), amp=1, period=12),
    lambda: ia.RegionShiftAnimator(box=(26, 3, 37, 7), amp=1, wave="ripple"),
    lambda: ia.RegionShiftAnimator(box=(26, 3, 37, 7), amp=2, wave="hinge"),
    lambda: ia.RegionRotateAnimator(box=(26, 3, 37, 7), pivot=(37, 5), amp_deg=12, period=12),
    lambda: ia.OrbiterAnimator(cx=32, cy=16, rx=10, ry=5),
    lambda: ia.BlinkAnimator(box=(29, 15, 32, 17), color=0x336688),
    lambda: ia.SpriteLiftAnimator(boxes=((20, 10, 44, 21),),
                                  exclude_colors=(0x336688,), tol=8),
    lambda: ia.CoverAnimator(box=(28, 14, 34, 18), dy=-2, until=10),
    lambda: ia.VanishAnimator(boxes=((22, 10, 26, 14),), start=5),
    lambda: ia.FrameCycleAnimator(box=(20, 10, 44, 21), nframes=3, amp=1),
]


@pytest.mark.asyncio
@pytest.mark.parametrize("factory", ALL_ANIMATORS)
async def test_lifecycle_and_layer_balance(factory):
    """Every animator: start -> step across its hold -> detach, layers balanced."""
    d = await _make_display()
    layers0 = len(d._layer_group)
    anim = factory()
    tile, bmp, pal = _attach(d, anim)
    for f in range(0, anim.HOLD_FRAMES, 5):
        anim.step(f)
    anim.detach()
    anim.detach()                                     # idempotent
    d.remove_layer(tile)
    assert len(d._layer_group) == layers0


@pytest.mark.asyncio
async def test_region_shift_over_cap_raises_and_settles():
    """Oversized captures refuse (the host's fall-back contract)."""
    d = await _make_display()
    gfx = d.gfx
    bmp = gfx.Bitmap(64, 32, 2)
    for y in range(32):
        for x in range(64):
            bmp[x, y] = 1                             # 2048 lit px >> 320 cap
    pal = gfx.Palette(2)
    pal[1] = 0xFFFFFF
    tile = gfx.TileGrid(bmp, pixel_shader=pal)
    d.add_layer(tile)
    anim = ia.RegionShiftAnimator(box=(0, 0, 63, 31), amp=2)
    with pytest.raises(ValueError):
        anim.start(d, tile, bmp, pal, [0, 0xFFFFFF])
    d.remove_layer(tile)


@pytest.mark.asyncio
async def test_region_shift_detach_settles_pixels():
    """After detach the shifted region sits back at rest, image intact."""
    d = await _make_display()
    anim = ia.RegionShiftAnimator(box=(26, 3, 37, 7), amp=2, period=8)
    tile, bmp, pal = _attach(d, anim)
    before = [(x, y, bmp[x, y]) for y in range(32) for x in range(64)]
    anim.step(2)                                      # mid-swing
    anim.detach()
    after = [(x, y, bmp[x, y]) for y in range(32) for x in range(64)]
    assert before == after
    d.remove_layer(tile)


@pytest.mark.asyncio
async def test_region_rotate_moves_then_settles_exactly():
    """A true rotation TILTS the region mid-swing, then detach restores it exactly."""
    d = await _make_display()
    anim = ia.RegionRotateAnimator(box=(26, 3, 37, 7), pivot=(37, 5),
                                   amp_deg=14, period=8)
    tile, bmp, pal = _attach(d, anim)
    before = [(x, y, bmp[x, y]) for y in range(32) for x in range(64)]
    anim.step(2)                                      # quarter period -> peak tilt
    after_step = [(x, y, bmp[x, y]) for y in range(32) for x in range(64)]
    assert after_step != before                       # something actually rotated
    # hole-free: the rotated frame keeps essentially all the lit pixels (inverse map
    # fills every destination), not a sparse, gappy remnant of a forward map.
    lit0 = sum(1 for _, _, c in before if c)
    lit1 = sum(1 for _, _, c in after_step if c)
    assert lit1 >= lit0 - 2
    anim.detach()
    assert [(x, y, bmp[x, y]) for y in range(32) for x in range(64)] == before
    d.remove_layer(tile)


@pytest.mark.asyncio
async def test_region_rotate_exclude_leaves_body_untouched():
    """A head rotating on a body it's fused to must never hole the body: every pixel
    in the excluded region is identical on every frame (the winking-shoulder fix)."""
    d = await _make_display()
    body = (20, 13, 43, 21)                           # lower block: must stay frozen
    anim = ia.RegionRotateAnimator(box=(20, 4, 44, 16), pivot=(43, 14),
                                   amp_deg=16, period=8, exclude=body)
    tile, bmp, pal = _attach(d, anim)
    rest = {(x, y): bmp[x, y] for y in range(body[1], body[3] + 1)
            for x in range(body[0], body[2] + 1)}
    moved = False
    for f in range(anim.HOLD_FRAMES):
        anim.step(f)
        for (x, y), v in rest.items():
            assert bmp[x, y] == v, "body (%d,%d) changed -> a winking hole" % (x, y)
        if bmp[26, 5] == 0 or bmp[30, 5] == 0:        # a wing cell emptied -> it rotated
            moved = True
    assert moved
    anim.detach()
    d.remove_layer(tile)


@pytest.mark.asyncio
async def test_region_rotate_over_scan_cap_raises():
    """A box whose rotated scan area blows the budget refuses (fall-back contract)."""
    d = await _make_display()
    gfx = d.gfx
    bmp = gfx.Bitmap(64, 32, 2)
    for y in range(32):
        for x in range(64):
            bmp[x, y] = 1
    pal = gfx.Palette(2)
    pal[1] = 0xFFFFFF
    tile = gfx.TileGrid(bmp, pixel_shader=pal)
    d.add_layer(tile)
    anim = ia.RegionRotateAnimator(box=(0, 0, 63, 31), pivot=(0, 0), amp_deg=20)
    with pytest.raises(ValueError):
        anim.start(d, tile, bmp, pal, [0, 0xFFFFFF])
    d.remove_layer(tile)


@pytest.mark.asyncio
async def test_palette_pulse_touches_only_matched_and_restores():
    d = await _make_display()
    anim = ia.PalettePulseAnimator(match=(0xEE4444,), tol=8, lo=0.4, hi=1.5, period=20)
    tile, bmp, pal = _attach(d, anim)

    def rgb(i):
        c = pal.get_rgb888(i)
        return (int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2])

    # quantization reference: what a fresh write of each base color reads back as
    ref = ia.copy_to_writable  # noqa: F841 (documentation only)
    fresh = d.gfx.Palette(len(BASE))
    for i, c in enumerate(BASE):
        fresh[i] = c
    expect = [(int(fresh.get_rgb888(i)[0]) << 16)
              | (int(fresh.get_rgb888(i)[1]) << 8)
              | int(fresh.get_rgb888(i)[2]) for i in range(len(BASE))]

    anim.step(5)                                      # mid-pulse: matched index moved
    assert rgb(3) != expect[3]
    assert rgb(1) == expect[1] and rgb(2) == expect[2]  # unmatched untouched
    anim.detach()
    assert [rgb(i) for i in range(len(BASE))] == expect  # exact restore
    d.remove_layer(tile)


@pytest.mark.asyncio
async def test_motion_recenters_bob_but_not_traverse():
    d = await _make_display()
    bob = ia.MotionAnimator(path="bob", amp=2)
    tile, bmp, pal = _attach(d, bob)
    bob.step(6)
    bob.detach()
    assert tile.x == 0 and tile.y == 0
    d.remove_layer(tile)

    trav = ia.MotionAnimator(path="traverse_lr")
    tile2, bmp2, pal2 = _attach(d, trav)
    trav.step(trav.HOLD_FRAMES - 1)                   # fully exited
    x_exit = tile2.x
    trav.detach()
    assert tile2.x == x_exit                          # no recenter flash
    d.remove_layer(tile2)


@pytest.mark.asyncio
async def test_sprite_lift_scene_fixed_and_inpainted():
    """The lifted subject moves on its own layer; the scene keeps no hole."""
    d = await _make_display()
    anim = ia.SpriteLiftAnimator(boxes=((20, 10, 44, 21),),
                                 exclude_colors=(0x336688,), tol=8)
    tile, bmp, pal = _attach(d, anim)
    # the highlight band (index 2) + red feature (3) were lifted; the base-color
    # block (index 1, excluded) stays; lifted holes must be row-inpainted (non-zero)
    assert bmp[30, 16] != 0 and bmp[24, 12] != 0
    scene_before = [bmp[x, y] for y in range(32) for x in range(64)]
    anim.step(10)
    anim.step(40)
    scene_after = [bmp[x, y] for y in range(32) for x in range(64)]
    assert scene_before == scene_after                # scene NEVER changes per frame
    anim.detach()
    d.remove_layer(tile)


@pytest.mark.asyncio
async def test_frame_cycle_single_layer_and_restore():
    d = await _make_display()
    anim = ia.FrameCycleAnimator(box=(20, 10, 44, 21), nframes=3, amp=1, period=2)
    tile, bmp, pal = _attach(d, anim)
    layers_mid = []
    for f in range(0, 12):
        anim.step(f)
        layers_mid.append(len(d._layer_group))
    assert len(set(layers_mid)) == 1                  # exactly one frame layer, always
    anim.detach()
    assert bmp[30, 16] != 0                           # cloth restored for the host's fade
    d.remove_layer(tile)


@pytest.mark.asyncio
async def test_cel_walk_prebakes_a_nodding_head_and_keeps_steps_cheap():
    """The optional head rig is baked once; walking still only swaps tiles."""
    d = await _make_display()
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    path = os.path.join(root, "demos", "assets", "animators", "ostrich.bmp")
    from scrollkit.display.unified import displayio

    odb = displayio.OnDiskBitmap(path)
    pal = odb.pixel_shader
    pal.make_transparent(0)
    base = [pal[i] for i in range(len(pal))]
    bmp = ia.read_indexed_bmp(d.gfx, path)
    tile = d.gfx.TileGrid(bmp, pixel_shader=pal)
    d.add_layer(tile)
    layers0 = len(d._layer_group)

    anim = ia.CelWalkAnimator(
        period=6, head_box=(39, 0, 54, 10), head_pivot=(39, 10),
        head_amp_deg=7, head_steps=4,
    )
    anim.image_path = path
    anim.start(d, tile, bmp, pal, base)
    assert anim._head_steps == 5                  # odd -> includes the upright pose
    assert len(d._layer_group) == layers0 + 2     # authored body + nodding-head overlay
    assert anim._head_tile[0, 0] == 2             # pose 0, upright head (step 2 of 5)

    anim.step(6)                                  # pose 1, peak nod
    assert anim._tile[0, 0] == 1
    assert anim._head_tile[0, 0] == 9             # pose 1 * 5 + peak-angle step 4
    assert anim._head_tile.x == anim._tile.x
    assert anim._head_tile.y == anim._tile.y

    anim.detach()
    assert len(d._layer_group) == layers0
    d.remove_layer(tile)


@pytest.mark.asyncio
async def test_combo_cleans_up_when_a_later_part_fails():
    """The partial-start leak fix: part 1's overlay must not survive part 2's raise."""
    d = await _make_display()
    gfx = d.gfx
    bmp, pal = _scene(gfx)
    bmp = ia.copy_to_writable(gfx, bmp, 64, 32, len(BASE))
    tile = gfx.TileGrid(bmp, pixel_shader=pal)
    d.add_layer(tile)
    layers0 = len(d._layer_group)
    combo = ia.ComboAnimator([
        ia.TwinkleAnimator(count=5),                       # starts fine, adds overlay
        ia.SpriteLiftAnimator(boxes=((0, 0, 2, 2),)),      # empty capture -> raises
    ])
    with pytest.raises(ValueError):
        combo.start(d, tile, bmp, pal, list(BASE))
    assert len(d._layer_group) == layers0             # twinkle's overlay was detached
    d.remove_layer(tile)


@pytest.mark.asyncio
async def test_combo_aggregates_contract_flags():
    combo = ia.ComboAnimator([ia.MotionAnimator(path="traverse_lr"),
                              ia.RegionShiftAnimator(box=(28, 14, 34, 18), amp=1)])
    assert combo.wants_writable_bitmap is True        # OR of parts
    assert combo.HOLD_FRAMES == max(p.HOLD_FRAMES for p in combo._parts)


@pytest.mark.asyncio
async def test_copy_to_writable_exact_and_writable():
    d = await _make_display()
    gfx = d.gfx
    bmp, pal = _scene(gfx)
    dup = ia.copy_to_writable(gfx, bmp, 64, 32, len(BASE))
    assert all(dup[x, y] == bmp[x, y] for y in range(32) for x in range(64))
    dup[0, 0] = 1                                     # must not raise
    assert dup[0, 0] == 1


def test_feasibility_on_classes_only():
    """CircuitPython crashes importing modules that set attrs on functions."""
    for cls in (ia.TwinkleAnimator, ia.MotionAnimator, ia.EmitterAnimator,
                ia.PalettePulseAnimator, ia.RegionShiftAnimator, ia.OrbiterAnimator,
                ia.BlinkAnimator, ia.SpriteLiftAnimator, ia.CoverAnimator,
                ia.VanishAnimator, ia.FrameCycleAnimator, ia.ComboAnimator):
        assert isinstance(cls.FEASIBILITY, dict)
        assert "hardware_safe" in cls.FEASIBILITY
    assert not hasattr(ia.copy_to_writable, "FEASIBILITY")
    assert not hasattr(ia._shuffle, "FEASIBILITY")
