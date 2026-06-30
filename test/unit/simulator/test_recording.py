"""Test the simulator's GIF recording — the sibling of screenshot()."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # headless pygame

import pytest

pygame = pytest.importorskip("pygame")
Image = pytest.importorskip("PIL.Image")

from scrollkit.display.simulator import SimulatorDisplay


@pytest.mark.asyncio
async def test_save_gif_writes_a_multiframe_animation(tmp_path):
    display = SimulatorDisplay(width=64, height=32)
    await display.initialize()

    display.start_recording()
    assert display.is_recording
    # Move the text so successive captured frames actually differ.
    for i in range(6):
        await display.clear()
        await display.draw_text("HI", 5 + i * 5, 12, 0x00AAFF)
        await display.show()

    out = str(tmp_path / "demo.gif")
    result = display.save_gif(out, frame_step=1)

    assert result == out
    assert os.path.exists(out) and os.path.getsize(out) > 0
    assert not display.is_recording          # save stops/clears the recording
    with Image.open(out) as im:
        assert getattr(im, "n_frames", 1) > 1  # it's an animation, not one frame


@pytest.mark.asyncio
async def test_save_gif_with_nothing_recorded_returns_none(tmp_path):
    display = SimulatorDisplay(width=64, height=32)
    await display.initialize()
    # No start_recording(): there is nothing to save, and that's not an error.
    assert display.save_gif(str(tmp_path / "empty.gif")) is None
