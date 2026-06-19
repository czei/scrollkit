"""SimulatorDisplay must reuse Labels like the hardware path, so the feasibility
model only charges a text rebuild when .text actually changes.

Before: draw_text() created a new Label every call, so the model charged the
(expensive) glyph-bitmap rebuild every frame — even for scrolling, where the text
is constant. That made the estimate pessimistic and fired a bogus "cache your
Label" warning at apps that were already fine. Now the simulator pools and reuses
Label objects, matching UnifiedDisplay/hardware.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # headless pygame

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.simulator import SimulatorDisplay
from scrollkit.simulator.core.performance_manager import set_active


@pytest.fixture(autouse=True)
def _reset_active_manager():
    set_active(None)
    yield
    set_active(None)


@pytest.mark.asyncio
async def test_constant_text_reuses_one_label():
    d = SimulatorDisplay(64, 32)
    await d.initialize()
    for x in range(40, 0, -1):                 # scroll: same text, moving x
        await d.clear()
        await d.draw_text("HELLO", x, 12, 0xFFFFFF)
        await d.show()
    assert len(d._label_pool) == 1


@pytest.mark.asyncio
async def test_constant_text_rebuilds_once_changing_rebuilds_every_frame():
    # Constant text -> the glyph bitmap is built once, then reused.
    d = SimulatorDisplay(64, 32, hardware_timing=True)
    await d.initialize()
    for x in range(40, 25, -1):
        await d.clear()
        await d.draw_text("HELLO", x, 12, 0xFFFFFF)
        await d.show()
    const_rebuild = d.feasibility_report().breakdown_ms["bitmap_rebuild"]

    # Text that changes every frame must cost far more (rebuild each frame).
    d2 = SimulatorDisplay(64, 32, hardware_timing=True)
    await d2.initialize()
    for i in range(15):
        await d2.clear()
        await d2.draw_text("VALUE %d" % i, 0, 12, 0xFFFFFF)
        await d2.show()
    changing_rebuild = d2.feasibility_report().breakdown_ms["bitmap_rebuild"]

    assert changing_rebuild > 3 * const_rebuild
