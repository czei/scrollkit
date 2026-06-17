"""SLDK Effects Module."""

from __future__ import annotations

from .effects import EffectsEngine
from .base import Effect, CompositeEffect
from .basic_transitions import FadeInEffect, SlideInEffect, WipeEffect
from .particles import ParticleEngine, Sparkle, Snow
from .reveal import RevealEffect

__all__: list[str] = [
    'EffectsEngine',
    'Effect',
    'CompositeEffect',
    'FadeInEffect',
    'SlideInEffect',
    'WipeEffect',
    'ParticleEngine',
    'Sparkle',
    'Snow',
    'RevealEffect'
]