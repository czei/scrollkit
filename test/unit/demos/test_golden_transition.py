"""The golden-reference transition is always hardware-feasible.

``demos/medium/golden_transition.py`` is the copy-me example for contributors and
AI agents. This pins that the reference itself passes the strict feasibility gate
(the real safety mechanism) and declares its FEASIBILITY budget on the class — so
the example can never drift into teaching something that wouldn't run on device.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import importlib.util

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import DisplayContent
from scrollkit.dev import run_headless

_DEMO_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                          "demos", "medium", "golden_transition.py")


def _load_demo():
    spec = importlib.util.spec_from_file_location("golden_transition_demo", _DEMO_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DEMO = _load_demo()


class _Loop(DisplayContent):
    """Drives GoldenWipe repeatedly between two labels so the run keeps advancing."""

    def __init__(self):
        super().__init__(duration=None, priority=2)
        self.label = "ALPHA"
        self.t = DEMO.GoldenWipe(duration_frames=7, cover_color=0x202020)
        self._started = False

    async def render(self, display):
        if not self._started:
            await self.t.start(display, self._swap)
            self._started = True
        await display.draw_text(self.label, 18, 20, 0xFFFFFF)
        await self.t.render(display)
        if self.t.is_complete:
            self.t = DEMO.GoldenWipe(duration_frames=7, cover_color=0x202020)
            await self.t.start(display, self._swap)

    def _swap(self):
        self.label = "BRAVO" if self.label == "ALPHA" else "ALPHA"

    @property
    def is_complete(self):
        return False


def _app():
    class _App(ScrollKitApp):
        def __init__(self):
            super().__init__(enable_web=False, update_interval=10)
            self._c = None

        async def create_display(self):
            from scrollkit.display.simulator import SimulatorDisplay
            return SimulatorDisplay(width=64, height=32)

        async def prepare_display_content(self):
            return self._c

        async def setup(self):
            self._c = _Loop()
    return _App()


def test_golden_transition_passes_strict_at_20fps():
    result = run_headless(_app(), frames=120, hardware=True, strict=True)
    assert result.errors == [], result.errors
    assert result.ok is True
    assert result.advanced is True


def test_golden_transition_declares_feasibility_on_the_class():
    feas = DEMO.GoldenWipe.FEASIBILITY
    assert feas["hardware_safe"] is True
    assert feas["allocates_per_frame"] is False
    assert feas["modeled_frame_ms"] <= 50.0
