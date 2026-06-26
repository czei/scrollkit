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
    palette_effects_for, RainbowChase, NeonTubeCrawl, ChromeSheen, HazardStripes, MonoChase,
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
    expected = {RainbowChase, NeonTubeCrawl, ChromeSheen, HazardStripes, MonoChase}
    assert set(palette_effects_for("scrolling")) == expected
    assert set(palette_effects_for("static")) == expected


def test_palette_effects_derive_shades_from_a_base_colour():
    """Chrome / Neon / Hazard / MonoChase build their shades from one base colour."""
    def written(effect):
        pal = {}
        effect.apply(pal)                 # fills palette indices 1..RAMP
        return list(pal.values())

    # ChromeSheen of pure red -> every shade is red-only (G and B are zero)
    assert all((c & 0x00FFFF) == 0 for c in written(ChromeSheen(0xFF0000)))
    # MonoChase of pure blue -> every shade is blue-only (R and G are zero)
    assert all((c & 0xFFFF00) == 0 for c in written(MonoChase(0x0000FF)))
    # NeonTubeCrawl: glow IS the colour, base is a dimmer version of the same hue
    neon = NeonTubeCrawl(0x00FF00)
    assert neon.glow == 0x00FF00
    assert 0 < neon.base < 0x00FF00 and (neon.base & 0xFF00FF) == 0
    # HazardStripes: accent colour on a dark ground; the two-colour form still works
    assert HazardStripes(0x00C0FF).a == 0x00C0FF
    assert HazardStripes(a=0x111111, b=0x222222).a == 0x111111   # back-compat
