#!/usr/bin/env python3
"""Tests for ScrollKitApp's data-refresh resilience + last-resort auto-reboot.

The watchdog only catches a frozen loop; a box whose every fetch fails is not
frozen (loop runs, web server serves, panel shows stale data). These assert the
framework-level safety net: the app reports refresh outcomes, the box exposes a
staleness signal, and — opt-in — reboots after a sustained failure run.
"""
import sys
import types

from unittest.mock import MagicMock, patch

from scrollkit.app import SLDKApp


class TestRefreshSignals:
    def test_counts_increment_and_reset(self, mock_circuitpython_imports):
        app = SLDKApp(enable_web=False)
        assert app.consecutive_refresh_failures == 0
        assert app.data_stale is False

        assert app.note_refresh_result(False, reason="timeout") == 1
        assert app.note_refresh_result(False, reason="timeout") == 2
        assert app.consecutive_refresh_failures == 2
        assert app.data_stale is True
        assert app.last_refresh_error == "timeout"

        assert app.note_refresh_result(True) == 0
        assert app.consecutive_refresh_failures == 0
        assert app.data_stale is False
        assert app.last_refresh_error is None

    def test_seconds_since_last_success(self, mock_circuitpython_imports):
        app = SLDKApp(enable_web=False)
        # Never succeeded yet.
        assert app.seconds_since_last_refresh_success() is None
        app.note_refresh_result(False, reason="x")
        assert app.seconds_since_last_refresh_success() is None
        app.note_refresh_result(True)
        secs = app.seconds_since_last_refresh_success()
        assert secs is not None and secs >= 0


class TestAutoReboot:
    def test_reboot_after_threshold_when_enabled(self, mock_circuitpython_imports):
        app = SLDKApp(enable_web=False, enable_auto_reboot=True,
                      max_refresh_failures=3)
        with patch.object(app, "_hardware_reset") as reset:
            with patch("scrollkit.utils.diagnostics.open") as diag_open:
                # No failure-reboot epoch pending (a bare MagicMock would read
                # as truthy and defer the reboot).
                diag_open.return_value.was_deliberate_reboot.return_value = False
                app.note_refresh_result(False, reason="oserror")  # 1
                assert not reset.called
                app.note_refresh_result(False, reason="oserror")  # 2
                assert not reset.called
                app.note_refresh_result(False, reason="oserror")  # 3 -> reboot
        assert reset.call_count == 1
        # The cause is persisted to NVM before resetting (diagnosable post-reboot),
        # and the failure-reboot epoch is opened for the next boot's rate limit.
        assert diag_open.return_value.record_crash.called
        recorded = diag_open.return_value.record_crash.call_args[0][0]
        assert "oserror" in recorded
        assert "consecutive refresh failures" in recorded
        assert diag_open.return_value.note_deliberate_reboot.called

    def test_no_reboot_when_disabled_by_default(self, mock_circuitpython_imports):
        app = SLDKApp(enable_web=False, max_refresh_failures=2)
        assert app.enable_auto_reboot is False
        with patch.object(app, "_hardware_reset") as reset:
            for _ in range(10):
                app.note_refresh_result(False, reason="oserror")
        assert not reset.called

    def test_success_prevents_reboot(self, mock_circuitpython_imports):
        """A success mid-run resets the streak, so an intermittent network never
        accumulates to the reboot threshold."""
        app = SLDKApp(enable_web=False, enable_auto_reboot=True,
                      max_refresh_failures=3)
        with patch.object(app, "_hardware_reset") as reset:
            with patch("scrollkit.utils.diagnostics.open"):
                for _ in range(5):
                    app.note_refresh_result(False, reason="blip")
                    app.note_refresh_result(True)  # recovers each time
        assert not reset.called


