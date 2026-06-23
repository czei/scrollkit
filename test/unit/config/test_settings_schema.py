"""Tests for SettingsManager.define() and the _schema list."""
import pytest
from unittest.mock import patch

from scrollkit.config.settings_manager import SettingsManager


def _make(**kwargs):
    """Return a fresh SettingsManager with load_settings mocked."""
    with patch.object(SettingsManager, "load_settings", return_value={}):
        return SettingsManager("test.json", **kwargs)


class TestDefine:
    def test_define_registers_default(self):
        sm = _make()
        sm.define("x", 42)
        assert sm.get("x") == 42

    def test_define_preserves_saved_value(self):
        with patch.object(SettingsManager, "load_settings", return_value={"x": 99}):
            sm = SettingsManager("test.json")
        sm.define("x", 42)
        assert sm.get("x") == 99

    def test_define_infers_text_type(self):
        sm = _make()
        sm.define("greeting", "hello")
        entry = next(e for e in sm._schema if e["key"] == "greeting")
        assert entry["type"] == "text"

    def test_define_infers_bool_type(self):
        sm = _make()
        sm.define("flag", True)
        entry = next(e for e in sm._schema if e["key"] == "flag")
        assert entry["type"] == "checkbox"

    def test_define_bool_not_number(self):
        """bool subclasses int — ensure it maps to 'checkbox', not 'number'."""
        sm = _make()
        sm.define("active", False)
        entry = next(e for e in sm._schema if e["key"] == "active")
        assert entry["type"] == "checkbox"

    def test_define_infers_number_type_int(self):
        sm = _make()
        sm.define("count", 5)
        entry = next(e for e in sm._schema if e["key"] == "count")
        assert entry["type"] == "number"

    def test_define_infers_number_type_float(self):
        sm = _make()
        sm.define("scale", 1.5)
        entry = next(e for e in sm._schema if e["key"] == "scale")
        assert entry["type"] == "number"

    def test_define_infers_select_type(self):
        sm = _make()
        sm.define("speed", "Medium", options=["Slow", "Medium", "Fast"])
        entry = next(e for e in sm._schema if e["key"] == "speed")
        assert entry["type"] == "select"
        assert entry["options"] == ["Slow", "Medium", "Fast"]

    def test_define_infers_range_type_min(self):
        sm = _make()
        sm.define("vol", 50, min=0, max=100)
        entry = next(e for e in sm._schema if e["key"] == "vol")
        assert entry["type"] == "range"

    def test_define_explicit_color_type(self):
        sm = _make()
        sm.define("bg", 0xFF0000, type="color")
        entry = next(e for e in sm._schema if e["key"] == "bg")
        assert entry["type"] == "color"

    def test_define_explicit_type_overrides_inference(self):
        sm = _make()
        sm.define("num", 0, type="text")
        entry = next(e for e in sm._schema if e["key"] == "num")
        assert entry["type"] == "text"

    def test_define_default_label(self):
        sm = _make()
        sm.define("scroll_speed", "Medium", options=["Slow", "Medium", "Fast"])
        entry = next(e for e in sm._schema if e["key"] == "scroll_speed")
        assert entry["label"] == "Scroll Speed"

    def test_define_explicit_label(self):
        sm = _make()
        sm.define("x", 1, label="My Label")
        entry = next(e for e in sm._schema if e["key"] == "x")
        assert entry["label"] == "My Label"

    def test_define_schema_order(self):
        sm = _make()
        sm.define("a", 1)
        sm.define("b", 2)
        sm.define("c", 3)
        keys = [e["key"] for e in sm._schema if e["key"] in ("a", "b", "c")]
        assert keys == ["a", "b", "c"]

    def test_define_bool_auto_bool_key(self):
        sm = _make()
        sm.define("notifications", True)
        assert "notifications" in sm._bool_keys

    def test_base_library_defaults_in_schema(self):
        sm = _make()
        keys = [e["key"] for e in sm._schema]
        assert "brightness_scale" in keys
        assert "scroll_speed" in keys
        assert "default_color" in keys

    def test_brightness_schema_is_range(self):
        sm = _make()
        entry = next(e for e in sm._schema if e["key"] == "brightness_scale")
        assert entry["type"] == "range"
        assert entry["min"] == 0.0
        assert entry["max"] == 1.0

    def test_scroll_speed_schema_is_select(self):
        sm = _make()
        entry = next(e for e in sm._schema if e["key"] == "scroll_speed")
        assert entry["type"] == "select"
        assert "Slow" in entry["options"]
