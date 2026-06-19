"""scrollkit.dev.validate() — structured pre-flight checks with concrete fixes.

These pin the contract an AI agent relies on: clean apps pass, and the common
mistakes (color name strings, out-of-range RGB, off-panel text/position, blank
or crashing renders) each produce a specific, actionable issue.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import StaticText, ScrollingText
from scrollkit.dev import validate, ValidationReport


def _mk_display():
    from scrollkit.display.simulator import SimulatorDisplay
    return SimulatorDisplay(width=64, height=32)


class _GoodApp(ScrollKitApp):
    def __init__(self):
        super().__init__(enable_web=False, update_interval=10)

    async def create_display(self):
        return _mk_display()

    async def setup(self):
        self.content_queue.add(ScrollingText("HELLO", y=12, color=0x00FF88))


class _StringColorApp(_GoodApp):
    async def setup(self):
        self.content_queue.add(StaticText("HI", x=2, y=12, color="red"))


class _BadGeometryApp(_GoodApp):
    async def setup(self):
        self.content_queue.add(
            StaticText("THIS IS WAY TOO LONG TO FIT", x=0, y=40, color=(300, 0, 0)))


class _EmptyApp(_GoodApp):
    async def setup(self):
        pass  # nothing added, default prepare_display_content -> None -> blank


class _BrokenSetupApp(_GoodApp):
    async def setup(self):
        raise RuntimeError("boom")


def _codes(report):
    return {i.code for i in report.issues}


def test_good_app_passes():
    report = validate(_GoodApp(), frames=20)
    assert isinstance(report, ValidationReport)
    assert report.ok is True
    assert report.errors == []


def test_color_name_string_is_an_error():
    report = validate(_StringColorApp(), frames=20)
    assert report.ok is False
    assert "color_string" in _codes(report)


def test_geometry_and_range_issues_are_flagged():
    report = validate(_BadGeometryApp(), frames=20)
    codes = _codes(report)
    assert "text_clipped" in codes
    assert "offscreen_y" in codes
    assert "color_out_of_range" in codes


def test_blank_render_is_an_error():
    report = validate(_EmptyApp(), frames=15)
    codes = _codes(report)
    assert "blank_render" in codes
    assert report.ok is False


def test_setup_crash_is_surfaced():
    report = validate(_BrokenSetupApp(), frames=10)
    assert report.ok is False
    assert "runtime_error" in _codes(report)


def test_static_only_mode_does_not_run():
    # run=False: static checks fire (string color) without a headless render,
    # so there is no RunResult and no hardware issues.
    report = validate(_StringColorApp(), run=False)
    assert report.run is None
    assert "color_string" in _codes(report)
    assert "hardware" not in _codes(report)


def test_as_dict_shape():
    d = validate(_GoodApp(), frames=15).as_dict()
    assert set(d.keys()) == {"ok", "counts", "issues"}
    assert set(d["counts"].keys()) == {"error", "warning", "info"}
    for issue in d["issues"]:
        assert set(issue.keys()) == {"severity", "code", "message", "fix"}
