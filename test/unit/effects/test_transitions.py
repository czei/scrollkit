"""Class 2 — theatrical transitions on the OverlayMask.

For every transition: the old content is fully hidden at peak cover (and the swap
has not fired yet), the new content is revealed by completion, per-frame mask writes
are bounded (no full-screen Python repaint), and it is strict-feasible at 20 fps.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import DisplayContent
from scrollkit.dev import run_headless
import scrollkit.simulator.bitmaptools as bt
from scrollkit.effects.transitions import (
    IrisSnap, VenetianShutters, MosaicResolve, CRTCollapse, LightSlitRewrite,
)

# The classes whose covered span fills the panel exactly (64x32) so "fully hidden"
# is a clean all-opaque assertion. MosaicResolve uses 8x4 blocks (exact divisors).
ALL_TRANSITIONS = [IrisSnap, VenetianShutters, MosaicResolve, CRTCollapse,
                   LightSlitRewrite]


async def _make_display():
    from scrollkit.display.simulator import SimulatorDisplay
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    return d


@pytest.mark.asyncio
@pytest.mark.parametrize("cls", ALL_TRANSITIONS)
async def test_cover_hides_then_swaps_then_reveals(cls):
    d = await _make_display()
    half = 6
    t = cls(duration_frames=half)
    swaps = []
    await t.start(d, lambda: swaps.append(1))
    for _ in range(half):                       # full cover phase
        await t.render(d)
    bm = t._mask.bitmap
    # Peak cover: every pixel is opaque (content hidden) and the swap has NOT fired.
    assert all(bm[x, y] != 0 for x in range(d.width) for y in range(d.height)), cls.__name__
    assert swaps == [], cls.__name__
    await t.render(d)                           # first reveal frame fires the swap
    assert swaps == [1], cls.__name__
    for _ in range(half + 4):                   # finish the reveal
        await t.render(d)
    assert t.is_complete, cls.__name__
    # Fully revealed: mask back to transparent.
    assert all(bm[x, y] == 0 for x in range(d.width) for y in range(d.height)), cls.__name__


@pytest.mark.asyncio
@pytest.mark.parametrize("cls", ALL_TRANSITIONS)
async def test_per_frame_writes_are_bounded(cls, monkeypatch):
    d = await _make_display()
    t = cls(duration_frames=6)
    await t.start(d, lambda: None)
    orig = bt.fill_region

    def counting(*a, **k):
        counting.n += 1
        return orig(*a, **k)
    counting.n = 0
    monkeypatch.setattr(bt, "fill_region", counting)

    peak = 0
    for _ in range(14):
        counting.n = 0
        await t.render(d)
        peak = max(peak, counting.n)
    # Bounded per-frame bulk calls — never anything like a 2048-pixel Python loop.
    assert peak <= 2 * d.height + 8, (cls.__name__, peak)


@pytest.mark.asyncio
async def test_mosaic_is_deterministic_given_seed():
    # MosaicResolve block order is seeded; it must match across runs with the same
    # seed and differ with another seed.
    d = await _make_display()
    a = MosaicResolve(seed=7)
    b = MosaicResolve(seed=7)
    await a.start(d, lambda: None)
    await b.start(d, lambda: None)
    assert a._order == b._order
    c = MosaicResolve(seed=8)
    await c.start(d, lambda: None)
    assert a._order != c._order


# --- strict feasibility: each transition passes the gate at 20 fps -----------

class _TransitionLoop(DisplayContent):
    """Runs a transition repeatedly between two labels (covered swap rebuilds the
    label, which the gate tolerates) so the run keeps advancing for 120 frames."""

    FACTORY = None

    def __init__(self):
        super().__init__(duration=None, priority=2)
        self.label = "ALPHA"
        self.t = self.FACTORY()
        self._started = False

    async def render(self, display):
        if not self._started:
            await self.t.start(display, self._swap)
            self._started = True
        await display.draw_text(self.label, 6, 12, 0xFFFFFF)
        await self.t.render(display)
        if self.t.is_complete:
            self.t = self.FACTORY()
            await self.t.start(display, self._swap)

    def _swap(self):
        self.label = "BETA" if self.label == "ALPHA" else "ALPHA"

    @property
    def is_complete(self):
        return False


def _loop_cls(factory):
    return type("_Loop", (_TransitionLoop,), {"FACTORY": staticmethod(factory)})


def _app(content_cls):
    class _App(ScrollKitApp):
        def __init__(self):
            super().__init__(enable_web=False, update_interval=10)
            self._c = None

        async def create_display(self):
            from scrollkit.display.simulator import SimulatorDisplay
            return SimulatorDisplay(width=64, height=32)

        async def prepare_display_content(self):
            return self._c

        async def setup(self):
            self._c = content_cls()
    return _App()


@pytest.mark.parametrize("cls", ALL_TRANSITIONS)
def test_transition_passes_strict_at_20fps(cls):
    # duration_frames=7 -> a 14-frame cycle that does NOT evenly divide the 120-frame
    # window, so the first and last frames land on different phases (the harness's
    # advanced= heuristic compares them) instead of aliasing to the same picture.
    content_cls = _loop_cls(lambda: cls(duration_frames=7, cover_color=0x202020))
    result = run_headless(_app(content_cls), frames=120, hardware=True, strict=True)
    assert result.errors == [], (cls.__name__, result.errors)
    assert result.ok is True
    assert result.advanced is True
