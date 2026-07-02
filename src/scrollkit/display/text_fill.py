# Copyright (c) 2024-2026 Michael Czeiszperger
"""Shared vocabulary for gradient text fills (the live source of truth).

Kept deliberately tiny and dependency-free (pure constants + functions, no
displayio, no colour math) so the RAM-constrained device pays almost nothing to
import it, and so three callers can share ONE definition instead of hardcoding
the strings in each place:

* ``display.content`` — validates the ``direction`` argument at construction;
* ``display.gradient_text`` — maps a pixel's position to a ramp index per axis;
* ``dev.capabilities`` — advertises the directions to the AI-authoring catalog by
  calling :func:`gradient_directions` (never a copy-pasted tuple), the same
  live-introspection discipline ``transition_names`` / ``palette_effects_for``
  already use.
"""

# The three gradient axes, matching ``SwarmReveal``'s colour-axis vocabulary so a
# user learns one set of names. "vertical" is the default because a top-light →
# bottom-dark shade reads as depth (the common "subtle" case). Reverse any axis by
# reversing the palette tuple — there is intentionally no ``*_reverse`` name.
GRADIENT_DIRECTIONS = ("vertical", "horizontal", "diagonal")

# Default number of palette ramp steps generated from the stops. Small on purpose:
# the panel is RGB444 (4 bits/channel) at the default bit_depth=4, so more steps
# rarely survive as distinct colours.
DEFAULT_PALETTE_STEPS = 8

# Hard cap. ``steps`` colours plus the transparent background (palette index 0)
# must fit in 16 values to keep the indexed bitmap at 4 bits/pixel (RAM + speed).
MAX_PALETTE_STEPS = 15


__all__ = ['gradient_directions', 'normalize_direction', 'clamp_palette_steps', 'GRADIENT_DIRECTIONS', 'DEFAULT_PALETTE_STEPS', 'MAX_PALETTE_STEPS']

def gradient_directions():
    """The supported gradient ``direction`` values, as a tuple of strings."""
    return GRADIENT_DIRECTIONS


def normalize_direction(direction):
    """Return ``direction`` if valid, else fall back to ``"vertical"``.

    Mirrors ``SwarmReveal``'s lenient handling: an unknown axis name degrades to
    the sensible default rather than raising on the device.
    """
    return direction if direction in GRADIENT_DIRECTIONS else "vertical"


def clamp_palette_steps(steps):
    """Clamp a requested ramp length into the 2..``MAX_PALETTE_STEPS`` range."""
    try:
        steps = int(steps)
    except (TypeError, ValueError):
        return DEFAULT_PALETTE_STEPS
    if steps < 2:
        return 2
    if steps > MAX_PALETTE_STEPS:
        return MAX_PALETTE_STEPS
    return steps
