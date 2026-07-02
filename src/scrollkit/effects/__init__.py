# Copyright (c) 2024-2026 Michael Czeiszperger
"""ScrollKit Effects package.

Kept deliberately empty of imports: importing ``scrollkit.effects`` must not
pull in every standalone visual system, so a device build that only uses
transitions (``app.base``'s lazy ``from ..effects.transitions import
transition_factory``) never loads the particle engine or the splash reveals
into RAM. Import each submodule directly instead:

- **Transitions** (the one content-swap contract) —
  ``from scrollkit.effects.transitions import Transition, transition_factory,
  supported_names``
- **Content scrollers** (Class 1 — characterful scrolling) —
  ``from scrollkit.effects.scrolling import KineticMarquee, WaveRider, SplitFlap``
- **Splash / reveal animations** —
  ``from scrollkit.effects.reveal_splash import show_reveal_splash, pixels_from_text``,
  ``from scrollkit.effects.drip_splash import show_drip_splash, DripReveal``,
  ``from scrollkit.effects.swarm_reveal import show_swarm_splash, SwarmReveal``
- **Particles** —
  ``from scrollkit.effects.particles import ParticleEngine, Sparkle, Snow``
- **Text-rendering helpers** —
  ``from scrollkit.effects.text_render import pixels_from_font_text, font_text_width``

The old ``Effect``/``EffectRegistry``/``EffectsEngine``/``SimpleEffect`` systems
were removed: there is one transition contract (``effects.transitions.Transition``)
plus these standalone helpers — no overlapping per-frame "effect" base classes,
and no plugin/registry architecture layered on top of them.
"""
