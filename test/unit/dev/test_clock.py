"""scrollkit.dev.clock — content time driven by modeled device time.

The bug this closes is a real one: a headless run steps frames with no
inter-frame sleep, so a ``duration=2.0`` item never expires and a correct
animated app scores as "never animates". The fix that preceded this one — a
fixed-rate frame clock — traded that for a quieter version of the same error,
where a sign modeling 71 fps advances its content at 20.

These tests pin the property that makes the injection worth having: the clock
reads modeled *device* microseconds, which come from operations rather than from
wall time, so it says the same thing on any host and in any runtime.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # headless pygame

import time

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.app.base import ScrollKitApp
from scrollkit.display import content as content_module
from scrollkit.display.content import StaticText
from scrollkit.dev import run_headless
from scrollkit.dev.clock import (
    VirtualClockUnavailable,
    install_virtual_clock,
    modeled_device_time,
    uninstall_virtual_clock,
    virtual_clock_installed,
)
from scrollkit.simulator.core.hardware_profile import matrixportal_s3_profile
from scrollkit.simulator.core.performance_manager import (
    PerformanceManager,
    get_active,
    set_active,
)

FRAMES = 60


class _TimedApp(ScrollKitApp):
    """Two duration-driven items — the shape that froze without a clock."""

    def __init__(self, duration=0.5):
        super().__init__(enable_web=False, update_interval=10)
        self._duration = duration

    async def create_display(self):
        from scrollkit.display.simulator import SimulatorDisplay
        return SimulatorDisplay(width=64, height=32)

    async def setup(self):
        self.content_queue.add(StaticText("ONE", x=4, y=12, color=0xFFFFFF,
                                          duration=self._duration))
        self.content_queue.add(StaticText("TWO", x=4, y=12, color=0xFF0000,
                                          duration=self._duration))


class _BrokenApp(_TimedApp):
    async def setup(self):
        raise RuntimeError("boom in setup")


@pytest.fixture(autouse=True)
def _leave_no_clock_behind():
    """No test may leak an injection into the next one."""
    yield
    uninstall_virtual_clock()
    set_active(None)


def _manager(**kw):
    return PerformanceManager(matrixportal_s3_profile(), **kw)


def _spend_frame(pm, pixels=100):
    """One frame's worth of accounted work, ending at the refresh."""
    for _ in range(pixels):
        pm.simulate_instruction_delay(1)
    pm.simulate_io_operation("display_refresh")


# -- the accumulator -------------------------------------------------------

def test_modeled_time_accumulates_across_frames():
    pm = _manager()
    assert pm.modeled_elapsed_us == 0.0
    _spend_frame(pm)
    one = pm.modeled_elapsed_us
    assert one > 0
    _spend_frame(pm)
    assert pm.modeled_elapsed_us == pytest.approx(2 * one)
    assert pm.frames_ended == 2
    assert pm.modeled_elapsed_s == pytest.approx(pm.modeled_elapsed_us / 1e6)


def test_the_total_outlives_the_frame_history():
    """The rolling history forgets; a clock built on it would run backwards.

    ``self._frames`` is a bounded deque — that is right for a median over the
    recent window and wrong for elapsed time, which only ever goes up.
    """
    pm = _manager(history=3)
    for _ in range(10):
        _spend_frame(pm)
    assert len(pm.frames) == 3
    assert pm.frames_ended == 10
    assert pm.modeled_elapsed_us == pytest.approx(10 * pm.frames[0].total_us)


def test_modeled_time_does_not_move_with_wall_time():
    pm = _manager()
    _spend_frame(pm)
    before = pm.modeled_elapsed_us
    time.sleep(0.05)
    assert pm.modeled_elapsed_us == before


# -- the injection ---------------------------------------------------------

def test_the_source_reads_the_active_manager():
    pm = _manager()
    set_active(pm)
    _spend_frame(pm)
    assert modeled_device_time() == pytest.approx(pm.modeled_elapsed_s)


def test_reading_the_clock_with_no_model_says_so():
    """Loudly, and on the first frame.

    Returning 0.0 here would be the frozen-content bug wearing a different hat:
    the run would look fine and the content would never advance.
    """
    set_active(None)
    with pytest.raises(VirtualClockUnavailable) as exc:
        modeled_device_time()
    assert "hardware" in str(exc.value)


def test_install_replaces_the_clock_and_uninstall_restores_it():
    original = content_module.get_time
    assert not virtual_clock_installed()

    install_virtual_clock(source=lambda: 42.0)
    assert virtual_clock_installed()
    assert content_module.get_time() == 42.0

    uninstall_virtual_clock()
    assert not virtual_clock_installed()
    assert content_module.get_time is original


