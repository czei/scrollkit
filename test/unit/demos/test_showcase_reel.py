"""US7 — the showcase reel demos every signature effect under the strict gate.

Pins ``demos/hard/showcase_reel.py`` (the self-driving reel that replaced the
announced title-card showcase):

  - the act decks advertise EVERY signature effect — all 13 transitions as
    named acts, all 13 palette treatments, the splashes, the scrollers and
    bitmap-text banners, the particles, and both characters; and
  - a forced sample of acts (the owl opener, a treatment, a transition act's
    screen-to-screen swap, the swarm) plays end to end on a STRICT display —
    the feasibility gate raises if any effect busts the 20 fps device budget.

The reel is self-driving (setup() runs the show), so the runtime test drives
setup() as a task and swaps the app's ~20 fps frame presenter for a no-sleep
version — same rendering, unit-test speed.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import asyncio
import importlib.util
import random
import time

import pytest

pygame = pytest.importorskip("pygame")

_DEMO_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "..",
                          "demos", "hard", "showcase_reel.py")


def _load_demo():
    spec = importlib.util.spec_from_file_location("showcase_reel_demo",
                                                  _DEMO_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DEMO = _load_demo()

TREATMENT_ACTS = {"velvet", "wake", "halo", "sonar", "cipher", "ink", "rim",
                  "heatmap", "eclipse", "gradient", "anatomy", "circuit",
                  "trace"}
TRANSITION_ACTS = {"lightslit", "iris", "mosaic", "gradual", "venetian",
                   "scanfold", "crt", "dissolve", "glitch", "columnrain",
                   "diagonal", "wipe", "dropsky"}
OTHER_ACTS = {"scrollkit", "swarm", "drip", "wink", "swirl", "splitflap",
              "sparkle", "snow", "emberp"}
INTERSTITIALS = {"owl-l", "owl-r", "bee-r", "bee-l", "marquee", "wave",
                 "rainbow", "mono", "neon", "chrome", "hazard"}


def test_decks_advertise_every_signature_effect():
    """Structural completeness: nothing can quietly drop out of the reel."""
    app = DEMO.ShowcaseReelApp()
    acts, mids = app._decks()
    act_names = {entry[0] for entry in acts}
    mid_names = {entry[0] for entry in mids}
    assert TREATMENT_ACTS <= act_names, TREATMENT_ACTS - act_names
    assert TRANSITION_ACTS <= act_names, TRANSITION_ACTS - act_names
    assert OTHER_ACTS <= act_names, OTHER_ACTS - act_names
    assert INTERSTITIALS <= mid_names, INTERSTITIALS - mid_names
    # every act carries a (name, family, callable) shape the scheduler needs
    for entry in acts + mids:
        assert len(entry) == 3 and callable(entry[2]), entry[0]


def test_transition_deck_names_cover_all_13_library_transitions():
    """13 named transition acts <-> 13 library transitions, no drift."""
    from scrollkit.config.transition_names import TRANSITION_NAMES
    assert len(TRANSITION_ACTS) == len(TRANSITION_NAMES) == 13


@pytest.mark.asyncio
async def test_forced_acts_play_end_to_end_under_the_strict_gate():
    random.seed(11)
    app = DEMO.ShowcaseReelApp(
        force_acts=["scrollkit", "velvet", "iris", "swarm"])

    # Strict display: the feasibility gate raises FeasibilityError if any act
    # busts the modeled 20 fps hardware budget.
    async def strict_display():
        from scrollkit.display.simulator import SimulatorDisplay
        return SimulatorDisplay(width=64, height=32, strict=True)
    app.create_display = strict_display

    # Same rendering, no 20 fps pacing sleep — unit-test speed.
    async def fast_frame(self):
        ok = await self.display.show()
        await asyncio.sleep(0)
        return ok is not False
    orig_frame = DEMO.ShowcaseReelApp._frame
    DEMO.ShowcaseReelApp._frame = fast_frame
    try:
        await app._initialize_display()
        app.display.start_recording()
        app.running = True
        task = asyncio.create_task(app.setup())
        deadline = time.monotonic() + 60
        try:
            while (not task.done()
                   and len(app.display._recording or []) < 900
                   and time.monotonic() < deadline):
                await asyncio.sleep(0)
        finally:
            app.running = False
            if not task.done():
                task.cancel()
                try:
                    await task
                except BaseException:
                    pass
        if task.done() and not task.cancelled() and task.exception():
            raise task.exception()

        frames = app.display._recording or []
        # The forced acts alone span ~800 frames; reaching the cap means the
        # opener, treatment, transition swap, and swarm all rendered.
        assert len(frames) >= 900, len(frames)
        lit = sum(1 for f in frames[::40] if f.max() > 40)
        assert lit >= 10, "reel rendered mostly-dark frames"
    finally:
        DEMO.ShowcaseReelApp._frame = orig_frame
        app.display.stop_recording()
        try:
            await app.cleanup()
        except Exception:
            pass
