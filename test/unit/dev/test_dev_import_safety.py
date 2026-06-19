"""RAM-safety guard for the desktop-only dev toolkit.

Two invariants protect the memory-constrained device:
  1. A device-style ``import scrollkit`` must never drag in ``scrollkit.dev``
     (numpy/pygame/etc.) — verified in a clean subprocess.
  2. Importing ``scrollkit.dev`` on CircuitPython must fail fast with a clear
     ImportError, so device code can't depend on it by accident.
"""

import os
import sys
import subprocess
import types

import pytest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
SRC = os.path.join(REPO_ROOT, "src")


def _run_in_clean_subprocess(code):
    env = dict(os.environ)
    env["PYTHONPATH"] = SRC + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONSAFEPATH"] = "1"  # root code.py shadows stdlib `code` otherwise
    return subprocess.run([sys.executable, "-c", code],
                          env=env, capture_output=True, text=True)


def test_core_import_does_not_pull_in_dev():
    code = (
        "import sys\n"
        "import scrollkit\n"
        "import scrollkit.app.base\n"          # the device import chain
        "leaked = [m for m in sys.modules if m.startswith('scrollkit.dev')]\n"
        "assert not leaked, 'scrollkit.dev leaked into a core import: %r' % leaked\n"
        "print('OK')\n"
    )
    result = _run_in_clean_subprocess(code)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout


def test_dev_import_raises_on_circuitpython(monkeypatch):
    # Force a fresh import so the guard re-runs, then restore on teardown.
    for name in list(sys.modules):
        if name == "scrollkit.dev" or name.startswith("scrollkit.dev."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    real = sys.implementation
    # Copy real attrs (incl. cache_tag, which importlib needs) and override name.
    fake = types.SimpleNamespace(
        **{k: getattr(real, k) for k in dir(real) if not k.startswith("__")})
    fake.name = "circuitpython"
    monkeypatch.setattr(sys, "implementation", fake)

    with pytest.raises(ImportError):
        import scrollkit.dev  # noqa: F401
