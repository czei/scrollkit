"""US7 — the showcase reel runs strict end-to-end and demos every signature effect.

Loads the actual ``demos/hard/showcase.py`` reel and verifies:
  - it visits ALL 14 announced scenes (3 scrollers + 7 transitions + 4 palette
    effects), and
  - it cleans up its effect layers between scenes (no layer leak), and
  - a full pass passes the strict feasibility gate at 20 fps end to end.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import importlib.util

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.app.base import ScrollKitApp
from scrollkit.dev import run_headless

_DEMO_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                          "demos", "hard", "showcase.py")


def _load_demo():
    spec = importlib.util.spec_from_file_location("showcase_demo", _DEMO_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DEMO = _load_demo()

# Enough frames to complete one full pass through every scene (and wrap), measured
# from the reel pacing — so every scene boundary (layer attach/detach + the strict
# gate) is exercised, not just the first few.
FULL_PASS_FRAMES = 2300


def _reel_app():
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
            self._c = DEMO.ShowcaseReel()
    return _App()


def test_reel_runs_strict_end_to_end():
    result = run_headless(_reel_app(), frames=FULL_PASS_FRAMES,
                          hardware=True, strict=True)
    assert result.errors == [], result.errors
    assert result.ok is True
    assert result.advanced is True


@pytest.mark.asyncio
async def test_reel_visits_all_scenes_without_leaking_layers():
    from scrollkit.display.simulator import SimulatorDisplay
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    reel = DEMO.ShowcaseReel()
    n_scenes = len(reel.SCENES)
    visited = set()
    peak_layers = 0
    for _ in range(FULL_PASS_FRAMES):
        await d.clear()
        await reel.render(d)
        await d.show()
        visited.add(reel._i)
        peak_layers = max(peak_layers, len(d._layer_group))
        if len(visited) == n_scenes:
            break
    # Every announced scene was reached...
    assert visited == set(range(n_scenes)), visited
    # ...and effect layers are detached between scenes — at most the single
    # persistent (transparent) paint canvas plus one active effect layer remains.
    assert peak_layers <= 2, peak_layers


def test_reel_advertises_every_signature_effect():
    # The reel must chain all three classes + the foundation, announced by name.
    labels = [s.LABEL for s in DEMO.ShowcaseReel().SCENES]
    for expected in ["MARQUEE", "WAVERIDER", "SPLITFLAP",
                     "IRIS", "VENETIAN", "MOSAIC", "CRT FOLD", "LIGHTSLIT",
                     "RAIN", "DROP IN",
                     "RAINBOW", "NEON TUBE", "CHROME", "HAZARD"]:
        assert expected in labels, expected