class TestHardwareReset:
    def test_calls_microcontroller_reset_on_device(self, mock_circuitpython_imports):
        """On CircuitPython the seam actually calls microcontroller.reset()."""
        app = SLDKApp(enable_web=False)
        fake_mc = types.ModuleType("microcontroller")
        fake_mc.reset = MagicMock()
        with patch.object(app, "_is_circuitpython", return_value=True):
            with patch.dict(sys.modules, {"microcontroller": fake_mc}):
                app._hardware_reset()
        assert fake_mc.reset.called

    def test_noop_on_desktop(self, mock_circuitpython_imports):
        """Off-device the reset is a no-op — the simulator/tests never reboot."""
        app = SLDKApp(enable_web=False)
        assert app._is_circuitpython() is False
        # Must not raise even though microcontroller isn't importable here.
        app._hardware_reset()

    def test_auto_reboot_is_noop_off_device(self, mock_circuitpython_imports):
        """_auto_reboot itself is safe to call on desktop (records + no reset)."""
        app = SLDKApp(enable_web=False)
        with patch("scrollkit.utils.diagnostics.open") as diag_open:
            app._auto_reboot("test reason")
        assert diag_open.return_value.record_crash.called


class TestFailureRebootRateLimit:
    """2026-07-19: during a sustained failure epoch (a failure-driven reboot
    happened and no fetch has succeeded since — the NVM flag), further
    failure reboots wait out FAILURE_REBOOT_COOLDOWN_S of uptime, so an
    ordinary long outage settles to ~one reboot/hour, not one every ~13 min."""

    def test_epoch_defers_reboot_until_cooldown(self, mock_circuitpython_imports):
        app = SLDKApp(enable_web=False, enable_auto_reboot=True,
                      max_refresh_failures=3)
        with patch.object(app, "_hardware_reset") as reset:
            with patch("scrollkit.utils.diagnostics.open") as diag_open:
                diag_open.return_value.was_deliberate_reboot.return_value = True
                for _ in range(6):
                    app.note_refresh_result(False, reason="outage")
                assert not reset.called          # young uptime: deferred
                app._uptime_s = lambda: app.FAILURE_REBOOT_COOLDOWN_S + 1
                app.note_refresh_result(False, reason="outage")
        assert reset.call_count == 1             # cooled down: one reboot

    def test_no_epoch_means_first_reboot_fires_normally(
            self, mock_circuitpython_imports):
        app = SLDKApp(enable_web=False, enable_auto_reboot=True,
                      max_refresh_failures=2)
        with patch.object(app, "_hardware_reset") as reset:
            with patch("scrollkit.utils.diagnostics.open") as diag_open:
                diag_open.return_value.was_deliberate_reboot.return_value = False
                app.note_refresh_result(False, reason="outage")
                app.note_refresh_result(False, reason="outage")
        assert reset.call_count == 1


class TestProgressSupervision:
    """The alive-and-stale deadman (2026-07-19): a dead/hung data task must
    not hide behind a happily-fed watchdog. Progress = attempts COMPLETING,
    success or failure alike — an offline box actively retrying is healthy."""

    def _app(self):
        app = SLDKApp(enable_web=False)
        app.running = True
        return app

    def test_offline_but_retrying_is_not_a_fault(self, mock_circuitpython_imports):
        app = self._app()
        now = 10_000.0
        app._data_process_started = 0.0
        app._data_loop_beat = now - 60           # loop iterating
        app._attempt_started = now - 120
        app._attempt_finished = now - 119        # attempts complete (and FAIL)
        task = MagicMock()
        task.done.return_value = False
        app._data_task = task
        assert app._progress_fault(now) is None

    def test_dead_data_task_is_a_fault(self, mock_circuitpython_imports):
        app = self._app()
        task = MagicMock()
        task.done.return_value = True
        app._data_task = task
        assert app._progress_fault(10_000.0) == "data task exited"

    def test_hung_attempt_is_a_fault(self, mock_circuitpython_imports):
        app = self._app()
        now = 10_000.0
        app._data_loop_beat = now - 30
        app._attempt_started = now - app.ATTEMPT_STALL_S - 1
        app._attempt_finished = None             # never returned
        assert "never finished" in app._progress_fault(now)

    def test_stalled_loop_is_a_fault(self, mock_circuitpython_imports):
        app = self._app()
        now = 100_000.0
        window = max(app.DATA_LOOP_STALL_FLOOR_S, 3 * app.update_interval)
        app._data_loop_beat = now - window - 1
        assert "no progress" in app._progress_fault(now)

    def test_supervisor_records_reason_and_fires_once(
            self, mock_circuitpython_imports):
        app = self._app()
        task = MagicMock()
        task.done.return_value = True
        app._data_task = task
        with patch.object(app, "_hardware_reset") as reset:
            with patch("scrollkit.utils.diagnostics.open") as diag_open:
                app._supervise_progress()
                app._last_supervisor_check = 0   # force a re-check
                app._supervise_progress()        # _supervisor_fired: no repeat
        assert reset.call_count == 1
        recorded = diag_open.return_value.record_crash.call_args[0][0]
        assert "deadman" in recorded and "data task exited" in recorded


