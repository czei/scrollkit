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
async def test_set_brightness_via_display_not_hardware(monkeypatch):
    d = _make_hw_display(monkeypatch)
    await d.set_brightness(0.7)
    assert d.display.brightness == pytest.approx(0.7)


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
    assert disp.display.brightness == pytest.approx(
        float(app.settings.get("brightness_scale", 0.5))
    )
