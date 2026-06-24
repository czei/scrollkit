"""The headless verification harness — scrollkit.dev.run_headless.

This is the AI agent's primary tool: write an app, run it headlessly, read back
whether it rendered, advanced, and would survive on real hardware. The tests pin
the contract: deterministic by frame count, a sane RunResult, errors surfaced
(not swallowed), and the hardware feasibility block present only when requested.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # headless pygame

import time

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import ScrollingText, StaticText, DisplayContent
from scrollkit.dev import run_headless, run_headless_async, RunResult


class _ScrollApp(ScrollKitApp):
    def __init__(self):
        super().__init__(enable_web=False, update_interval=10)

    async def create_display(self):
        from scrollkit.display.simulator import SimulatorDisplay
        return SimulatorDisplay(width=64, height=32)

    async def setup(self):
        self.content_queue.add(ScrollingText("HELLO HARDWARE", y=12, color=0xFFFFFF))


class _StaticApp(_ScrollApp):
    async def setup(self):
        self.content_queue.add(StaticText("HI", x=4, y=12, color=0xFFFFFF))


class _BrokenSetupApp(_ScrollApp):
    async def setup(self):
        raise RuntimeError("boom in setup")


def test_run_headless_returns_sane_result():
    result = run_headless(_ScrollApp(), frames=30)
    assert isinstance(result, RunResult)
    assert result.frames == 30
    assert not result.is_blank
    assert result.bright_pixels > 0
    assert result.advanced is True          # scrolling text moved
    assert result.errors == []
    assert result.ok is True


def test_frame_count_is_deterministic():
    # Same app + same frame count -> identical rendered state (reproducible).
    a = run_headless(_ScrollApp(), frames=25)
    b = run_headless(_ScrollApp(), frames=25)
    assert a.frames == b.frames == 25
    assert a.bright_pixels == b.bright_pixels
    assert a.coverage == b.coverage
    # Final scroll position is part of current_content and must match.
    assert a.current_content["position"] == b.current_content["position"]


def test_seconds_is_sugar_for_frames_at_20fps():
    result = run_headless(_ScrollApp(), seconds=1.0)
    assert result.frames == 20


def test_static_content_does_not_report_advanced():
    result = run_headless(_StaticApp(), frames=15)
    assert result.is_blank is False
    assert result.advanced is False         # nothing moved
    assert result.current_content["type"] == "StaticText"


def test_errors_are_surfaced_not_swallowed():
    result = run_headless(_BrokenSetupApp(), frames=10)
    assert any("setup() failed" in e for e in result.errors)
    assert result.ok is False


def test_hardware_block_present_when_enabled():
    result = run_headless(_ScrollApp(), frames=20, hardware=True)
    assert result.hardware is not None
    # The shipped profile is calibrated from a real device baseline.
    assert result.hardware["calibrated"] is True
    assert result.estimated_hardware_fps is not None
    assert result.hardware_text and "MEASURED on device" in result.hardware_text


def test_hardware_block_absent_when_disabled():
    result = run_headless(_ScrollApp(), frames=20, hardware=False)
    assert result.hardware is None
    assert result.estimated_hardware_fps is None


def test_screenshot_is_written(tmp_path):
    path = str(tmp_path / "frame.png")
    result = run_headless(_ScrollApp(), frames=10, screenshot=path)
    assert result.screenshot == path
    assert os.path.exists(path) and os.path.getsize(path) > 0


@pytest.mark.asyncio
async def test_async_entry_point_works_inside_a_loop():
    # run_headless() uses asyncio.run() and can't be called from a running loop;
    # run_headless_async() is the in-loop entry point.
    result = await run_headless_async(_ScrollApp(), frames=12)
    assert result.frames == 12
    assert not result.is_blank


class _HeavyThrottledApp(_ScrollApp):
    """Heavy per-frame redraw on a throttle=True display — the harness must still
    run it fast (headless never crawls), even though a live window would."""

    async def create_display(self):
        from scrollkit.display.simulator import SimulatorDisplay
        return SimulatorDisplay(width=64, height=32, throttle=True)

    async def setup(self):
        self.content_queue.add(_HeavyContent())


class _HeavyContent(DisplayContent):
    def __init__(self):
        super().__init__(duration=None, priority=2)
        self.n = 0

    async def render(self, display):
        self.n += 1
        for i in range(12):  # ~150 ms/frame modeled -> would crawl if throttled
            await display.draw_text("%02d:%02d" % (i, self.n % 60),
                                    (i % 4) * 16, (i // 4) * 10, 0xFFAA00)

    @property
    def is_complete(self):
        return False


class _DefaultDisplayApp(ScrollKitApp):
    """No create_display() override -> exercises the default UnifiedDisplay
    auto-detect path (not SimulatorDisplay)."""

    def __init__(self):
        super().__init__(enable_web=False, update_interval=10)

    async def setup(self):
        self.content_queue.add(ScrollingText("UNIFIED", y=12, color=0xFF00FF))


def test_default_unified_display_app_gets_feasibility():
    # Apps that don't pick a display still render and get a hardware report,
    # because UnifiedDisplay honors the harness's hardware-timing env var too.
    result = run_headless(_DefaultDisplayApp(), frames=25)
    assert not result.is_blank and result.advanced
    assert result.hardware is not None
    assert result.estimated_hardware_fps is not None


def test_harness_never_throttles_even_if_app_requests_it():
    # If the harness honored the display's throttle=True, 20 heavy frames would
    # sleep ~3 s. Forced off, it finishes well under that.
    start = time.monotonic()
    result = run_headless(_HeavyThrottledApp(), frames=20)
    elapsed = time.monotonic() - start
    assert result.frames == 20 and not result.is_blank
    assert elapsed < 1.5, "headless run honored throttle (slept) — it must not"


# --- strict feasibility gate through run_headless ------------------------------

class _StrictHeavyContent(DisplayContent):
    """A full glyph-bitmap rebuild of an ~84-char string every frame (~60+ ms
    modeled on the device) — sustained over the 50 ms / 20 fps budget."""

    def __init__(self):
        super().__init__(duration=None, priority=2)
        self.n = 0

    async def render(self, display):
        self.n += 1
        await display.draw_text(("HW %02d " % (self.n % 100)) * 14, 0, 12, 0xFFAA00)

    @property
    def is_complete(self):
        return False


class _StrictHeavyApp(_ScrollApp):
    async def setup(self):
        self.content_queue.add(_StrictHeavyContent())


class _OneSpikeContent(DisplayContent):
    """Cheap (static, unchanged text) except for a single mid-run rebuild spike:
    one ~55 ms glyph rebuild when the visible string changes once. The strict
    gate's median window must absorb it (no false trip)."""

    def __init__(self):
        super().__init__(duration=None, priority=2)
        self.n = 0

    async def render(self, display):
        self.n += 1
        text = ("SPIKE " * 12) if self.n >= 6 else "OK"   # changes exactly once
        await display.draw_text(text, 0, 12, 0xFFFFFF)

    @property
    def is_complete(self):
        return False


class _OneSpikeApp(_ScrollApp):
    async def setup(self):
        self.content_queue.add(_OneSpikeContent())


def test_strict_run_fails_on_sustained_over_budget():
    result = run_headless(_StrictHeavyApp(), frames=30, strict=True)
    assert result.ok is False
    assert any("feasibility" in e.lower() for e in result.errors)


def test_strict_run_passes_a_cheap_effect():
    # 160 frames (8 s at 20 FPS) keeps the text mid-scroll on its second pass
    # for any library speed setting (25–50 px/s), avoiding the blank-buffer
    # restart frame that frames=120 coincidentally hit with Medium speed.
    result = run_headless(_ScrollApp(), frames=160, strict=True)
    assert result.ok is True
    assert result.errors == []
    assert result.advanced is True


def test_strict_run_tolerates_one_isolated_rebuild():
    result = run_headless(_OneSpikeApp(), frames=30, strict=True)
    assert result.ok is True, result.errors


def test_non_strict_run_only_warns_on_heavy_effect():
    # The same heavy effect under strict=False renders fine (warnings only).
    result = run_headless(_StrictHeavyApp(), frames=30, strict=False)
    assert result.ok is True
    assert not any("feasibility" in e.lower() for e in result.errors)
