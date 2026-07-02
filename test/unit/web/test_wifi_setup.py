"""Tests for the WiFi onboarding portal (web/wifi_setup.py).

Like the settings-server tests, these call the internal methods
(_render_form, _apply) directly and drive run() with a stub server, so
adafruit_httpserver does not need to be installed in the test environment.
The portal is the restored no-file-editing WiFi setup feature — the flow
must save credentials through the SettingsManager, never a code file.
"""
import asyncio

import pytest
from unittest.mock import MagicMock, patch

import scrollkit.web.wifi_setup as wifi_setup_mod
from scrollkit.config.settings_manager import SettingsManager
from scrollkit.network.wifi_manager import WiFiManager
from scrollkit.web.wifi_setup import WiFiSetupPortal, _bars


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_wm(tmp_path, saved=None):
    """Real WiFiManager in desktop dev mode over a sandboxed SettingsManager."""
    with patch.object(SettingsManager, "load_settings", return_value=saved or {}):
        sm = SettingsManager(str(tmp_path / "settings.json"))
    with patch("scrollkit.network.wifi_manager.load_credentials",
               return_value=("", "")):
        return WiFiManager(sm)


def _fake_request(form_dict):
    req = MagicMock()
    req.form_data = dict(form_dict)
    return req


class _StubServer:
    """Stands in for adafruit_httpserver.Server inside run()."""

    def __init__(self, portal, save_on_poll=None, form=None):
        self._portal = portal
        self._save_on_poll = save_on_poll
        self._form = form or {"ssid": "HomeNetwork", "password": "hunter2"}
        self.polls = 0
        self.started = False
        self.stopped = False

    def start(self, host, port):
        self.started = True

    def poll(self):
        self.polls += 1
        if self._save_on_poll is not None and self.polls == self._save_on_poll:
            self._portal._apply(_fake_request(self._form))

    def stop(self):
        self.stopped = True


def _wire_stub(portal, **stub_kwargs):
    stub = _StubServer(portal, **stub_kwargs)

    def _fake_build():
        portal._server = stub
        portal._host = "localhost"
        portal._server_url = "http://localhost:80/"

    portal._build_server = _fake_build
    return stub


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

class TestRenderForm:
    def test_lists_scanned_networks_with_bars(self, tmp_path):
        portal = WiFiSetupPortal(_make_wm(tmp_path))
        portal._networks = [{"ssid": "HomeNetwork", "rssi": -50},
                            {"ssid": "GuestWiFi", "rssi": -80}]
        html = portal._render_form()
        assert "HomeNetwork" in html
        assert "GuestWiFi" in html
        assert "4 bars" in html      # -50 dBm
        assert "1 bars" in html      # -80 dBm

    def test_always_offers_manual_ssid_and_password(self, tmp_path):
        portal = WiFiSetupPortal(_make_wm(tmp_path))
        portal._networks = []
        html = portal._render_form()
        assert 'name="ssid_manual"' in html
        assert 'type="password"' in html
        assert "<select" not in html   # nothing to select from

    def test_ssid_html_is_escaped(self, tmp_path):
        portal = WiFiSetupPortal(_make_wm(tmp_path))
        portal._networks = [{"ssid": '<script>"evil"</script>', "rssi": -60}]
        html = portal._render_form()
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_error_message_is_shown(self, tmp_path):
        portal = WiFiSetupPortal(_make_wm(tmp_path))
        portal.error = "Please choose or type a network name."
        assert "Please choose" in portal._render_form()

    def test_bars_scale(self):
        assert _bars(-40) == 4
        assert _bars(-60) == 3
        assert _bars(-70) == 2
        assert _bars(-90) == 1
        assert _bars("garbage") == 1


# ---------------------------------------------------------------------------
# Saving (POST /save)
# ---------------------------------------------------------------------------

