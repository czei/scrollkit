# Copyright (c) 2024-2026 Michael Czeiszperger
"""Pins ``demos/medium/tilt_drip.py`` — the tilt-driven collapse demo.

The demo is the only place the three new pieces meet: the simulator's virtual
accelerometer, ``TiltSensor``, and ``GravityDripAnimator``. It is also the thing
a reader will copy, so it has to survive the strict feasibility gate — the same
~20 fps device budget the panel enforces — rather than merely looking right on a
desktop that is roughly 100x faster than the board.
"""
import asyncio
import importlib.util
import os

import pytest

pytest.importorskip("pygame")

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

_DEMO_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                          "demos", "medium", "tilt_drip.py")


def _load():
    spec = importlib.util.spec_from_file_location("tilt_drip_demo", _DEMO_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DEMO = _load()


async def _app_with_display(strict=False):
    from scrollkit.display.simulator import SimulatorDisplay
    from scrollkit.sensors.tilt import TiltSensor

    app = DEMO.TiltDripDemo()
    display = SimulatorDisplay(width=64, height=32, strict=strict)
    await display.initialize()
    app.display = display
    app.tilt = TiltSensor(display, min_interval=0.0)
    app.running = True
    return app, display


@pytest.mark.asyncio
async def test_the_demo_image_fits_the_animator_budget():
    """The chosen art must be under the 400-lit-pixel cap, or the demo never drips."""
    from scrollkit.display.simulator import SimulatorDisplay
    from scrollkit.effects.image_animators import GravityDripAnimator, read_indexed_bmp

    display = SimulatorDisplay(width=64, height=32)
    await display.initialize()
    path = os.path.join(os.path.dirname(_DEMO_PATH), "..", "assets", "animators",
                        DEMO._IMAGE)
    bitmap = read_indexed_bmp(display.gfx, path)
    lit = sum(1 for y in range(bitmap.height) for x in range(bitmap.width)
              if bitmap[x, y])
    cap = GravityDripAnimator()._max_pixels
    assert 0 < lit <= cap, "%s has %d lit px — over the animator's %d budget" % (
        DEMO._IMAGE, lit, cap)


@pytest.mark.asyncio
async def test_scene_drips_when_the_box_is_turned_and_resets_when_stood_up():
    """The full state machine, driven by the virtual accelerometer."""
    app, display = await _app_with_display()

    async def turn_it():
        await asyncio.sleep(0.3)
        display.set_virtual_tilt(angle=90)      # stand it on its right end
        await asyncio.sleep(1.5)
        display.set_virtual_tilt(angle=0)       # back upright -> scene resets
        await asyncio.sleep(1.0)
        app.running = False

    driver = asyncio.create_task(turn_it())
    result = await app._scene()
    await driver
    assert result is True                       # returned by the reset path


@pytest.mark.asyncio
async def test_a_flat_panel_reports_no_edge():
    """Lying face up there is no "down" — the demo must not pick one at random."""
    app, display = await _app_with_display()
    display.set_virtual_tilt(flat=True)
    assert app._down_edge() is None


@pytest.mark.asyncio
async def test_down_edge_tracks_the_virtual_accelerometer():
    app, display = await _app_with_display()
    for angle, edge in ((0, "bottom"), (90, "right"), (180, "top"), (270, "left")):
        display.set_virtual_tilt(angle=angle, flat=False)
        app.tilt.read(force=True)
        assert app._down_edge() == edge


@pytest.mark.asyncio
async def test_drip_holds_the_20fps_device_budget_under_the_strict_gate():
    """strict=True raises FeasibilityError if a frame busts the modeled budget."""
    app, display = await _app_with_display(strict=True)
    display.set_virtual_tilt(angle=90)          # trigger the drip immediately

    async def stop_soon():
        await asyncio.sleep(2.0)
        app.running = False

    driver = asyncio.create_task(stop_soon())
    await app._scene()                          # FeasibilityError would propagate
    await driver
