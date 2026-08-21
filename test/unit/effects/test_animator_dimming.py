# Copyright (c) 2024-2026 Michael Czeiszperger
"""Icon animators honour the global software brightness.

The icon is the one thing on the panel that is NOT drawn through draw_text, so
it needs its own path. The rule everywhere here: ``base_colors`` stays RAW (the
true art) and every write scales it. Pre-dimming the base instead would
double-dim CoverAnimator, which builds its overlay colours *from* base_colors
and passes them through the same _make_overlay that dims.
"""
import pytest

from scrollkit.effects.image_animators import PalettePulseAnimator


class _Pal:
    def __init__(self, n):
        self.v = [0] * n

    def __len__(self):
        return len(self.v)

    def __getitem__(self, i):
        return self.v[i]

    def __setitem__(self, i, c):
        self.v[i] = c

    def make_transparent(self, i):
        pass


class _Display:
    def __init__(self, scale):
        self.color_scale = scale
        self.width = 64
        self.height = 32


BASE = [0x000000, 0xFF0000, 0x00FF00, 0x0000FF]


def _started(scale, **kw):
    a = PalettePulseAnimator(match=(0xFF0000,), **kw)
    pal = _Pal(len(BASE))
    a.start(_Display(scale), tile=None, bitmap=None, palette=pal, base_colors=list(BASE))
    return a, pal


def test_pulse_compounds_with_the_dim_instead_of_fighting_it():
    """The pulse rewrites its matched entries every frame from base_colors, so
    a dim applied to the palette alone would be gone within a frame."""
    full, pal_full = _started(1.0)
    dim, pal_dim = _started(0.5)
    full.step(0)
    dim.step(0)
    assert pal_dim[1] < pal_full[1], "pulsing entry must be dimmer"
    # Same phase, so the ratio is the dim itself.
    assert ((pal_dim[1] >> 16) & 0xFF) == pytest.approx(((pal_full[1] >> 16) & 0xFF) * 0.5,
                                                        abs=2)


def test_detach_restores_to_the_DIMMED_base_not_the_raw_one():
    """detach() restores so the intro fade starts clean. Restoring the raw base
    while the rest of the panel is dimmed is a visible bright flash at the
    hold->fade handoff."""
    a, pal = _started(0.5)
    a.step(0)
    a.detach()
    assert pal[1] != BASE[1], "restored the RAW colour: bright flash at handoff"
    assert ((pal[1] >> 16) & 0xFF) == pytest.approx(0xFF * 0.5, abs=2)


def test_full_brightness_restores_exactly():
    a, pal = _started(1.0)
    a.step(0)
    a.detach()
    assert pal[1] == BASE[1]


def test_base_colors_are_never_mutated():
    """Everything downstream (the fade, the cloned palettes, Cover) reads this
    list. Dimming it in place would compound on every re-read."""
    a, _pal = _started(0.4)
    a.step(0)
    a.detach()
    assert a.base_colors == BASE
