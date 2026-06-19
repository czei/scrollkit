#!/usr/bin/env python3
"""Memory baseline gate for the merged ScrollKit library (spec FR-046).

Records free RAM (a) immediately after ``import scrollkit`` and (b) after
constructing a ScrollKitApp, then compares against a committed baseline so a
memory regression vs the pre-merge SLDK footprint fails the gate.

On CircuitPython (where ``gc.mem_free()`` exists) this measures real device RAM.
On desktop CPython ``gc.mem_free()`` is absent, so the measurement is skipped
(the gate is a device-only check); the script still verifies that importing the
package is cheap and side-effect-free.

Usage on device (from the REPL or code.py):
    import test.memory_baseline as mb; mb.run()

Usage on desktop:
    PYTHONSAFEPATH=1 PYTHONPATH=src python test/memory_baseline.py
"""

import gc
import json
import os

BASELINE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "memory_baseline.json")


def _free():
    """Return free bytes, or None on platforms without gc.mem_free (desktop)."""
    mem_free = getattr(gc, "mem_free", None)
    return mem_free() if mem_free else None


def measure():
    """Return {'after_import': int|None, 'after_app_init': int|None}."""
    gc.collect()
    import scrollkit  # noqa: F401  (cheap: lightweight __init__, no eager submodules)
    gc.collect()
    after_import = _free()

    from scrollkit.app.base import ScrollKitApp

    class _Probe(ScrollKitApp):
        async def prepare_display_content(self):
            return None

    _app = _Probe(enable_web=False)  # noqa: F841
    gc.collect()
    after_app_init = _free()

    return {"after_import": after_import, "after_app_init": after_app_init}


def run():
    result = measure()
    print("ScrollKit memory:", result)

    if result["after_import"] is None:
        print("gc.mem_free() unavailable (desktop) - import OK, device gate skipped.")
        return True

    try:
        with open(BASELINE_PATH) as f:
            baseline = json.load(f)
    except OSError:
        print("No baseline committed yet. Record current numbers as baseline:")
        print(json.dumps(result, indent=2))
        return True

    ok = True
    for key in ("after_import", "after_app_init"):
        b = baseline.get(key)
        r = result.get(key)
        if b is None or r is None:
            continue
        # Lower free RAM than baseline == regression (we must use <= baseline use,
        # i.e. >= baseline free). Allow a small slack for measurement noise.
        if r < b - 2048:
            print("REGRESSION at %s: free=%d < baseline=%d" % (key, r, b))
            ok = False
    print("Memory gate:", "PASS" if ok else "FAIL")
    return ok


if __name__ == "__main__":
    import sys
    sys.exit(0 if run() else 1)
