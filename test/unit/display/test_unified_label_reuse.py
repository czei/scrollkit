"""UnifiedDisplay must reuse Labels, not allocate (and leak) one per frame.

Regression test for a real bug: draw_text() cached Labels keyed by
``f"{text}_{x}_{y}"``. Scrolling changes x every frame, so the cache never hit —
a new Label + Group was allocated and appended to main_group *every frame*,
without removal. On the RAM-tiny, slow MatrixPortal S3 that meant growing
allocation and an ever-larger group to composite each refresh: progressive
slowdown and eventual out-of-memory. draw_text() now pulls from a per-frame
Label pool and mutates in place.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # headless pygame

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.unified import UnifiedDisplay
from scrollkit.display.content import ScrollingText


async def _make():
    d = UnifiedDisplay(64, 32)
    await d.initialize()
    return d


@pytest.mark.asyncio
async def test_scrolling_reuses_one_label_no_per_frame_alloc():
    d = await _make()
    content = ScrollingText("SCROLL TEST", y=12, color=0xFFFFFF)
    await content.start()
    first = None
    for _ in range(60):
        await d.clear()
        await content.render(d)
        await d.show()
        if first is None:
            first = d._label_pool[0]
    # One label, reused — not 60.
    assert len(d._label_pool) == 1
    assert len(d.main_group) == 1
    assert d._label_pool[0] is first


@pytest.mark.asyncio
async def test_changing_text_every_frame_stays_bounded():
    d = await _make()
    for i in range(60):
        await d.clear()
        await d.draw_text("VALUE %d" % i, 0, 12, 0xFFFFFF)  # distinct text each frame
        await d.show()
    # Slot reuse bounds it even when the text changes — no growth.
    assert len(d._label_pool) == 1
    assert len(d.main_group) == 1


@pytest.mark.asyncio
async def test_multi_text_frame_then_fewer_hides_leftovers():
    d = await _make()
    # Frame A draws three fields...
    await d.clear()
    for k in range(3):
        await d.draw_text("A%d" % k, 0, k * 10, 0xFFFFFF)
    await d.show()
    assert len(d._label_pool) == 3
    # ...frame B draws only one; the other two must be hidden, not left showing.
    await d.clear()
    await d.draw_text("B", 0, 0, 0xFFFFFF)
    await d.show()
    assert len(d._label_pool) == 3  # pool retained, not regrown
    visible = [c for c in d.main_group if not getattr(c, "hidden", False)]
    assert len(visible) == 1


@pytest.mark.asyncio
async def test_default_bit_depth_is_4():
    d = UnifiedDisplay(64, 32)
    assert d._bit_depth == 4
    d6 = UnifiedDisplay(64, 32, bit_depth=6)
    assert d6._bit_depth == 6
