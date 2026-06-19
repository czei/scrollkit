"""Test the simulator's built-in screenshot() helper."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # headless pygame

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.simulator import SimulatorDisplay


@pytest.mark.asyncio
async def test_screenshot_writes_an_image(tmp_path):
    display = SimulatorDisplay(width=64, height=32)
    await display.initialize()
    await display.clear()
    await display.draw_text("HI", 5, 12, 0xFFFFFF)
    await display.show()

    out = str(tmp_path / "frame.png")
    result = display.screenshot(out)

    assert result == out
    assert os.path.exists(out)
    assert os.path.getsize(out) > 0
    # It's a real image of the matrix surface (702x350 for a 64x32 panel).
    assert pygame.image.load(out).get_size() == display.matrix.get_surface().get_size()