def test_installing_twice_still_restores_the_real_clock():
    original = content_module.get_time
    install_virtual_clock(source=lambda: 1.0)
    install_virtual_clock(source=lambda: 2.0)
    uninstall_virtual_clock()
    assert content_module.get_time is original


def test_particles_get_the_same_clock():
    """Particles read time too, and a half-injected run is worse than neither."""
    from scrollkit.effects import particles

    install_virtual_clock(source=lambda: 7.0)
    assert particles.get_time() == 7.0
    uninstall_virtual_clock()
    assert particles.get_time is not None


# -- through the harness ---------------------------------------------------

def test_content_time_is_modeled_device_time():
    """The whole point: content elapsed == what the frames cost the panel.

    Both sides of this assertion are modeled, so it holds on a fast laptop and a
    loaded CI box alike.
    """
    result = run_headless(_TimedApp(), frames=FRAMES, hardware=True,
                          virtual_clock=True)
    assert result.errors == []
    modeled_s = result.hardware["median_frame_ms"] * FRAMES / 1000.0
    assert result.current_content["elapsed"] == pytest.approx(modeled_s, rel=0.1)


def test_the_clock_is_identical_across_two_runs():
    a = run_headless(_TimedApp(), frames=FRAMES, hardware=True, virtual_clock=True)
    b = run_headless(_TimedApp(), frames=FRAMES, hardware=True, virtual_clock=True)
    assert a.current_content["elapsed"] == b.current_content["elapsed"]


def test_duration_driven_content_advances():
    """Short items expire, which is the whole point: the bug never did.

    Asserted as a bound on the CURRENT item's age, not as "the last frame shows
    TWO". Items this short turn the queue over ~18 times in 60 frames, so which
    of the two is up at the cutoff is a phase accident that flips with a
    one-frame change in modeled cost — it read TWO on macOS and ONE on Linux CI
    with the clock working correctly on both. What actually separates a working
    clock from the frozen one is that no item stays on screen longer than it
    asked to.
    """
    duration = 0.05
    result = run_headless(_TimedApp(duration=duration), frames=FRAMES,
                          hardware=True, virtual_clock=True)
    assert result.errors == []
    # An item can only overrun by the single frame that discovers the expiry,
    # and no frame in the run cost more than worst_frame_ms — which is the term
    # to use, not the median: the discovering frame is usually the expensive
    # rebuild frame, so a median-sized slack is too tight and fails on some
    # frame counts. Both terms come from this same run, so the assertion
    # carries no host-specific constant.
    worst_frame_s = result.hardware["worst_frame_ms"] / 1000.0
    assert result.current_content["elapsed"] <= duration + worst_frame_s


def test_content_that_outlasts_the_run_never_advances():
    """The other half of the pair, and the shape of the original bug.

    An item longer than the run cannot expire, so it stays up and its age grows
    to the length of the whole run. Without this the test above would also pass
    against a clock stuck at 0.0.
    """
    result = run_headless(_TimedApp(duration=1e6), frames=FRAMES, hardware=True,
                          virtual_clock=True)
    assert result.current_content["text"] == "ONE"
    assert result.current_content["elapsed"] > 0.05


def test_the_run_does_not_leak_the_injection():
    original = content_module.get_time
    run_headless(_TimedApp(), frames=10, hardware=True, virtual_clock=True)
    assert not virtual_clock_installed()
    assert content_module.get_time is original


def test_the_injection_is_removed_even_when_the_app_fails():
    original = content_module.get_time
    result = run_headless(_BrokenApp(), frames=10, hardware=True, virtual_clock=True)
    assert result.errors
    assert not virtual_clock_installed()
    assert content_module.get_time is original


def test_default_runs_are_untouched():
    """No parameter, no injection — the harness's historical behaviour."""
    original = content_module.get_time
    run_headless(_TimedApp(), frames=10, hardware=True)
    assert content_module.get_time is original
    assert not virtual_clock_installed()


def test_the_feasibility_report_does_not_move():
    """Pacing and clocks change wall time; modeled cost comes from operations."""
    plain = run_headless(_TimedApp(), frames=FRAMES, hardware=True)
    clocked = run_headless(_TimedApp(), frames=FRAMES, hardware=True,
                           virtual_clock=True)
    assert (plain.hardware["median_frame_ms"]
            == clocked.hardware["median_frame_ms"])


def test_the_manager_is_gone_after_a_run():
    run_headless(_TimedApp(), frames=10, hardware=True, virtual_clock=True)
    assert get_active() is None