class TestDataTaskAlwaysCreated:
    def test_low_memory_does_not_omit_the_data_task(
            self, mock_circuitpython_imports):
        """A transient low free-memory reading at startup used to skip creating
        the data task entirely — no refresh, counter, or recovery ever ran
        again. It is ALWAYS created now; the loop degrades per-cycle instead."""
        import asyncio

        app = SLDKApp(enable_web=True)

        async def _noop():
            return None
        app.setup = _noop
        app._initialize_display = _noop

        created = []

        def _fake_create_task(coro):
            created.append(getattr(coro, "__qualname__", str(coro)))
            coro.close()
            t = MagicMock()
            t.done.return_value = True
            return t

        async def _fake_gather(*aws, return_exceptions=False):
            return []

        with patch("scrollkit.app.base.create_task", _fake_create_task), \
             patch("scrollkit.app.base.gather", _fake_gather), \
             patch("scrollkit.app.base.free_memory", return_value=1000):
            asyncio.run(app.run())

        assert any("_data_update_process" in n for n in created), created
        assert not any("_web_server_process" in n for n in created), \
            "web stays memory-gated (optional); data is not (required)"


class TestRenderErrorStarvesWatchdog:
    """A permanently-broken render path must STOP feeding the watchdog (the
    2026-07-16 'bricked morning': catch-log-refeed kept a frozen panel alive
    indefinitely). One successful frame resumes feeding."""

    def test_feeding_stops_after_consecutive_errors_and_resumes_on_recovery(
            self, mock_circuitpython_imports):
        import asyncio

        app = SLDKApp(enable_web=False)
        app.MAX_CONSECUTIVE_RENDER_ERRORS = 3
        app.running = True

        feeds = {"n": 0}
        app._feed_watchdog = lambda: feeds.__setitem__("n", feeds["n"] + 1)

        calls = {"n": 0}
        async def _step():
            calls["n"] += 1
            if calls["n"] <= 5:                 # 5 consecutive failures...
                raise RuntimeError("render broken")
            if calls["n"] == 8:                 # then recover briefly, then stop
                app.running = False
            return True
        app.step_frame = _step

        async def _fast_sleep(_):
            return None

        with patch("scrollkit.app.base.sleep", _fast_sleep):
            asyncio.run(app._display_process())

        # Feeds happen BEFORE step_frame (a long frame gets the full budget),
        # so: laps 1-3 feed (errors 1-3), laps 4-6 starve (counter still >= MAX
        # when lap 6's feed decision is made; its SUCCESS resets the counter),
        # laps 7-8 feed again.
        assert calls["n"] == 8
        assert feeds["n"] == 3 + 2              # 3 pre-starvation + 2 post-recovery
        assert app.frames_rendered == 3         # only successful frames count
