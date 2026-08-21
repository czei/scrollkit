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
    # One label, reused — not 60. Labels live in the content sub-group (D11).
    assert len(d._label_pool) == 1
    assert len(d._content_group) == 1
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
    assert len(d._content_group) == 1


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
    visible = [c for c in d._content_group if not getattr(c, "hidden", False)]
    assert len(visible) == 1


@pytest.mark.asyncio
async def test_default_bit_depth_is_4():
    d = UnifiedDisplay(64, 32)
    assert d._bit_depth == 4
    d6 = UnifiedDisplay(64, 32, bit_depth=6)
    assert d6._bit_depth == 6


def test_dimmed_label_colour_is_not_rewritten_each_frame(monkeypatch):
    """The riskiest line in the dimmer, pinned.

    draw_text dims BEFORE the `if label.color != color` reuse guard. Dim AFTER
    it and the stored (dimmed) value never equals the incoming (undimmed) one,
    so the guard misses every frame and rewrites the label -- and a colour
    change rebuilds the glyph bitmap, the dominant per-frame cost on hardware.
    Invisible on desktop, a frame-rate collapse on the panel.

    So this counts ASSIGNMENTS, not values: comparing the value passes either
    way, which is what makes this failure mode so easy to ship.
    """
    import asyncio
    from scrollkit.display.unified import UnifiedDisplay

    class _CountingLabel:
        """Wraps a pooled Label and counts writes to .color."""

        def __init__(self, inner):
            object.__setattr__(self, "_inner", inner)
            object.__setattr__(self, "color_writes", 0)

        def __getattr__(self, name):
            return getattr(object.__getattribute__(self, "_inner"), name)

        def __setattr__(self, name, value):
            if name == "color":
                object.__setattr__(self, "color_writes",
                                   object.__getattribute__(self, "color_writes") + 1)
            setattr(object.__getattribute__(self, "_inner"), name, value)

    async def _run():
        d = UnifiedDisplay(width=64, height=32)
        await d.initialize()
        d.set_color_scale(0.4)

        await d.clear()
        await d.draw_text("WAIT", 0, 20, 0xFFFFFF)      # frame 1: creates the label
        assert d._label_pool[0].color != 0xFFFFFF, "colour should be dimmed"

        spy = _CountingLabel(d._label_pool[0])
        d._label_pool[0] = spy

        for _ in range(3):                               # steady state
            await d.clear()
            await d.draw_text("WAIT", 0, 20, 0xFFFFFF)

        assert spy.color_writes == 0, (
            "same text + same colour rewrote label.color %d time(s) -- the dim "
            "is being applied after the reuse guard" % spy.color_writes)

    asyncio.run(_run())
