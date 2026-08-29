"""Acts: reveal a mark, hold it, take it away — over art someone else drew.

An **act** is the unit a sign is actually made of: build -> dwell -> exit. The
treatments in :mod:`scrollkit.effects.palette_treatments` are already portable dwells,
because they take a :class:`~scrollkit.effects.palette_partition.PalettePartition` and
nothing else — which is why twelve of a reference sign's fifteen dwells are one-liners.
Builds and exits were not portable, because they were written inside the app that owned
the mark and reached into its tiles, its layout and its palette directly.

This module is the missing half: a build or an exit that knows nothing about the mark
except what the context hands it.

**The context.** Duck-typed on purpose — an app already has these, under its own names,
and should not have to inherit anything to use an act:

===================  =========================================================
``ctx.slots``        The mark's lit cells. A mapping of ``(x, y) -> palette
                     index``, or any iterable of ``(x, y)``. Acts that need
                     per-pixel colour use the mapping; the rest just need the
                     positions.
``ctx.colors``       Optional. The ramp those indices point into, low->high.
                     **Indices are meaningless without it** — that is not a
                     style preference, it is what SwarmReveal enforces: an
                     index_map with no ramp raises. A context with slots but
                     no colours gets a flat reveal, which is correct and is
                     what a one-tone mark wants anyway.
``ctx.display``      The display to ``start()`` an effect against.
``ctx.running``      Falsy means the sign is stopping; an act must return early.
``await ctx.frame()``  Present one frame. ``False`` means the surface went away
                     and the act must stop — the return value is not advisory.
``ctx.show()``       Put the mark on screen in its final place.
``ctx.hide()``       Clear the mark and anything layered over it.
===================  =========================================================

Every act returns ``True`` if it ran to completion and ``False`` if it stopped early,
and every act detaches whatever it attached — including on the early exit, because the
overlay outlives the act otherwise and the next one starts on a dirty panel.

    from scrollkit.effects.acts import act_factory
    ok = await act_factory("drip")(ctx, direction="bottom")

`SimpleContext` is the smallest thing that satisfies the protocol; an app with its own
tiles and layouts will usually pass itself instead.
"""

from .drip_splash import DripReveal
from .swarm_reveal import SwarmReveal

#: Fallback when the context's slots carry no colour information.
_DEFAULT_COLOR = 0xFFB030

#: A frame-driven effect that never reports completion has to be stopped by something.
#: These are generous — a swarm is measured in hundreds of frames — because the cap is a
#: runaway guard and not a duration.
_SWARM_MAX_STEPS = 2500
_DRIP_MAX_STEPS = 2000


class SimpleContext:
    """The smallest thing an act will accept.

    Useful for tests and for an app that has no tile machinery of its own. An app that
    does should pass itself: the protocol is six names, and inheriting from this would
    buy nothing.
    """

    def __init__(self, display, slots, colors=None, show=None, hide=None, frame=None):
        self.display = display
        self.slots = slots
        self.colors = colors
        self.running = True
        self._show = show
        self._hide = hide
        self._frame = frame

    async def frame(self):
        if self._frame is not None:
            return await self._frame()
        if await self.display.show() is False:
            return False
        return True

    def show(self):
        if self._show is not None:
            self._show()

    def hide(self):
        if self._hide is not None:
            self._hide()


def _positions(slots):
    """The mark's cells as a list of ``(x, y)``, from a mapping or a plain iterable."""
    return list(slots)


def _index_map(slots):
    """``{(x, y): ramp index}`` when the slots carry colour, else ``None``."""
    if hasattr(slots, "items"):
        return dict(slots)
    return None


async def _drive(ctx, effect, max_steps, is_done):
    """Step an effect to completion, presenting a frame each time.

    Shared because the loop is where both acts previously differed only by accident:
    one checked ``running`` and the other did not, one bounded its steps at 2000 and the
    other at 2500. A build that ignores ``running`` keeps a stopping sign on screen for
    another two thousand frames.
    """
    steps = 0
    while steps < max_steps:
        if not ctx.running:
            return False
        if is_done(effect):
            return True
        effect.step()
        steps += 1
        if await ctx.frame() is False:
            return False
    return True