class TestApply:
    def test_saves_credentials_to_settings_not_a_file(self, tmp_path):
        wm = _make_wm(tmp_path)
        portal = WiFiSetupPortal(wm)

        ok = portal._apply(_fake_request({"ssid": "HomeNetwork",
                                          "password": "hunter2"}))
        assert ok is True
        assert portal.saved is True
        assert portal.saved_ssid == "HomeNetwork"
        # Landed in the settings manager (what settings.json persists).
        assert wm.settings_manager.settings["wifi_ssid"] == "HomeNetwork"
        assert wm.settings_manager.settings["wifi_password"] == "hunter2"

    def test_manual_ssid_beats_dropdown(self, tmp_path):
        wm = _make_wm(tmp_path)
        portal = WiFiSetupPortal(wm)
        portal._apply(_fake_request({"ssid": "Dropdown",
                                     "ssid_manual": "HiddenNet",
                                     "password": "pw"}))
        assert portal.saved_ssid == "HiddenNet"
        assert wm.settings_manager.settings["wifi_ssid"] == "HiddenNet"

    def test_missing_ssid_is_rejected(self, tmp_path):
        wm = _make_wm(tmp_path)
        portal = WiFiSetupPortal(wm)
        ok = portal._apply(_fake_request({"password": "pw"}))
        assert ok is False
        assert portal.saved is False
        assert portal.error
        assert "wifi_ssid" not in wm.settings_manager.settings

    def test_values_are_url_decoded(self, tmp_path):
        wm = _make_wm(tmp_path)
        portal = WiFiSetupPortal(wm)
        portal._apply(_fake_request({"ssid": "My%20Net",
                                     "password": "p%40ss+word"}))
        assert wm.settings_manager.settings["wifi_ssid"] == "My Net"
        assert wm.settings_manager.settings["wifi_password"] == "p@ss word"

    def test_saved_credentials_survive_a_new_wifi_manager(self, tmp_path):
        """End-to-end promise: what the portal saves is what the next boot's
        WiFiManager connects with (settings beat secrets.py)."""
        wm = _make_wm(tmp_path)
        WiFiSetupPortal(wm)._apply(_fake_request({"ssid": "HomeNetwork",
                                                  "password": "hunter2"}))
        with patch("scrollkit.network.wifi_manager.load_credentials",
                   return_value=("StaleSecretsNet", "old")):
            reborn = WiFiManager(wm.settings_manager)
        assert reborn.ssid == "HomeNetwork"
        assert reborn.password == "hunter2"


# ---------------------------------------------------------------------------
# The run() loop (stub server; dev-mode WiFiManager)
# ---------------------------------------------------------------------------

class TestRunLoop:
    @pytest.mark.asyncio
    async def test_run_serves_until_saved_then_cleans_up(self, tmp_path,
                                                          monkeypatch):
        monkeypatch.setattr(wifi_setup_mod, "_LINGER_S", 0.01)
        monkeypatch.setattr(wifi_setup_mod, "_POLL_INTERVAL", 0.001)
        wm = _make_wm(tmp_path)
        portal = WiFiSetupPortal(wm)          # display=None: headless flow
        stub = _wire_stub(portal, save_on_poll=3)

        saved = await portal.run()

        assert saved is True
        assert stub.started and stub.stopped
        assert stub.polls >= 3
        assert wm.ap_enabled is False          # AP torn down afterwards
        assert wm.settings_manager.settings["wifi_ssid"] == "HomeNetwork"
        # Dev-mode scan primed the form with the mock networks.
        assert any(n["ssid"] == "HomeNetwork" for n in portal._networks)

    @pytest.mark.asyncio
    async def test_run_times_out_without_save(self, tmp_path, monkeypatch):
        monkeypatch.setattr(wifi_setup_mod, "_POLL_INTERVAL", 0.001)
        wm = _make_wm(tmp_path)
        portal = WiFiSetupPortal(wm)
        stub = _wire_stub(portal)              # never saves

        saved = await portal.run(timeout_s=0.05)

        assert saved is False
        assert stub.stopped
        assert wm.ap_enabled is False


# ---------------------------------------------------------------------------
# Panel instructions
# ---------------------------------------------------------------------------

class TestInstructions:
    def test_instructions_name_the_ap_and_url(self, tmp_path):
        wm = _make_wm(tmp_path)
        portal = WiFiSetupPortal(wm)
        text = portal._instructions()
        assert wm.AP_SSID in text
        assert wm.AP_PASSWORD in text
        assert "http://" in text

    def test_status_content_is_scrolling_text(self, tmp_path):
        from scrollkit.display.content import ScrollingText
        wm = _make_wm(tmp_path)
        portal = WiFiSetupPortal(wm, display=MagicMock())
        content = portal._make_status_content()
        assert isinstance(content, ScrollingText)
        assert wm.AP_SSID in content.text

    def test_no_display_means_no_status_content(self, tmp_path):
        portal = WiFiSetupPortal(_make_wm(tmp_path), display=None)
        assert portal._make_status_content() is None
