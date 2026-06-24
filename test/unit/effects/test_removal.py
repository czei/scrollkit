"""US1 removal contract: the broken transition effects are gone.

Asserts every FR-001 removed name is unimportable from its old module, absent
from ``scrollkit.effects.__all__``, and absent from the ``capabilities()``
catalog. Retained items (the standalone particle system) are spot-checked so the
removal didn't take them with it.
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
    # Effects-consolidation removals: the dead Effect/EffectRegistry stack, the
    # SimpleEffect/EffectsEngine system, and the orphaned enhanced-content family.
    "scrollkit.effects.base",
    "scrollkit.effects.effects",
    "scrollkit.display.enhanced_content",
]

OLD_TRANSITION_CLASSES = (
    "TransitionEngine", "BaseTransition", "FadeTransition", "WipeTransition",
    "SlideTransition",
)

# Every removed name: the original FR-001 batch (broken transitions/effects) plus
# the effects-consolidation removals (the Effect ABC + registry, the
# SimpleEffect/EffectsEngine system, and the concrete SimpleEffects). Since
# ``effects.effects`` is now deleted, the formerly-retained ``PulseEffect`` is gone
# too — all of these must be absent from the package namespace and the catalog.
REMOVED_NAMES = [
    "TransitionEngine", "BaseTransition", "FadeTransition", "WipeTransition",
    "SlideTransition", "RevealEffect", "RevealCenterEffect", "FadeInEffect",
    "SlideInEffect", "WipeEffect", "FlashEffect", "PulseEffect",
    # effects-consolidation removals
    "EffectsEngine", "Effect", "CompositeEffect", "SimpleEffect",
    "SparkleEffect", "EdgeGlowEffect", "RainbowCycleEffect", "CornerFlashEffect",
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


def test_effect_attachment_api_is_removed():
    """WS1 Tier 2: the dead Effect.apply attachment surface is gone.

    It drove a contract (``Effect.apply``) that no longer exists, was a no-op in
    practice, and a trap for AI-authored code that called it expecting effects.
    """
    from scrollkit.display.strategy import DisplayItem
    from scrollkit.content_classes import BaseContent
    item = DisplayItem("text", {})
    for attr in ("effects", "add_effect", "with_effect"):
        assert not hasattr(item, attr), "DisplayItem still has %s" % attr
    for attr in ("with_effect", "with_effects"):
        assert not hasattr(BaseContent, attr), "BaseContent still has %s" % attr


def test_retained_items_still_work():
    # The standalone particle system is orthogonal to the removed effect systems
    # and must survive the consolidation.
    from scrollkit.effects.particles import (  # noqa: F401
        ParticleEngine, Sparkle, Snow, RainDrop, Ember)
    import scrollkit.effects.particles as p
    assert hasattr(p, "ParticleEngine")
