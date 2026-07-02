# Copyright (c) 2024-2026 Michael Czeiszperger
"""Simulator display for SLDK — the interactive desktop entry point.

``SimulatorDisplay`` IS ``UnifiedDisplay`` (one per-frame pipeline: the same
clear/draw_text/set_pixel/fill/show code that runs on hardware, over the
emulated ``displayio`` backend). What this subclass adds is purely the desktop
developer ergonomics:

- opens the pygame window automatically on the first ``show()``
- constructor knobs for the window (``scale``) and recording quality (``pitch``)
- the hardware-timing flags as first-class constructor args (they exist on
  ``UnifiedDisplay`` too)

Everything else — recording (``start_recording`` / ``save_gif`` /
``save_video``), ``screenshot``, the painters, the label pools, feasibility —
is inherited. If simulator output ever disagrees with hardware, fix the
simulator backend (``scrollkit.simulator``), never this class: there is no
per-class render logic left to diverge.
"""

from __future__ import annotations

import sys

# Verify we're NOT on CircuitPython
if hasattr(sys, 'implementation') and sys.implementation.name == 'circuitpython':
    raise ImportError("Simulator display cannot be used on CircuitPython")

from .unified import UnifiedDisplay, LED_SIMULATOR_AVAILABLE

if not LED_SIMULATOR_AVAILABLE:
    raise ImportError(
        "SLDK simulator not available. "
        "Ensure all SLDK components are properly installed."
    )


__all__ = ['SimulatorDisplay']


class SimulatorDisplay(UnifiedDisplay):
    """Interactive desktop display: UnifiedDisplay + an auto-created window."""

    _WINDOW_TITLE = "SLDK Simulator"
    _AUTO_WINDOW = True

    def __init__(self, width: int = 64, height: int = 32, scale: int = 10,
                 *, hardware_timing: bool = False, throttle: bool = False,
                 strict: bool = False, board=None, pitch: float = 3.0):
        """Initialize the simulator display.

        Args:
            width: Display width in pixels
            height: Display height in pixels
            scale: Window scale factor (fallback when the LED renderer doesn't
                publish its own surface size)
            hardware_timing: Model how slow the real CircuitPython device would
                run (read the estimate via feasibility_report()). Off by default;
                also enabled by the env var SCROLLKIT_HW_SIM=1.
            throttle: When hardware_timing is on, also sleep so the window crawls
                at the modeled hardware speed (off by default; tests never use it).
            strict: Enforce the feasibility gate — a sustained over-budget run (or
                a catastrophic single frame, or a RAM breach) raises
                FeasibilityError instead of just warning. Implies hardware_timing.
                Also enabled by SCROLLKIT_HW_STRICT=1. Off by default.
            board: Which board's performance profile to model for hardware
                timing/feasibility (e.g. ``"pimoroni_interstate75_w"``). ``None``
                honors ``SCROLLKIT_HW_BOARD`` and defaults to the MatrixPortal S3.
            pitch: LED pitch (mm) -> on-screen LED size. Raise it (e.g. 6.0) to
                render the panel at a higher resolution for crisp recordings and
                screenshots; changes only the visual scale, not the pixel grid.
        """
        super().__init__(width=width, height=height, board=board,
                         hardware_timing=hardware_timing, throttle=throttle,
                         strict=strict, pitch=pitch)
        self._scale: int = scale

    async def initialize(self) -> None:
        await super().initialize()
        print("Simulator display initialized")
