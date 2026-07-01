"""Tests for SettingsWebServer — form rendering and POST apply logic.

These tests call internal methods (_render_form, _apply) directly so that
adafruit_httpserver does not need to be installed in the test environment.
"""
import sys
import types
import pytest
from unittest.mock import patch, MagicMock, call

from scrollkit.config.settings_manager import SettingsManager
from scrollkit.web.settings_server import SettingsWebServer, _color_to_html


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_sm(saved=None):
    """Fresh SettingsManager with controlled on-disk state."""
    with patch.object(SettingsManager, "load_settings", return_value=saved or {}):
        sm = SettingsManager("test.json")
    return sm


def _make_server(sm=None, app=None):
    if sm is None:
        sm = _make_sm()
    return SettingsWebServer(sm, app=app, host="localhost", port=8080)


def _fake_request(form_dict):
    """Build a minimal fake request whose form_data behaves like a dict."""
    req = MagicMock()
    fd = dict(form_dict)  # plain dict: supports .keys(), .get(), 'key in fd'
    req.form_data = fd
    return req


# ---------------------------------------------------------------------------
# _color_to_html helper
# ---------------------------------------------------------------------------

class TestColorToHtml:
    def test_int_to_hex(self):
        assert _color_to_html(0xFF0000) == "#ff0000"

    def test_zero_black(self):
        assert _color_to_html(0) == "#000000"

    def test_white(self):
        assert _color_to_html(0xFFFFFF) == "#ffffff"

    def test_hash_passthrough(self):
        assert _color_to_html("#aabbcc") == "#aabbcc"

    def test_0x_string(self):
        assert _color_to_html("0xFF0000") == "#ff0000"


# ---------------------------------------------------------------------------
# _render_form
# ---------------------------------------------------------------------------

class TestRenderForm:
    def test_render_contains_field_label(self):
        sm = _make_sm()
        sm.define("message", "hi", label="My Message")
        srv = _make_server(sm)
        html = srv._render_form()
        assert "My Message" in html

    def test_render_text_field_contains_value(self):
        sm = _make_sm()
        sm.define("message", "hello world")
        srv = _make_server(sm)
        html = srv._render_form()
        assert "hello world" in html

    def test_render_color_int_to_html(self):
        sm = _make_sm()
        sm.define("bg", 0xFF0000, type="color")
        srv = _make_server(sm)
        html = srv._render_form()
        assert "#ff0000" in html

    def test_render_select_marks_current(self):
        sm = _make_sm()
        sm.define("speed", "Fast", options=["Slow", "Medium", "Fast"])
        srv = _make_server(sm)
        html = srv._render_form()
        assert "<option selected>Fast</option>" in html

    def test_render_checkbox_checked_when_true(self):
        sm = _make_sm()
        sm.define("alerts", True)
        # force the value to True so it renders as checked
        sm.set("alerts", True)
        srv = _make_server(sm)
        html = srv._render_form()
        assert "checked" in html

    def test_render_checkbox_not_checked_when_false(self):
        sm = _make_sm()
        sm.define("alerts", False)
        sm.set("alerts", False)
        srv = _make_server(sm)
        html = srv._render_form()
        # <input type="checkbox" name="alerts" value="1"> without "checked"
        assert 'name="alerts"' in html
        # Should not have "checked" attribute on this particular checkbox
        # (The base settings have no checkboxes so this is the only one)
        assert " checked" not in html

    def test_render_range_contains_min_max(self):
        sm = _make_sm()
        sm.define("vol", 50, min=0, max=100, step=1)
        srv = _make_server(sm)
        html = srv._render_form()
        assert 'min="0"' in html
        assert 'max="100"' in html

    def test_render_has_save_button(self):
        sm = _make_sm()
        srv = _make_server(sm)
        html = srv._render_form()
        assert "<button" in html
        assert "Save" in html

    def test_render_escapes_html_in_value(self):
        sm = _make_sm()
        sm.define("msg", '<script>alert(1)</script>')
        sm.set("msg", '<script>alert(1)</script>')
        srv = _make_server(sm)
        html = srv._render_form()
        assert "<script>" not in html
        assert "&lt;script&gt;" in html


# ---------------------------------------------------------------------------
# _apply
# ---------------------------------------------------------------------------

