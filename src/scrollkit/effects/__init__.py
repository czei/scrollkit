"""SLDK Effects Module.

Standalone visual systems: the particle engine, splash/reveal animations, and
text-rendering helpers. Transitions live in ``effects.transitions`` and are
imported **lazily** (see ``app.base._get_transition``) so a no-transition setup
never loads them on the RAM-constrained device.

The old ``Effect``/``EffectRegistry``/``EffectsEngine``/``SimpleEffect`` systems
were removed: there is one transition contract (``effects.transitions.Transition``)
plus these standalone helpers — no overlapping per-frame "effect" base classes.
"""

from __future__ import annotations

from .particles import ParticleEngine, Sparkle, Snow
from .reveal_splash import show_reveal_splash, pixels_from_text
from .drip_splash import show_drip_splash, DripReveal
from .swarm_reveal import show_swarm_splash, SwarmReveal
from .text_render import pixels_from_font_text, font_text_width

__all__ = [
    'ParticleEngine',
    'Sparkle',
    'Snow',
    'show_reveal_splash',
    'show_drip_splash',
    'DripReveal',
    'show_swarm_splash',
    'SwarmReveal',
    'pixels_from_text',
    'pixels_from_font_text',
    'font_text_width',
]
