"""US1 removal contract: the broken transition effects are gone.

Asserts every FR-001 removed name is unimportable from its old module, absent
from ``scrollkit.effects.__all__``, and absent from the ``capabilities()``
catalog. Retained items (``EffectsEngine.get_rainbow_color``, particles) are
spot-checked so the removal didn't take them with it.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import importlib

import pytest

import scrollkit.effects as fx

# Files deleted outright. NOTE: effects/transitions.py was deleted in Phase 1 and a
# brand-new, unrelated transitions.py (the Class 2 Transition base + IrisSnap) was
# created in Phase 3 — so the *module* exists again but must not carry the old
# broken classes (asserted separately below).
REMOVED_MODULES = [
    "scrollkit.effects.reveal",
    "scrollkit.effects.basic_transitions",
]

OLD_TRANSITION_CLASSES = (
    "TransitionEngine", "BaseTransition", "FadeTransition", "WipeTransition",
    "SlideTransition",
)

# Every FR-001 name. NOTE: ``PulseEffect`` here is the broken duplicate that
# lived in ``basic_transitions``; the retained ``PulseEffect(SimpleEffect)`` in
# ``effects.effects`` is intentionally NOT exported and not part of this list's
# package-namespace check.
REMOVED_NAMES = [
    "TransitionEngine", "BaseTransition", "FadeTransition", "WipeTransition",
    "SlideTransition", "RevealEffect", "RevealCenterEffect", "FadeInEffect",
    "SlideInEffect", "WipeEffect", "FlashEffect", "PulseEffect",
]


@pytest.mark.parametrize("modname", REMOVED_MODULES)
def test_removed_module_is_gone(modname):
    with pytest.raises(ImportError):
        importlib.import_module(modname)


@pytest.mark.parametrize("name", REMOVED_NAMES)
def test_removed_name_not_exported(name):
    assert name not in (fx.__all__ or [])
    with pytest.raises(AttributeError):
        getattr(fx, name)


def test_removed_names_absent_from_capabilities():
    pytest.importorskip("pygame")
    from scrollkit.dev import capabilities
    names = {e["name"] for e in capabilities()["effects"]}
    for name in REMOVED_NAMES:
        assert name not in names, "still in catalog: %s" % name


def test_fresh_transitions_module_lacks_the_old_broken_classes():
    import scrollkit.effects.transitions as tr
    for name in OLD_TRANSITION_CLASSES:
        assert not hasattr(tr, name), "old class survived in new module: %s" % name
    # the fresh module ships the replacement Class 2 base + the IrisSnap spike
    assert hasattr(tr, "Transition") and hasattr(tr, "IrisSnap")


def test_retained_items_still_work():
    from scrollkit.effects.effects import EffectsEngine
    from scrollkit.effects.particles import (  # noqa: F401
        ParticleEngine, Sparkle, Snow, RainDrop, Ember)
    assert hasattr(EffectsEngine, "get_rainbow_color")
