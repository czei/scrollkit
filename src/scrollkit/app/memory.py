# Copyright (c) 2024-2026 Michael Czeiszperger
"""Realistic free-RAM estimate shared by the run loop and the dev harness.

The run loop gates optional processes on free RAM (data updates need ~20-30 KB,
the web server ~50 KB). On real CircuitPython that comes from ``gc.mem_free()``.
On the desktop simulator there is no such limit, so historically these sites just
pretended ~100 KB was free — which means an AI agent verifying an app on the
simulator never sees the low-memory code paths a real MatrixPortal S3 would hit.

``free_memory()`` keeps that generous desktop default UNLESS the hardware-realism
simulation is active (``SimulatorDisplay(hardware_timing=True)`` /
``SCROLLKIT_HW_SIM=1``), in which case it reports the modeled *device* budget
minus the modeled live allocation. So the existing 20/30/50 KB ladder actually
gates against the device's tiny RAM during a simulated run, and the feasibility
report's "won't fit" warning lines up with what the loop decided.

Default behavior is unchanged: on hardware it's the real number; on desktop with
the sim OFF it's the same large constant as before.

Device-safe: ``gc`` is the only hard import; the simulator lookup is wrapped so it
never fails on CircuitPython (where the simulator package isn't present).
"""

import gc

# Free RAM reported on desktop when the hardware sim is OFF. Matches the literal
# previously hard-coded across app/base.py, so default behavior is unchanged.
DESKTOP_FREE_BYTES = 100_000


__all__ = ['free_memory', 'DESKTOP_FREE_BYTES']

def free_memory():
    """Best estimate of free RAM in bytes.

    - CircuitPython hardware: the real ``gc.mem_free()``.
    - Desktop + hardware sim ON: modeled device budget minus modeled usage.
    - Desktop + hardware sim OFF: ``DESKTOP_FREE_BYTES`` (no behavior change).
    """
    if hasattr(gc, "mem_free"):
        # Real hardware (or any build exposing mem_free) — trust the device.
        try:
            return gc.mem_free()
        except Exception:
            pass
    modeled = _modeled_free_memory()
    if modeled is not None:
        return modeled
    return DESKTOP_FREE_BYTES


def _modeled_free_memory():
    """Free RAM implied by the active hardware PerformanceManager, or None.

    The import lives entirely inside the (desktop-only) simulator package; any
    failure simply means "no hardware model active" and we fall back.
    """
    try:
        from ..simulator.core.performance_manager import get_active
    except Exception:
        return None
    manager = get_active()
    if manager is None:
        return None
    try:
        budget = manager.profile.usable_ram_bytes
        used = manager.estimated_peak_ram_bytes()
        return max(0, budget - used)
    except Exception:
        return None
