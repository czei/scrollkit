# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Shared desktop-simulator backend setup for the two display classes.

``UnifiedDisplay`` (the production entry point, which auto-selects hardware vs
simulator) and ``SimulatorDisplay`` (the desktop recording/verification display)
both stand up an identical simulator device: build a ``MatrixPortalS3``, wire the
optional hardware-timing model onto it *before* ``initialize()`` (the LEDMatrix
reads ``device.performance_manager`` there), initialize it, and prepare the
render surface. That setup lived duplicated in both classes; it lives here now so
one edit updates both.

Desktop-only by design: every simulator import is inside a function, so importing
this module costs nothing and it is never reached on the CircuitPython path (the
hardware branch of ``UnifiedDisplay`` doesn't call it, and ``SimulatorDisplay``
itself raises ``ImportError`` on CircuitPython).
"""

from __future__ import annotations

import os


def create_sim_device(width, height, board_id, *, pitch=None,
                      hardware_timing=False, throttle=False, strict=False):
    """Build and initialize a simulator ``MatrixPortalS3``.

    Wires an optional ``PerformanceManager`` (hardware-timing model) onto the
    device before ``initialize()`` when timing is requested — via the
    ``hardware_timing``/``throttle``/``strict`` flags or the
    ``SCROLLKIT_HW_SIM`` / ``SCROLLKIT_HW_THROTTLE`` / ``SCROLLKIT_HW_STRICT``
    env vars. ``strict`` (and throttle) imply timing: you can't gate/crawl a
    model you aren't running.

    Args:
        width, height: Panel geometry in pixels.
        board_id: Which board's timing profile to model.
        pitch: LED pitch (mm) -> on-screen size; ``None`` uses the device default
            (``UnifiedDisplay`` doesn't set it; ``SimulatorDisplay`` does, for
            higher-resolution recordings).
        hardware_timing, throttle, strict: Constructor-level opt-ins for the
            timing model (env vars are honored regardless).

    Returns:
        ``(device, matrix, display, perf)`` where ``perf`` is the
        ``PerformanceManager`` (or ``None`` when hardware timing is off).
    """
    from scrollkit.simulator.devices.matrixportal_s3 import MatrixPortalS3

    env_sim = os.environ.get("SCROLLKIT_HW_SIM") == "1"
    env_throttle = os.environ.get("SCROLLKIT_HW_THROTTLE") == "1"
    env_strict = os.environ.get("SCROLLKIT_HW_STRICT") == "1"
    want_throttle = throttle or env_throttle
    want_strict = strict or env_strict
    # strict implies hardware timing — you can't gate a model you aren't running.
    want_timing = hardware_timing or env_sim or want_throttle or want_strict

    if pitch is None:
        device = MatrixPortalS3(width=width, height=height)
    else:
        device = MatrixPortalS3(width=width, height=height, pitch=pitch)

    perf = None
    if want_timing:
        try:
            from scrollkit.simulator.core.hardware_profile import profile_for
            from scrollkit.simulator.core.performance_manager import (
                PerformanceManager, set_active)
        except ImportError:
            perf = None
        else:
            perf = PerformanceManager(profile_for(board_id), enabled=True,
                                      throttle=want_throttle, strict=want_strict)
            # Wired BEFORE initialize() (LEDMatrix reads it there); set_active
            # feeds the Label glyph-rebuild hook.
            device.performance_manager = perf
            set_active(perf)

    device.initialize()

    matrix = device.matrix
    display = device.display
    if hasattr(matrix, "initialize_surface"):
        matrix.initialize_surface()

    return device, matrix, display, perf


def disabled_feasibility_report(hint):
    """The shared "hardware timing is off" stub report.

    ``hint`` is the caller-specific way to turn timing on (the env var alone for
    ``UnifiedDisplay``; the constructor flag for ``SimulatorDisplay``).
    """
    from scrollkit.simulator.core.feasibility import FeasibilityReport
    return FeasibilityReport(
        "hardware timing disabled", "DISABLED",
        hint,
        False, None, 0.0, 0.0, {}, 0, 0,
        ["Hardware timing is off — no feasibility data. " + hint])
