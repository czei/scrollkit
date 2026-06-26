"""The one-call effect-selection API: per-category functions filtered by presentation.

`transitions_for`, `scrollers_for`, `palette_effects_for` each return the live set
for ONE category (kept separate, since they're applied differently), so an app/agent
calls one function instead of hand-filtering the catalog.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.effects.transitions import transitions_for
from scrollkit.effects.scrolling import scrollers_for, KineticMarquee, WaveRider, SplitFlap
from scrollkit.display.bitmap_text import (
    palette_effects_for, RainbowChase, NeonTubeCrawl, ChromeSheen, HazardStripes,
)


def test_transitions_for_returns_names_for_the_setting():
    names = transitions_for()                       # default 'fullscreen' = all
    assert "Iris Snap" in names and "Horizontal Wipe" in names
    assert len(names) == 13
    # transitions are full-screen swaps — never tagged scrolling/static
    assert transitions_for("scrolling") == ()
    assert transitions_for("static") == ()


def test_scrollers_for_filters_by_presentation_and_returns_classes():
    assert set(scrollers_for("scrolling")) == {KineticMarquee, WaveRider}
    assert scrollers_for("static") == (SplitFlap,)


def test_palette_effects_for_read_well_static_or_scrolling():
    expected = {RainbowChase, NeonTubeCrawl, ChromeSheen, HazardStripes}
    assert set(palette_effects_for("scrolling")) == expected
    assert set(palette_effects_for("static")) == expected
