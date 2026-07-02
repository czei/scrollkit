"""Removal contract: dead/legacy APIs stay gone.

Covers two eras of cleanup:

1. The original effects-consolidation removal (the broken transition engine,
   the Effect ABC/EffectRegistry stack, the SimpleEffect/EffectsEngine system).
2. The 0.8.2 legacy-cleanup release: the pre-consolidation display pipeline
   (content_classes -> display.strategy -> display.queue -> display.manager),
   MinimalLEDApp, the OTA server/updater duplicates, and other zero-importer
   orphans (see the ScrollKit 0.8.2 design audit).

Asserts every removed name is unimportable from its old module, absent from
``scrollkit.effects.__all__``, and absent from the ``capabilities()`` catalog.
Retained items (the standalone particle system) are spot-checked so the
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
    # Already gone before the 0.8.2 cleanup — pinned so it never comes back.
    "scrollkit.display.display_factory",
    # 0.8.2 legacy cleanup: the dead pre-consolidation display pipeline. Only
    # Priority survived (relocated to scrollkit.display.content).
    "scrollkit.content_classes",
    "scrollkit.content",
    "scrollkit.display.strategy",
    "scrollkit.display.queue",
    "scrollkit.display.manager",
    # 0.8.2 legacy cleanup: MinimalLEDApp (disjoint from ScrollKitApp, nothing
    # built on it) and its broken desktop fallback.
    "scrollkit.app.minimal",
    # 0.8.2 legacy cleanup: OTA producer/consumer duplicates, unused by the
    # library, tests, demos, or the shipping app.
    "scrollkit.ota.updater",
    "scrollkit.ota.server",
    # 0.8.2 legacy cleanup: zero-importer utility/simulator orphans.
    "scrollkit.utils.timer",
    "scrollkit.utils.image_processor",
    "scrollkit.simulator.devices.generic_matrix",
    "scrollkit.simulator.adafruit_display_text.bitmap_label",
    "scrollkit.simulator.terminalio.font_scaler",
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
    # effects/__init__.py is import-free (0.8.2) and carries no __all__ at all.
    assert name not in (getattr(fx, "__all__", None) or [])
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
    # The standalone particle system is orthogonal to the removed effect systems
    # and must survive the consolidation.
    from scrollkit.effects.particles import (  # noqa: F401
        ParticleEngine, Sparkle, Snow, RainDrop, Ember)
    import scrollkit.effects.particles as p
    assert hasattr(p, "ParticleEngine")


def test_priority_relocated_to_display_content():
    """0.8.2: Priority moved out of the deleted display.strategy module."""
    from scrollkit.display.content import Priority
    assert Priority.NORMAL == 2


def test_wifi_captive_portal_symbols_are_gone():
    """0.8.2: the unused ~330-line captive-portal web server is deleted."""
    from scrollkit.network.wifi_manager import WiFiManager
    for attr in ("generate_wifi_setup_page", "start_web_server", "run_web_server",
                 "register_routes", "update_http_clients", "_save_to_secrets_file"):
        assert not hasattr(WiFiManager, attr), "WiFiManager still has %s" % attr


def test_wifi_is_connected_method_shadow_is_gone():
    """0.8.2: the unreachable is_connected() METHOD (shadowed by the bool
    attribute set in __init__) is deleted rather than left dead."""
    from scrollkit.network.wifi_manager import WiFiManager
    assert not hasattr(WiFiManager, "is_connected"), \
        "is_connected should only exist as an instance attribute, not a class member"


# 0.8.2: exceptions.py collapsed to only the types the library actually raises.
# These 9 were caught-but-never-raised or fully dead.
REMOVED_EXCEPTIONS = [
    "DisplayError", "ContentError", "ConfigurationError", "WebServerError",
    "DeploymentError", "SimulatorError", "ResourceNotFoundError", "UpdateError",
    "ValidationError",
]


@pytest.mark.parametrize("name", REMOVED_EXCEPTIONS)
def test_removed_exception_is_gone(name):
    import scrollkit.exceptions as exc
    with pytest.raises(AttributeError):
        getattr(exc, name)


def test_surviving_exceptions_and_sldk_alias():
    """The four raised types survive; SLDKError stays as the ScrollKitError alias."""
    from scrollkit.exceptions import (
        ScrollKitError, SLDKError, NetworkError, OTAError, FeasibilityError)
    assert SLDKError is ScrollKitError
    for cls in (NetworkError, OTAError, FeasibilityError):
        assert issubclass(cls, ScrollKitError)


# Post-0.8.2 security removal: OTA manifests could carry pre/post_update_scripts
# that OTAClient.apply_update exec()'d — unsigned remote code execution, and no
# publisher ever emitted a script. The whole surface is gone; old manifests that
# still carry the (empty) keys must parse fine with the keys ignored.

def test_ota_manifest_script_surface_is_gone():
    from scrollkit.ota.manifest import UpdateManifest
    m = UpdateManifest(version="1.0.0")
    assert not hasattr(m, "add_script")
    assert not hasattr(m, "pre_update_scripts")
    assert not hasattr(m, "post_update_scripts")
    assert "pre_update_scripts" not in m.to_dict()


def test_ota_manifest_ignores_legacy_script_keys():
    from scrollkit.ota.manifest import UpdateManifest
    legacy = {
        "version": "1.0.0",
        "files": {"/src/code.py": {"size": 1, "checksum": "0" * 64,
                                   "required": True}},
        "pre_update_scripts": [],
        "post_update_scripts": [],
    }
    m = UpdateManifest.from_dict(legacy)  # must not raise
    assert m.version == "1.0.0"
    assert not hasattr(m, "pre_update_scripts")


def test_ota_client_source_has_no_exec():
    """Nothing in the OTA client may exec()/eval() downloaded content."""
    import inspect
    import scrollkit.ota.client as client
    src = inspect.getsource(client)
    assert "exec(" not in src
    assert "eval(" not in src


# Post-0.8.2 orphan pruning (zero references anywhere, incl. tests + the app):
# the DisplayManager windowing cluster (only reachable through the equally dead
# BaseDevice.run/run_once), the unused ScrollingLabel emulation shim, the
# captive-portal residue methods on WiFiManager, the ColorUtils static helpers
# (class survives for its `colors` table), and the UpdateManifest builder half
# (real producers build the manifest dict directly).

def test_display_manager_and_scrolling_label_are_gone():
    with pytest.raises(ImportError):
        from scrollkit.simulator.core import display_manager  # noqa: F401
    with pytest.raises(ImportError):
        from scrollkit.simulator.adafruit_display_text import scrolling_label  # noqa: F401
    import scrollkit.simulator.core as core
    assert not hasattr(core, "DisplayManager")
    from scrollkit.simulator.devices.base_device import BaseDevice
    assert not hasattr(BaseDevice, "run")
    assert not hasattr(BaseDevice, "run_once")


def test_wifi_manager_captive_portal_residue_is_gone():
    """The dead HELPERS stay gone — but NOT the onboarding feature itself.

    start_access_point/stop_access_point were briefly deleted in the same
    sweep and then restored on purpose: they are half of the no-file-editing
    WiFi setup portal (a major feature that had been silently unwired since
    the settings-server rewrite). See run_setup_portal / web/wifi_setup.py.
    """
    from scrollkit.network.wifi_manager import WiFiManager
    for name in ("disconnect", "is_available", "get_ip_address"):
        assert not hasattr(WiFiManager, name), name
    # The restored onboarding surface must stay.
    for name in ("start_access_point", "stop_access_point", "ap_ip_address",
                 "run_setup_portal", "scan_networks", "save_credentials"):
        assert hasattr(WiFiManager, name), name


def test_color_utils_static_helpers_are_gone():
    from scrollkit.utils.color_utils import ColorUtils
    for name in ("to_rgb", "from_rgb", "scale_color", "hex_str_to_rgb",
                 "pad_hex", "hex_str_to_number", "number_to_hex_string"):
        assert not hasattr(ColorUtils, name), name
    assert "Yellow" in ColorUtils.colors      # the surviving reason-to-exist


def test_manifest_builder_half_is_gone():
    from scrollkit.ota.manifest import UpdateManifest
    m = UpdateManifest(version="1.0.0")
    for name in ("add_dependency", "set_requirement", "from_json",
                 "get_required_files", "get_optional_files"):
        assert not hasattr(m, name), name
    assert hasattr(m, "add_file")             # test helper deliberately kept
