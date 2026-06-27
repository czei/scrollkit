# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Canonical list of built-in transition names — the single source of truth.

This module is **literal-only**: it imports nothing, so it is safe to import on
the device boot path (e.g. from ``settings_manager``) without dragging in the
heavy ``scrollkit.effects`` package. The name -> class dispatch lives in
``scrollkit.effects.transitions`` (``_TRANSITION_MAP`` / ``transition_factory``);
``test_transition_registry`` asserts the two stay in lockstep, in this order.

Order is UI-facing: the settings dropdown / web form render the choices in this
order (with ``"None"`` prepended), so do not reorder casually.
"""

TRANSITION_NAMES = (
    "Drop from Sky",
    "Pixel Dissolve",
    "Column Rain",
    "Gradual Reveal",
    "Scan Fold",
    "Horizontal Wipe",
    "Glitch Bars",
    "Diagonal Wipe",
    "Iris Snap",
    "Venetian Shutters",
    "Mosaic Resolve",
    "CRT Collapse",
    "Light Slit",
)
