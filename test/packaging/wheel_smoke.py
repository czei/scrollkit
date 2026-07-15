"""Run from outside the checkout to prove a built wheel is self-contained."""

import asyncio
import os
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import scrollkit
from scrollkit.display.simulator import SimulatorDisplay
from scrollkit.simulator.core.hardware_profile import baseline_path
from scrollkit.simulator.terminalio import FONT


async def main():
    package_root = Path(scrollkit.__file__).resolve().parent
    assert "site-packages" in str(package_root), package_root
    assert Path(baseline_path()).is_file()
    assert FONT is not None

    display = SimulatorDisplay(width=64, height=32)
    await display.initialize()
    await display.clear()
    await display.fill(0x002040)
    await display.draw_text("WHEEL OK", 4, 12, 0xFFFFFF)
    await display.show()
    pixels = display.matrix.pixel_buffer.get_buffer()
    assert int(pixels.sum()) > 0


asyncio.run(main())
