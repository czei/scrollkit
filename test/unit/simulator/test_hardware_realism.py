"""Hardware-realism modeling: the cost accumulator, feasibility report, and the
opt-in wiring through SimulatorDisplay.

The model exists so an AI agent discovers — in the simulator — that an app which
looks great at desktop speed would crawl or run out of RAM on the real
MatrixPortal S3. These tests pin the behavior that makes it trustworthy:
off by default (zero overhead), accumulates modeled time rather than sleeping,
the Label bitmap-rebuild hook fires, the report is honestly labeled (UNCALIBRATED
estimate, or MEASURED once a device baseline is captured), and the warnings fire
on slow / over-budget frames.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # headless pygame

import time

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.simulator import SimulatorDisplay
from scrollkit.simulator.core.hardware_profile import (
    HardwareProfile, matrixportal_s3_estimate, matrixportal_s3_profile,
    baseline_path, CONFIDENCE_ESTIMATE, CONFIDENCE_CALIBRATED)
from scrollkit.simulator.core.performance_manager import (
    PerformanceManager, get_active, set_active)


@pytest.fixture(autouse=True)
def _reset_active_manager():
    """Never let the module-global active manager leak between tests."""
    set_active(None)
    yield
    set_active(None)


# --- the model in isolation ---------------------------------------------------

def _end_frame(pm):
    pm.simulate_io_operation("display_refresh")


def test_disabled_by_default_zero_overhead():
    # A fresh simulator display without hardware_timing registers no manager,
    # so the Label hook's get_active() stays None -> no work is done.
    assert get_active() is None
    d = SimulatorDisplay(width=64, height=32)
    assert get_active() is None
    report = d.feasibility_report()
    assert report.confidence == "DISABLED"
    assert report.est_hw_fps is None


def test_accumulates_time_without_sleeping():
    # 100 frames each modeling a big (~150 ms) rebuild = ~15 s of *modeled* time.
    # If the manager actually slept, this test would take ~15 s; it must not.
    pm = PerformanceManager(matrixportal_s3_estimate(), throttle=False)
    start = time.monotonic()
    for _ in range(100):
        pm.account_bitmap_rebuild(64, 32)
        _end_frame(pm)
    elapsed = time.monotonic() - start
    assert elapsed < 1.0, "accumulator must not real-sleep when throttle=False"
    report = pm.report()
    # ...yet the modeled per-frame time is large (tens to hundreds of ms).
    assert report.median_frame_ms > 100.0


def test_bitmap_rebuild_is_the_dominant_modeled_cost():
    pm = PerformanceManager(matrixportal_s3_estimate())
    pm.account_bitmap_rebuild(64, 16)
    pm.simulate_instruction_delay(3)
    _end_frame(pm)
    report = pm.report()
    bd = report.breakdown_ms
    assert bd["bitmap_rebuild"] > bd["pixel_writes"]
    assert bd["bitmap_rebuild"] > 0


def test_slow_frame_emits_stutter_warning():
    pm = PerformanceManager(matrixportal_s3_estimate())
    for _ in range(3):
        pm.account_bitmap_rebuild(64, 32)  # ~150 ms/frame -> well under 10 FPS
        _end_frame(pm)
    report = pm.report()
    assert report.est_hw_fps is not None and report.est_hw_fps < 15
    text = " ".join(report.warnings).lower()
    assert "stutter" in text or "frozen" in text or "cache" in text


def test_over_budget_ram_warns_wont_fit():
    tiny = HardwareProfile(
        name="Tiny [ESTIMATE]",
        usable_ram_bytes=10_000, base_app_ram_bytes=8_000, bytes_per_label_px=1.0,
        pixel_write_us=5.0, full_refresh_us=5_000.0, bitmap_rebuild_us_per_px=75.0,
        gc_pause_us=15_000.0, gc_every_n_frames=30)
    pm = PerformanceManager(tiny)
    pm.account_bitmap_rebuild(200, 200)  # 40 KB of bitmap -> blows a 10 KB budget
    _end_frame(pm)
    report = pm.report()
    assert report.est_peak_ram_bytes > report.ram_budget_bytes
    assert any("exceeds" in w for w in report.warnings)


def test_report_is_labeled_uncalibrated():
    pm = PerformanceManager(matrixportal_s3_estimate())
    pm.account_bitmap_rebuild(32, 8)
    _end_frame(pm)
    report = pm.report()
    assert report.confidence == CONFIDENCE_ESTIMATE
    assert report.calibrated is False
    assert report.as_dict()["calibrated"] is False
    text = report.as_text().lower()
    assert "rough estimate" in text and "not measured" in text


def test_from_measurements_flips_to_calibrated(tmp_path):
    import json
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"full_refresh_us": 1234.0}))
    profile = HardwareProfile.from_measurements(str(path))
    assert profile.confidence == CONFIDENCE_CALIBRATED
    assert profile.is_calibrated
    assert profile.full_refresh_us == 1234.0


# --- wiring through SimulatorDisplay ------------------------------------------

@pytest.mark.asyncio
async def test_hardware_timing_flag_enables_model_and_label_hook():
    d = SimulatorDisplay(width=64, height=32, hardware_timing=True)
    await d.initialize()
    assert get_active() is not None
    for i in range(10):
        await d.clear()
        await d.draw_text("FRAME %d" % i, 0, 12, 0xFFFFFF)  # changing text each frame
        await d.show()
    data = d.feasibility_report().as_dict()
    assert data["estimated_hardware_fps"] is not None
    assert data["breakdown_ms"]["bitmap_rebuild"] > 0  # the Label hook fired


@pytest.mark.asyncio
async def test_env_var_toggles_hardware_timing(monkeypatch):
    monkeypatch.setenv("SCROLLKIT_HW_SIM", "1")
    d = SimulatorDisplay(width=64, height=32)  # no explicit flag
    await d.initialize()
    assert get_active() is not None
    assert d.feasibility_report().confidence in (
        CONFIDENCE_ESTIMATE, CONFIDENCE_CALIBRATED)


# --- M3: visceral throttle mode + ambient stutter nags ------------------------

def _slow_frame(pm):
    pm.account_bitmap_rebuild(64, 32)  # ~150 ms -> well under 10 FPS
    pm.simulate_io_operation("display_refresh")


def test_ambient_warning_fires_on_slow_frame_without_sleeping():
    # ambient_warnings on but throttle OFF -> warns, never sleeps.
    pm = PerformanceManager(matrixportal_s3_estimate(), throttle=False,
                            ambient_warnings=True, warn_interval=1)
    captured = []
    pm._emit = lambda msg: captured.append(msg)
    start = time.monotonic()
    _slow_frame(pm)
    elapsed = time.monotonic() - start
    assert elapsed < 0.5, "ambient warnings must not sleep when throttle is off"
    assert len(captured) == 1 and "stutter" in captured[0]
    assert pm.last_warning is not None


def test_ambient_warning_silent_on_fast_frames():
    pm = PerformanceManager(matrixportal_s3_estimate(), ambient_warnings=True,
                            warn_interval=1)
    captured = []
    pm._emit = lambda msg: captured.append(msg)
    pm.account_bitmap_rebuild(1, 1)            # trivial frame -> very fast
    pm.simulate_io_operation("display_refresh")
    assert captured == [] and pm.last_warning is None


def test_ambient_warning_is_rate_limited():
    pm = PerformanceManager(matrixportal_s3_estimate(), ambient_warnings=True,
                            warn_interval=3)
    captured = []
    pm._emit = lambda msg: captured.append(msg)
    for _ in range(9):
        _slow_frame(pm)
    # warn_interval=3 over 9 slow frames -> nags at frames 3, 6, 9.
    assert len(captured) == 3


@pytest.mark.asyncio
async def test_throttle_flag_implies_hardware_timing():
    # throttle=True with no hardware_timing flag still enables the model.
    d = SimulatorDisplay(width=64, height=32, throttle=True)
    await d.initialize()
    pm = get_active()
    assert pm is not None and pm.throttle is True
    assert pm.ambient_warnings is True   # visceral mode nags by default


@pytest.mark.asyncio
async def test_env_throttle_toggle_enables_crawl(monkeypatch):
    monkeypatch.setenv("SCROLLKIT_HW_THROTTLE", "1")
    d = SimulatorDisplay(width=64, height=32)  # no explicit flags
    await d.initialize()
    pm = get_active()
    assert pm is not None and pm.throttle is True


# --- M4: calibration from a real device baseline -----------------------------

def test_shipped_baseline_yields_a_calibrated_profile():
    # A real MatrixPortal S3 baseline ships in the package, so the default
    # profile is MEASURED, not an estimate.
    assert os.path.exists(baseline_path())
    p = matrixportal_s3_profile()
    assert p.is_calibrated and p.confidence == CONFIDENCE_CALIBRATED
    assert "measured" in p.source.lower()


def test_calibrated_report_says_measured_not_estimate():
    pm = PerformanceManager(matrixportal_s3_profile())
    pm.account_bitmap_rebuild(40, 12)
    pm.simulate_io_operation("display_refresh")
    text = pm.report().as_text()
    assert "MEASURED on device" in text
    assert "ESTIMATE" not in text and "ROUGH ESTIMATE" not in text


def test_baseline_env_override_to_missing_file_falls_back_to_estimate(monkeypatch):
    monkeypatch.setenv("SCROLLKIT_HW_BASELINE", "/no/such/baseline.json")
    p = matrixportal_s3_profile()
    assert not p.is_calibrated and p.confidence == CONFIDENCE_ESTIMATE


def test_from_measurements_keeps_descriptive_source(tmp_path):
    import json
    path = tmp_path / "b.json"
    path.write_text(json.dumps({"full_refresh_us": 9999.0,
                                "source": "measured on my bench"}))
    p = HardwareProfile.from_measurements(str(path))
    assert p.is_calibrated
    assert p.source == "measured on my bench"   # JSON source preserved, not the path
    assert p.full_refresh_us == 9999.0


# --- strict feasibility gate --------------------------------------------------

from scrollkit.exceptions import FeasibilityError  # noqa: E402


def _strict_pm(**kw):
    """A strict PerformanceManager on the calibrated profile (20fps budget)."""
    kw.setdefault("warmup_frames", 2)
    kw.setdefault("gate_window", 8)
    return PerformanceManager(matrixportal_s3_profile(), strict=True, **kw)


def _inject_frame(pm, us):
    """End a frame whose modeled cost is exactly ``us`` microseconds."""
    pm._frame.bitmap_rebuild_us += us
    pm._end_frame()


def test_strict_sustained_over_budget_raises():
    # Every frame ~60 ms (over the 50 ms / 20 fps budget, under the 100 ms
    # transient ceiling) -> the steady-state median bites once the window fills.
    pm = _strict_pm()
    with pytest.raises(FeasibilityError):
        for _ in range(12):
            _inject_frame(pm, 60_000)


def test_strict_tolerates_an_isolated_rebuild_spike():
    # 19 cheap frames + ONE 60 ms spike (over budget, under ceiling). The median
    # window absorbs the lone spike, so strict mode does NOT false-trip — this is
    # the whole point of a steady-state gate over a single-frame budget.
    pm = _strict_pm()
    for i in range(20):
        _inject_frame(pm, 60_000 if i == 10 else 1_000)   # no exception expected


def test_strict_transient_ceiling_raises_on_a_catastrophic_frame():
    pm = _strict_pm()
    _inject_frame(pm, 1_000)            # warmup
    _inject_frame(pm, 1_000)            # warmup
    _inject_frame(pm, 1_000)            # past warmup, cheap
    with pytest.raises(FeasibilityError):
        _inject_frame(pm, 120_000)     # > 100 ms ceiling -> immediate bust


def test_strict_warmup_grace_exempts_the_first_frames():
    pm = _strict_pm(warmup_frames=2)
    # The first two frames are catastrophic but exempt (one-time scene build).
    _inject_frame(pm, 200_000)
    _inject_frame(pm, 200_000)
    # The third catastrophic frame is past the grace -> it bites.
    with pytest.raises(FeasibilityError):
        _inject_frame(pm, 200_000)


def test_strict_ram_breach_raises_even_when_time_fits():
    # A profile where bitmaps are time-free but RAM-expensive isolates the RAM
    # gate from the time gate.
    ram_bound = HardwareProfile(
        name="RamBound [ESTIMATE]",
        usable_ram_bytes=10_000, base_app_ram_bytes=8_000, bytes_per_label_px=1.0,
        pixel_write_us=0.0, full_refresh_us=0.0, bitmap_rebuild_us_per_px=0.0,
        gc_pause_us=0.0, gc_every_n_frames=30)
    pm = PerformanceManager(ram_bound, strict=True, warmup_frames=2)
    _inject_frame(pm, 0)
    _inject_frame(pm, 0)
    _inject_frame(pm, 0)               # past warmup, RAM still fits
    pm.account_bitmap_rebuild(200, 200)  # 40 KB live bitmap -> blows a 10 KB budget
    with pytest.raises(FeasibilityError):
        pm._end_frame()


def test_strict_resets_frame_state_when_it_raises():
    # If a caller catches FeasibilityError and keeps going, the live frame must
    # already be reset (not still carrying the busted cost) so the next frame's
    # accounting and the rolling history stay correct.
    pm = _strict_pm(warmup_frames=0)
    try:
        _inject_frame(pm, 200_000)         # > transient ceiling -> raises
    except FeasibilityError:
        pass
    assert pm._frame.total_us == 0         # live frame was reset before the raise
    assert pm.frames[-1].total_us == 200_000  # history kept the real busted frame
    # ...and a subsequent cheap frame is accounted on its own, not on top.
    _inject_frame(pm, 1_000)
    assert pm.frames[-1].total_us == 1_000


def test_strict_off_by_default_never_raises():
    # Default (strict=False) must behave exactly as before: never raise, even on
    # sustained catastrophic frames.
    pm = PerformanceManager(matrixportal_s3_profile())  # strict defaults to False
    for _ in range(12):
        _inject_frame(pm, 500_000)     # absurdly over budget; still no exception
    assert pm.report().est_hw_fps is not None


def test_account_bulk_op_feeds_the_breakdown():
    pm = PerformanceManager(matrixportal_s3_profile())
    pm.account_bulk_op("fill_region", 512)
    pm.account_bulk_op("blit", 256)
    pm.simulate_io_operation("display_refresh")
    bd = pm.report().breakdown_ms
    assert "bulk_ops" in bd and bd["bulk_ops"] > 0


@pytest.mark.asyncio
async def test_one_show_is_exactly_one_modeled_frame():
    # Regression guard: show() must not double-count modeled frames (it used to
    # render the matrix twice — via display.refresh() and again explicitly — so
    # the estimated FPS disagreed with the throttle crawl by ~2x).
    d = SimulatorDisplay(width=64, height=32, hardware_timing=True)
    await d.initialize()
    pm = get_active()
    before = pm._frame_index
    for i in range(5):
        await d.clear()
        await d.draw_text("HI %d" % i, 0, 12, 0xFFFFFF)
        await d.show()
    assert pm._frame_index - before == 5, "each show() must be exactly one frame"
