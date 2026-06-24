"""SLDK Effects Module."""

from __future__ import annotations

from .effects import EffectsEngine
from .base import Effect, CompositeEffect
from .particles import ParticleEngine, Sparkle, Snow
from .reveal_splash import show_reveal_splash, pixels_from_text
from .drip_splash import show_drip_splash, DripReveal
from .text_render import pixels_from_font_text, font_text_width

__all__: list[str] = [
    'EffectsEngine',
    'Effect',
    'CompositeEffect',
    'ParticleEngine',
    'Sparkle',
    'Snow',
    'show_reveal_splash',
    'show_drip_splash',
    'DripReveal',
    'pixels_from_text',
    'pixels_from_font_text',
    'font_text_width',
]