class TestApply:
    def test_apply_text_field(self):
        sm = _make_sm()
        sm.define("message", "old")
        srv = _make_server(sm)
        req = _fake_request({"message": "new text"})
        with patch.object(sm, "save_settings"):
            srv._apply(req, sm, None)
        assert sm.get("message") == "new text"

    def test_apply_color_field(self):
        sm = _make_sm()
        sm.define("bg", 0x000000, type="color")
        srv = _make_server(sm)
        req = _fake_request({"bg": "#ff0000"})
        with patch.object(sm, "save_settings"):
            srv._apply(req, sm, None)
        assert sm.get("bg") == 0xFF0000

    def test_apply_range_float(self):
        sm = _make_sm()
        srv = _make_server(sm)
        # brightness_scale default is 0.5 (float) -> stored as float
        req = _fake_request({"brightness_scale": "0.75",
                             "scroll_speed": "Medium",
                             "default_color": "#ffffff"})
        with patch.object(sm, "save_settings"):
            srv._apply(req, sm, None)
        assert sm.get("brightness_scale") == pytest.approx(0.75)

    def test_apply_select_field(self):
        sm = _make_sm()
        srv = _make_server(sm)
        req = _fake_request({"brightness_scale": "0.5",
                             "scroll_speed": "Fast",
                             "default_color": "#ffffff"})
        with patch.object(sm, "save_settings"):
            srv._apply(req, sm, None)
        assert sm.get("scroll_speed") == "Fast"

    def test_apply_checkbox_absent_is_false(self):
        sm = _make_sm()
        sm.define("alerts", True)
        sm.set("alerts", True)
        srv = _make_server(sm)
        # "alerts" absent from form -> False
        req = _fake_request({})
        with patch.object(sm, "save_settings"):
            srv._apply(req, sm, None)
        assert sm.get("alerts") is False

    def test_apply_checkbox_present_is_true(self):
        sm = _make_sm()
        sm.define("alerts", False)
        sm.set("alerts", False)
        srv = _make_server(sm)
        req = _fake_request({"alerts": "1"})
        with patch.object(sm, "save_settings"):
            srv._apply(req, sm, None)
        assert sm.get("alerts") is True

    def test_apply_calls_save_settings(self):
        sm = _make_sm()
        srv = _make_server(sm)
        req = _fake_request({})
        with patch.object(sm, "save_settings") as mock_save:
            srv._apply(req, sm, None)
        mock_save.assert_called_once()

    def test_apply_calls_notify_settings_changed(self):
        """The web server flags the main loop rather than applying settings itself."""
        sm = _make_sm()
        app = MagicMock()
        srv = _make_server(sm, app=app)
        req = _fake_request({})
        with patch.object(sm, "save_settings"):
            srv._apply(req, sm, app)
        app.notify_settings_changed.assert_called_once()
        app.on_settings_changed.assert_not_called()
        app._apply_library_settings.assert_not_called()

    def test_apply_survives_bad_notify(self):
        sm = _make_sm()
        app = MagicMock()
        app.notify_settings_changed.side_effect = RuntimeError("boom")
        srv = _make_server(sm, app=app)
        req = _fake_request({})
        with patch.object(sm, "save_settings"):
            with pytest.raises(RuntimeError):
                srv._apply(req, sm, app)

    def test_apply_ignores_unknown_field(self):
        sm = _make_sm()
        srv = _make_server(sm)
        req = _fake_request({"nonexistent_key": "value"})
        with patch.object(sm, "save_settings"):
            srv._apply(req, sm, None)  # must not raise


# ---------------------------------------------------------------------------
# base.py integration: create_web_server returns SettingsWebServer by default
# ---------------------------------------------------------------------------

class TestBaseIntegration:
    @pytest.mark.asyncio
    async def test_server_created_by_default(self):
        from scrollkit.app.base import ScrollKitApp

        with patch.object(SettingsManager, "load_settings", return_value={}):
            app = ScrollKitApp()

        server = await app.create_web_server()
        assert isinstance(server, SettingsWebServer)

    def test_on_settings_changed_noop(self):
        from scrollkit.app.base import ScrollKitApp

        with patch.object(SettingsManager, "load_settings", return_value={}):
            app = ScrollKitApp()

        app.on_settings_changed()  # must not raise and must return None