async def swarm_build(ctx, colors=None, index_map=None, bird_color=0xB0B0B0,
                      num_birds=48, bird_speed=2.6, reverse=False):
    """A flock carries the mark into place, pixel by pixel.

    ``colors`` is a low->high ramp for the assembled image; with ``index_map`` (or
    colour-carrying ``ctx.slots``) each cell takes its own stop, which is how a mark
    assembles in its true colours rather than one flat tone.

    ``num_birds`` is the hardware-feasibility knob: per-frame cost grows with its
    square, because of the boids neighbour pass.
    """
    ctx.hide()
    pixels = _positions(ctx.slots)
    if colors is None:
        colors = getattr(ctx, "colors", None)
    # **Only with a ramp.** Per-pixel indices point into `colors`, and SwarmReveal
    # raises on an index_map without one rather than guessing — correctly, because a
    # guessed palette is a sign in colours nobody chose. No ramp means a flat reveal.
    if index_map is None and colors is not None:
        index_map = _index_map(ctx.slots)
    if colors is None:
        index_map = None
    swarm = SwarmReveal(pixels, bird_color=bird_color, num_birds=num_birds,
                        bird_speed=bird_speed, text_colors=colors,
                        index_map=index_map, reverse=reverse)
    swarm.start(ctx.display)
    try:
        ok = await _drive(ctx, swarm, _SWARM_MAX_STEPS,
                          lambda s: s.is_complete)
        if ok and not reverse:
            ctx.show()
        return ok
    finally:
        # Detached even when the act stopped early. The overlay outlives the act
        # otherwise, and the next one starts on a panel it did not draw.
        swarm.detach()


async def swarm_unbuild(ctx, colors=None, index_map=None, bird_color=0xB0B0B0,
                        num_birds=48, bird_speed=2.6):
    """The same flock, carrying the mark away. The exit half of :func:`swarm_build`."""
    return await swarm_build(ctx, colors=colors, index_map=index_map,
                             bird_color=bird_color, num_birds=num_birds,
                             bird_speed=bird_speed, reverse=True)


async def drip_in(ctx, direction="top", color=None, fall_speed=2, stagger=1):
    """The mark's pixels rain in from an edge, then the real colours arrive.

    The drip draws in one flat ``color``; :meth:`ctx.show` lifts that overlay onto the
    mark's own layers underneath, so the true palette appears at the moment the last
    drop lands. ``direction`` is "top", "bottom", "left" or "right".
    """
    ctx.hide()
    if color is None:
        color = _DEFAULT_COLOR
    drip = DripReveal(_positions(ctx.slots), color=color, fall_speed=fall_speed,
                      stagger=stagger, direction=direction)
    drip.start(ctx.display)
    try:
        ok = await _drive(ctx, drip, _DRIP_MAX_STEPS, lambda d: d.is_complete)
        if ok:
            ctx.show()
        return ok
    finally:
        drip.detach()


#: name -> build. Mirrors :func:`scrollkit.effects.transitions.transition_factory`:
#: a name is what an app, a catalogue or a person selecting from a menu can hold.
BUILDS = {
    "swarm": swarm_build,
    "drip": drip_in,
}

#: name -> exit.
EXITS = {
    "unswarm": swarm_unbuild,
}


def act_factory(name):
    """The act for a name, or ``None`` if the name is not one.

    ``None`` rather than a raise, matching ``transition_factory``: the caller decides
    whether an unknown name is a typo or a feature it does not have yet.
    """
    return BUILDS.get(name) or EXITS.get(name)


def supported_acts(kind=None):
    """Act names, all of them or just ``"build"`` / ``"exit"``."""
    if kind == "build":
        return tuple(BUILDS)
    if kind == "exit":
        return tuple(EXITS)
    return tuple(BUILDS) + tuple(EXITS)
