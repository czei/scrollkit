"""fill() and set_pixel() must actually render (they survive show()'s refresh)."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # headless pygame

from collections import Counter

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.simulator import SimulatorDisplay


def _dominant_color(display):
    buf = display.matrix.pixel_buffer.get_buffer()
    counts = Counter()
    for y in range(display.height):
        for x in range(display.width):
            px = tuple(int(v) for v in buf[y, x])
            if px != (0, 0, 0):
                counts[px] += 1
    return counts.most_common(1)[0][0] if counts else None


@pytest.mark.asyncio
async def test_fill_renders_the_actual_color():
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    await d.clear()
    await d.fill(0xFF0000)
    await d.show()
    # Was a bug: fill() wrote to the pixel buffer, which refresh() then wiped,
    # leaving the grey "off" LED color. Now it renders as a background.
    assert _dominant_color(d) == (255, 0, 0)


@pytest.mark.asyncio
async def test_fill_is_a_background_behind_text():
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    await d.clear()
    await d.fill(0x0000FF)
    await d.draw_text("HI", 20, 12, 0xFFFFFF)
    await d.show()
    buf = d.matrix.pixel_buffer.get_buffer()
    blue = sum(1 for y in range(32) for x in range(64)
               if int(buf[y, x][2]) > 150 and int(buf[y, x][0]) < 80)
    white = sum(1 for y in range(32) for x in range(64)
                if all(int(v) > 150 for v in buf[y, x]))
    assert blue > 100, "fill background not rendered"
    assert white > 0, "text not rendered on top of the fill"


@pytest.mark.asyncio
async def test_set_pixel_renders_on_top():
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    await d.clear()
    await d.set_pixel(10, 10, 0x00FF00)
    await d.show()
    buf = d.matrix.pixel_buffer.get_buffer()
    assert tuple(int(v) for v in buf[10, 10]) == (0, 255, 0)
