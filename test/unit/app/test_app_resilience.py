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
                app.note_refresh_result(False, reason="oserror")  # 1
                assert not reset.called
                app.note_refresh_result(False, reason="oserror")  # 2
                assert not reset.called
                app.note_refresh_result(False, reason="oserror")  # 3 -> reboot
        assert reset.call_count == 1
        # The cause is persisted to NVM before resetting (diagnosable post-reboot).
        assert diag_open.return_value.record_crash.called
        recorded = diag_open.return_value.record_crash.call_args[0][0]
        assert "oserror" in recorded
        assert "consecutive refresh failures" in recorded

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
