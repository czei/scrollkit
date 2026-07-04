"""0.8.2: scrollkit.effects/__init__.py is import-free (no registry either).

``app.base``'s lazy ``from ..effects.transitions import transition_factory``
must load ONLY transitions.py (+ its own easing/overlay dependencies) — not the
whole standalone-helper set (particles, splash reveals, text_render). Before
0.8.2, ``effects/__init__.py`` eagerly imported all of those, so using any
transition silently pulled the full ~1000-line helper set into RAM regardless
of whether the app used splashes at all. Verified in a subprocess so the
assertion can't be contaminated by other tests that already imported the
effects stack in this process.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pathlib
import subprocess
import sys


def test_importing_transitions_does_not_load_the_standalone_helpers():
    src = pathlib.Path(__file__).resolve().parents[3] / "src"
    code = (
        "import sys\n"
        "from scrollkit.effects.transitions import transition_factory\n"
        "forbidden = [\n"
        "    'scrollkit.effects.particles',\n"
        "    'scrollkit.effects.reveal_splash',\n"
        "    'scrollkit.effects.drip_splash',\n"
        "    'scrollkit.effects.swarm_reveal',\n"
        "    'scrollkit.effects.text_render',\n"
        "    'scrollkit.effects.image_animators',\n"
        "]\n"
        "loaded = [m for m in forbidden if m in sys.modules]\n"
        "if loaded:\n"
        "    raise SystemExit('transitions import pulled in: ' + repr(loaded))\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(src)
    env["PYTHONSAFEPATH"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_effects_package_has_no_eager_imports():
    """importing scrollkit.effects itself must not load any submodule."""
    src = pathlib.Path(__file__).resolve().parents[3] / "src"
    code = (
        "import sys\n"
        "import scrollkit.effects\n"
        "forbidden = [m for m in sys.modules if m.startswith('scrollkit.effects.')]\n"
        "if forbidden:\n"
        "    raise SystemExit('effects/__init__ eagerly loaded: ' + repr(forbidden))\n"
    )
    env = dict(os.environ)
    env["PYTHONPATH"] = str(src)
    env["PYTHONSAFEPATH"] = "1"
    result = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_effects_package_has_no_all_or_registry():
    """No __all__, no name->class dict — deliberate: no plugin/registry layer."""
    import scrollkit.effects as fx
    assert not hasattr(fx, "__all__")
