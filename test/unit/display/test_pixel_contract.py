"""One per-frame surface: set_pixel/fill on BOTH display classes.

Regression contract for the post-0.8.2 consolidation. Historically
UnifiedDisplay.set_pixel probed the raw matrix object — an API that does not
exist on the hardware Matrix wrapper (every call printed an error) — and on
desktop its writes were wiped by show()'s displayio re-render; only
SimulatorDisplay had a private overlay fix. So the particle system rendered on
SimulatorDisplay ONLY. Now both classes share GraphicsMixin's implementation
(a 1x1 fill_rect into the persistent paint-canvas layer), so pixels are part
of the displayio tree and survive refresh identically on both platforms.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # headless pygame

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.simulator import SimulatorDisplay
from scrollkit.display.unified import UnifiedDisplay
from scrollkit.dev.metrics import buffer_from_display, bright_pixels, coverage, lit_pixels

DISPLAY_CLASSES = [UnifiedDisplay, SimulatorDisplay]


async def _make(cls):
    d = cls(width=64, height=32)
    await d.initialize()
    return d


@pytest.mark.asyncio
@pytest.mark.parametrize("cls", DISPLAY_CLASSES)
async def test_set_pixel_survives_show(cls):
    d = await _make(cls)
    await d.clear()
    await d.set_pixel(5, 7, 0xFF0000)
    assert await d.show() is True

    buf = buffer_from_display(d)
    # Red-dominant and clearly lit (RGB565 round-trip may shave low bits).
    assert int(buf[7, 5].sum()) > 100
    assert buf[7, 5, 0] > buf[7, 5, 2]
    # And ONLY that pixel is lit.
    assert lit_pixels(buf) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("cls", DISPLAY_CLASSES)
async def test_set_pixel_is_immediate_mode(cls):
    """clear() wipes pixels from the previous frame — no ghost trails."""
    d = await _make(cls)
    await d.clear()
    await d.set_pixel(10, 10, 0x00FF00)
    await d.show()
    assert lit_pixels(buffer_from_display(d)) == 1

    await d.clear()
    await d.show()
    assert lit_pixels(buffer_from_display(d)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("cls", DISPLAY_CLASSES)
async def test_fill_is_a_background_below_text(cls):
    d = await _make(cls)
    await d.clear()
    await d.fill(0x000080)
    await d.draw_text("HI", x=2, y=12, color=0xFFFFFF)
    await d.show()

    buf = buffer_from_display(d)
    assert coverage(buf) > 0.95            # background covers the panel
    assert bright_pixels(buf) > 5          # white text renders ABOVE it
    # fill is immediate-mode too: gone after the next clear().
    await d.clear()
    await d.show()
    assert lit_pixels(buffer_from_display(d)) == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("cls", DISPLAY_CLASSES)
async def test_fill_allocates_only_once(cls):
    """The background tile is cached — palette mutation, not per-call builds."""
    d = await _make(cls)
    await d.clear()
    await d.fill(0x123456)
    tile_first = d._bg_tile
    await d.clear()
    await d.fill(0x654321)
    assert d._bg_tile is tile_first


@pytest.mark.asyncio
@pytest.mark.parametrize("cls", DISPLAY_CLASSES)
async def test_particles_render_through_the_shared_surface(cls):
    """The particle system's only display primitive is set_pixel — it must
    produce visible pixels on BOTH display classes (it used to work only on
    SimulatorDisplay)."""
    from scrollkit.effects.particles import ParticleEngine, Sparkle

    d = await _make(cls)
    engine = ParticleEngine(max_particles=8)
    for i in range(6):
        p = Sparkle(x=6 + i * 6, y=10 + (i % 3), lifetime=10.0)
        engine.add_particle(p)          # stamps spawn_time = now
        p.spawn_time -= 3.0             # backdate: mid-life => bright

    await d.clear()
    await engine.update(d)   # updates + renders via display.set_pixel
    await d.show()

    assert lit_pixels(buffer_from_display(d)) >= 4


@pytest.mark.asyncio
async def test_recording_available_on_unified_display(tmp_path):
    """Recording moved up to UnifiedDisplay (SimulatorDisplay inherits it)."""
    pytest.importorskip("PIL")
    d = await _make(UnifiedDisplay)
    assert d.start_recording() is d
    assert d.is_recording
    for i in range(3):
        await d.clear()
        await d.fill(0x102030 + i * 0x101010)
        await d.show()
    out = d.save_gif(str(tmp_path / "unified.gif"))
    assert out is not None
    assert os.path.getsize(out) > 0
    assert not d.is_recording


@pytest.mark.asyncio
async def test_screenshot_available_on_unified_display(tmp_path):
    d = await _make(UnifiedDisplay)
    await d.clear()
    await d.fill(0x800000)
    await d.show()
    path = d.screenshot(str(tmp_path / "unified.png"))
    assert path is not None
    assert os.path.getsize(path) > 0


@pytest.mark.asyncio
async def test_hardware_timing_flag_on_unified_display():
    """The feasibility flags are first-class on UnifiedDisplay now (they used
    to exist only on SimulatorDisplay, forcing every demo to bypass the
    auto-detecting entry point)."""
    d = UnifiedDisplay(width=64, height=32, hardware_timing=True)
    await d.initialize()
    assert d._perf is not None              # timing model is running
    report = d.feasibility_report()
    assert report.confidence != "DISABLED"
