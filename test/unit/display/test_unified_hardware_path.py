"""Regression tests for the CircuitPython hardware handles in UnifiedDisplay.

The Interstate 75 board path stores a raw ``rgbmatrix.RGBMatrix`` as
``display.hardware`` — it has NO ``.display`` attribute (only the MatrixPortal
S3's ``Matrix`` wrapper happens to have one). show(), set_brightness() and
SLDKApp._apply_library_settings() must therefore reach the displayio display
via ``self.display`` only. Reaching through ``self.hardware.display`` raised
AttributeError every frame (swallowed by the display loop's broad except), and
with auto_refresh=False the Interstate 75 panel never refreshed at all.
"""
from types import SimpleNamespace

import pytest

from scrollkit.app.base import SLDKApp
from scrollkit.display import unified as unified_mod
from scrollkit.display.unified import UnifiedDisplay


class _FakeDisplayioDisplay:
    """Stands in for the board's displayio display (has refresh + brightness)."""

    def __init__(self):
        self.refresh_calls = []
        self.brightness = None

    def refresh(self, **kwargs):
        self.refresh_calls.append(kwargs)


class _RawRGBMatrix:
    """Stand-in for rgbmatrix.RGBMatrix: deliberately has no .display."""


def _make_hw_display(monkeypatch):
    monkeypatch.setattr(unified_mod, "IS_CIRCUITPYTHON", True)
    d = UnifiedDisplay(width=64, height=32)
    d.display = _FakeDisplayioDisplay()
    d.hardware = _RawRGBMatrix()
    d.matrix = d.hardware
    return d


@pytest.mark.asyncio
async def test_show_refreshes_via_display_not_hardware(monkeypatch):
    d = _make_hw_display(monkeypatch)
    ok = await d.show()
    assert ok is True
    assert d.display.refresh_calls == [{"minimum_frames_per_second": 0}]


@pytest.mark.asyncio
async def test_set_brightness_dims_in_software_and_pins_the_panel(monkeypatch):
    """The hardware property is NOT a dimmer.

    On the MatrixPortal S3 ``display.brightness`` is effectively on/off: 0.0
    blanks the panel and everything above it looks the same. A customer's sign
    sat dark for months on a stored "0" because of it. So brightness is now a
    software colour scale and the panel is pinned to FULL.
    """
    d = _make_hw_display(monkeypatch)
    await d.set_brightness(0.7)
    assert d.color_scale == pytest.approx(0.7)      # the dim lives here now
    assert d.display.brightness == 1.0              # ...and the panel stays full


@pytest.mark.asyncio
async def test_hardware_brightness_is_pinned_at_every_setting(monkeypatch):
    """The pin is the invariant that protects users from a full-bright panel if
    the scale ever fails to reach a colour path — and from a black one at 0."""
    d = _make_hw_display(monkeypatch)
    for f in (0.0, 0.15, 0.5, 1.0):
        await d.set_brightness(f)
        assert d.display.brightness == 1.0, f


@pytest.mark.asyncio
async def test_set_color_scale_clears_the_paint_index_cache(monkeypatch):
    """Paint palette entries hold DIMMED values, so a new scale makes every
    cached colour->index mapping stale."""
    d = _make_hw_display(monkeypatch)
    d._paint_colors = {0xFF0000: 1}
    d.set_color_scale(0.4)
    assert d._paint_colors == {}


def test_apply_library_settings_brightness_with_raw_matrix_hardware():
    """Brightness from a web-settings save must land on .display even when
    .hardware is a raw matrix (the Interstate 75 case)."""
    app = SLDKApp(enable_web=False)
    disp = SimpleNamespace(
        _brightness=0.3,
        hardware=_RawRGBMatrix(),
        display=_FakeDisplayioDisplay(),
    )
    app.display = disp
    app._apply_library_settings()
    # A display without set_color_scale (an older library build) keeps the old
    # behaviour rather than silently ignoring the setting.
    assert disp.display.brightness == pytest.approx(
        float(app.settings.get("brightness_scale", 0.5))
    )


def test_apply_library_settings_prefers_the_software_scale():
    """With a modern display, the setting becomes a colour scale and the panel
    is pinned — the reverse of the old behaviour."""
    from scrollkit.display.unified import UnifiedDisplay
    app = SLDKApp(enable_web=False)
    d = UnifiedDisplay(width=64, height=32)
    d.display = _FakeDisplayioDisplay()
    app.display = d
    app.settings.set("brightness_scale", "0.4")
    app._apply_library_settings()
    assert d.color_scale == pytest.approx(0.4)
    assert d.display.brightness == 1.0


def test_apply_library_settings_respects_the_app_floor():
    """A stored 0 must not reach the display. The library floor is 0.0 (no
    product policy); an app overrides MIN_BRIGHTNESS to keep its panel
    readable, and the live/preview path has to honour it too -- not just boot."""
    from scrollkit.display.unified import UnifiedDisplay

    class _FlooredApp(SLDKApp):
        MIN_BRIGHTNESS = 0.15

    app = _FlooredApp(enable_web=False)
    d = UnifiedDisplay(width=64, height=32)
    d.display = _FakeDisplayioDisplay()
    app.display = d
    app.settings.set("brightness_scale", "0")
    app._apply_library_settings()
    assert d.color_scale == pytest.approx(0.15)
