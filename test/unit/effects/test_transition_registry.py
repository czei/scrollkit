"""The transition name list and the dispatch factory are one source of truth.

WS2 contract:
- ``config.transition_names.TRANSITION_NAMES`` (what the settings UI offers) and
  ``effects.transitions`` dispatch (``transition_factory`` / ``supported_names``)
  must stay in lockstep, IN ORDER — drift here used to silently make a selected
  transition a no-op.
- Importing the boot-path settings module must NOT pull the heavy
  ``scrollkit.effects`` package into RAM. Verified in a subprocess so the
  assertion can't be contaminated by other tests that already imported the
  effects stack in this process.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pathlib
import subprocess
import sys

from scrollkit.config.transition_names import TRANSITION_NAMES
from scrollkit.effects.transitions import transition_factory, supported_names


def test_names_and_factory_in_lockstep_and_ordered():
    # Ordered equality: the UI renders choices in this order, and a set comparison
    # would miss order drift between the two sources.
    assert tuple(supported_names()) == tuple(TRANSITION_NAMES)


def test_every_name_resolves_to_a_fresh_transition():
    for name in TRANSITION_NAMES:
        t = transition_factory(name)
        assert t is not None, name
        # duck-typed transition contract (DropFromSky is not a Transition subclass)
        assert hasattr(t, "render") and hasattr(t, "is_complete"), name
    # fresh instance each call (no shared state across content swaps)
    assert transition_factory("Iris Snap") is not transition_factory("Iris Snap")


def test_unknown_name_returns_none():
    assert transition_factory("Definitely Not A Transition") is None


def test_settings_import_does_not_load_the_effects_stack():
    """Boot-path guarantee: importing settings imports no scrollkit.effects.* module."""
    src = pathlib.Path(__file__).resolve().parents[3] / "src"
    code = (
        "import sys\n"
        "import scrollkit.config.settings_manager\n"
        "forbidden = [\n"
        "    'scrollkit.effects',\n"
        "    'scrollkit.effects.transitions',\n"
        "    'scrollkit.effects.overlay',\n"
        "    'scrollkit.effects.easing',\n"
        "    'scrollkit.effects.particles',\n"
        "    'scrollkit.effects.reveal_splash',\n"
        "    'scrollkit.effects.drip_splash',\n"
        "    'scrollkit.effects.swarm_reveal',\n"
        "    'scrollkit.effects.text_render',\n"
        "]\n"
        "loaded = [m for m in forbidden if m in sys.modules]\n"
        "if loaded:\n"
        "    raise SystemExit('boot-path imported effects modules: ' + repr(loaded))\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(src)
    env["PYTHONSAFEPATH"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr or result.stdout
