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
_DWELL_MAX_STEPS = 3000

#: A treatment theme is EXACTLY five stops, dark to bright: base, dim, flat, warm, hot.
#: Every treatment unpacks it that way (``base, dim, flat, warm, hot = self.theme``), so
#: a ramp of any other length raises from inside the effect on its first step. This is
#: the default when a mark carries no palette of its own.
_DEFAULT_RAMP = (0x70140E, 0x8F1B12, 0xB02318, 0xC93A1E, 0xE65A28)

#: How many stops a treatment theme has. Named because the number is a contract with
#: every class in palette_treatments, not a taste.
_THEME_STOPS = 5


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


# ---------------------------------------------------------------------------
# The library's own catalogue, as acts
# ---------------------------------------------------------------------------
#
# These three functions are where the menu actually comes from. A reference sign's
# thirty-seven acts are mostly not bespoke code: twenty-four are a transition or a
# palette treatment applied to the mark, selected by name. Wrapping the three
# selection mechanisms turns those into deck entries without writing them out.


def _centre(slots):
    """The mark's bounding-box centre, for the partitions that need an anchor."""
    xs = [x for (x, _y) in slots]
    ys = [y for (_x, y) in slots]
    if not xs:
        return 0, 0
    return (min(xs) + max(xs)) // 2, (min(ys) + max(ys)) // 2


def _partition_for(nickname, slots, groups):
    """``(group_map, n)`` for a treatment's partition, or ``None`` if it needs more.

    The builders take different arguments — an anchor column, a centre, nothing at
    all — so this supplies them from the mark's own geometry. ``map_route`` is the one
    that cannot be served: it needs the glyph stroke paths and terminus pixels of a
    specific mark, which is app knowledge and not derivable from a set of cells. The
    two treatments that want it are simply not offered rather than offered broken.
    """
    from . import palette_partition as P

    cx, cy = _centre(slots)
    if nickname == "diagonal":
        return P.map_diagonal(slots, groups)
    if nickname == "anchor":
        return P.map_anchor_distance(slots, cx, groups)
    if nickname == "radial":
        return P.map_radial(slots, cx, cy, groups)
    if nickname == "angle":
        return P.map_angle(slots, cx, cy, max(groups, 14))
    if nickname == "rain":
        return P.map_rain(slots, groups)
    if nickname == "checker":
        return P.map_checker(slots, 4)
    if nickname == "exposure":
        return P.map_exposure(slots)
    if nickname == "regions":
        return P.map_regions(slots, groups)
    if nickname == "topology":
        return P.map_topology(slots)
    return None


def _theme(colors):
    """Exactly five stops, whatever the caller had.

    A mark's palette is however many colours its art needed; a treatment theme is a
    five-stop ramp its author unpacks by name. Resampled rather than refused, because
    "your wordmark has six colours so you may not have a heat sweep" is not a rule
    anyone would accept, and picking five from a ramp is a well-defined thing to do.
    """
    colors = list(colors)
    if len(colors) == _THEME_STOPS:
        return colors
    if len(colors) < 2:
        return list(_DEFAULT_RAMP)
    # Evenly spaced across the ramp, endpoints included, so the darkest and brightest
    # the author chose stay the darkest and brightest the treatment sees.
    last = len(colors) - 1
    return [colors[round(i * last / (_THEME_STOPS - 1))] for i in range(_THEME_STOPS)]


def transitions_available():
    """Transition names that can drive a MARK, which is not all of them.

    A cover-and-swap transition hides the panel, runs a callback while nothing is
    visible, and uncovers the result — that is the model an act needs. ``Drop from Sky``
    is a different thing wearing the same word: it hooks ``pre_render_hook`` and
    animates a content Label's x/y through the display process, so its ``start`` never
    calls the swap callback at all and a mark handed to it stays hidden.

    It is excluded rather than offered and left to fail, for the reason the route
    treatments are: a menu entry that cannot work is worse than an absent one.
    """
    from .transitions import _TRANSITION_MAP

    return tuple(name for name, cls in _TRANSITION_MAP.items()
                 if not hasattr(cls, "pre_render_hook"))


def _treatment_extras(cls, theme):
    """Positional arguments a treatment needs beyond ``(fx, theme)``, or ``None``.

    Only ``lo`` and ``hi`` are servable, and the ramp's ends are the obvious answer for
    them — a gradient dwell between the darkest and brightest stop the author chose.
    Anything else required is something this module cannot invent, so the treatment is
    not offered.

    Read from the class's ``EXTRA_ARGS`` and **not** from ``inspect.signature``, which
    is the whole point: CircuitPython has no ``inspect``, so the introspecting version
    raised ImportError on the board and took ``treatments_available``, ``selectable``,
    ``treatment_dwell`` and ``play_sign`` down with it. Widening the ``except`` would
    not have fixed it either, only moved the failure: swallowing the error reports
    "no extras needed" and then calls ``GradientDwell(fx, theme)`` without its
    required ``lo``/``hi``. A test pins every ``EXTRA_ARGS`` against the real
    signature, so declaring it cannot drift from the code it describes.
    """
    extras = []
    for name in getattr(cls, "EXTRA_ARGS", ()):
        if name == "lo":
            extras.append(theme[0])
        elif name == "hi":
            extras.append(theme[-1])
        else:
            return None
    return tuple(extras)


def treatments_available():
    """Treatment names this module can drive over an arbitrary mark.

    Not every treatment in the library: the two route-based ones need a mark's stroke
    paths, so they are excluded here rather than offered and left to fail.
    """
    from .palette_treatments import TREATMENT_CLASSES

    probe = {(0, 0): 1, (1, 1): 1, (2, 2): 1, (3, 1): 1}
    names = []
    for cls in TREATMENT_CLASSES:
        if _partition_for(cls.PARTITION, probe, 4) is None:
            continue
        if _treatment_extras(cls, _DEFAULT_RAMP) is None:
            continue
        names.append(cls.__name__)
    return tuple(names)


async def treatment_dwell(ctx, treatment="VelvetSweep", ramp=None, groups=10):
    """A palette treatment over the mark: the DWELL between a build and an exit.

    The mark is not redrawn. A :class:`PalettePartition` groups its own pixels and the
    treatment animates the groups by rewriting palette entries — zero pixel writes a
    frame, which is why a reference sign can afford a dozen of these. Name any of
    :func:`treatments_available`.
    """
    from .palette_partition import PalettePartition
    from . import palette_treatments as T

    cls = getattr(T, treatment, None)
    if cls is None or cls not in T.TREATMENT_CLASSES:
        raise RuntimeError("no treatment named %r. Known: %s"
                           % (treatment, ", ".join(treatments_available())))
    # **Slot 1 is body; anything above it is identity and stays out of the sweep.**
    # That is the convention PalettePartition and the map_ builders share, and it is
    # how a reference sign stops a heat treatment recolouring an eye. A mark that
    # carries its own slots keeps them; a plain one is all body, because it has no
    # such distinction to lose.
    slots = (dict(ctx.slots) if hasattr(ctx.slots, "items")
             else {cell: 1 for cell in ctx.slots})

    built = _partition_for(cls.PARTITION, slots, groups)
    if built is None:
        raise RuntimeError(
            "%s wants the %r partition, which needs a mark's own stroke paths"
            % (treatment, cls.PARTITION))
    group_map, n = built

    theme = _theme(ramp or getattr(ctx, "colors", None) or _DEFAULT_RAMP)
    # The mark's own non-body colours, so an identity pixel keeps looking like itself
    # while the body is swept. Slots are 1-based into the ramp, and slot 1 is body.
    top = max(slots.values())
    identity = tuple(theme[1:top]) if top > 1 else ()

    fx = PalettePartition(ctx.display.gfx, slots, group_map, n,
                          identity_colors=identity,
                          width=ctx.display.width, height=ctx.display.height)
    ctx.display.add_layer(fx.tile)
    try:
        ctx.hide()
        fx.tile.hidden = False
        extras = _treatment_extras(cls, theme)
        if extras is None:
            raise RuntimeError("%s needs arguments this module cannot supply"
                               % (treatment,))
        effect = cls(fx, theme, *extras)
        if hasattr(effect, "start"):
            effect.start(ctx.display)
        ok = await _drive(ctx, effect, _DWELL_MAX_STEPS, lambda e: e.is_complete)
        fx.tile.hidden = True
        if ok:
            ctx.show()
        return ok
    finally:
        ctx.display.remove_layer(fx.tile)


async def reveal_via(ctx, transition="Iris Snap"):
    """A screen transition covers the panel, the mark appears behind it, it uncovers.

    Thirteen builds from one function — every name in
    :func:`scrollkit.effects.transitions.supported_names`.
    """
    return await _swap_via(ctx, transition, ctx.show, before=ctx.hide)


async def hide_via(ctx, transition="Pixel Dissolve"):
    """The same, taking the mark away. Thirteen exits from one function."""
    return await _swap_via(ctx, transition, ctx.hide)


async def _swap_via(ctx, name, swap, before=None):
    """Drive one screen transition: cover, run ``swap`` while hidden, uncover."""
    from .transitions import transition_factory

    if name not in transitions_available():
        raise RuntimeError("no transition named %r that can drive a mark. Known: %s"
                           % (name, ", ".join(transitions_available())))
    tr = transition_factory(name)
    if before is not None:
        before()
    await tr.start(ctx.display, swap)
    try:
        while not tr.is_complete:
            if not ctx.running:
                return False
            await tr.render(ctx.display)
            if await ctx.frame() is False:
                return False
        return True
    finally:
        # Not every transition has one — DropFromSky does not — and an act must not
        # fail on the way out of a transition that succeeded.
        detach = getattr(tr, "detach", None)
        if callable(detach):
            detach()


async def wink_in(ctx, color=None, off_per_frame=44, hold_seconds=0.6):
    """Every LED lights, then everything that is not the mark winks off."""
    from .reveal_splash import show_reveal_splash

    ctx.show()
    ok = await show_reveal_splash(ctx.display, _positions(ctx.slots),
                                  color=color if color is not None else _DEFAULT_COLOR,
                                  off_per_frame=off_per_frame,
                                  hold_seconds=hold_seconds)
    return ok is not False and bool(ctx.running)


# ---------------------------------------------------------------------------
# A whole sign: art, a deck, and a scheduler
# ---------------------------------------------------------------------------


def selectable():
    """The menu, one entry per CHOICE rather than per function.

    Seven act functions serve about forty selections, because a transition is both a
    build and an exit and every driveable treatment is its own dwell. A person picking
    from a list picks "Iris Snap", not "reveal_via with transition=Iris Snap", so the
    expansion happens here — once, where the acts are — rather than in each caller.

    Each entry is ``(name, kind, family, act, options)``:

    ``family``  What it looks like. Two entries sharing a family are "similar" and
                the scheduler will not play them back to back. A treatment's family is
                its PARTITION, because two treatments over the same grouping of pixels
                genuinely do look alike; a transition is its own family, which is the
                honest answer when nobody has grouped them by eye.
    """
    from . import palette_treatments as T

    out = []
    for name in transitions_available():
        out.append((name, "build", "t:" + name, reveal_via, {"transition": name}))
    for name in treatments_available():
        family = getattr(getattr(T, name), "PARTITION", name)
        out.append((name, "dwell", "p:" + str(family), treatment_dwell,
                    {"treatment": name}))
    for name in transitions_available():
        out.append((name, "exit", "t:" + name, hide_via, {"transition": name}))
    for kind, deck in (("build", BUILDS), ("exit", EXITS)):
        for name in deck:
            if name in ("reveal", "hide"):
                continue
            out.append((name, kind, "a:" + name, deck[name], {}))
    return out


def _deck(entries, kind):
    """Scheduler deck for one kind: ``(name, family, act, options)`` tuples."""
    return [(n, fam, fn, opts) for n, k, fam, fn, opts in entries if k == kind]


async def play_sign(ctx, chosen=None, scheduler=None, acts=None):
    """Play a sign: build, dwell, exit, again, until told to stop.

    This is what a sign IS — a reference sign's 1,755 acts are 13 builds x 15 dwells x
    9 exits, drawn from by a picker rather than written out as a sequence. So a deck is
    chosen and the ORDER is not: `ActScheduler` leads with the least-recently-seen and
    never repeats a family twice running, which is why a shipped sign does not visibly
    loop.

    Args:
        chosen:    What to draw from, or ``None`` for everything available. Entries
                   are ``"kind:name"`` — ``"build:Iris Snap"`` — because **the same
                   name is often two different choices**: every transition is both a
                   build and an exit, and someone who kept "Pixel Dissolve" to end on
                   did not thereby ask for it to open with. A bare ``"name"`` selects
                   it in every kind it appears in, which is the forgiving reading when
                   nobody has said otherwise.

                   A name that is not on the menu is ignored rather than raising: a
                   deck is a preference, and one stale entry should not stop a sign.
        acts:      How many build-dwell-exit cycles to play. ``None`` runs until
                   ``ctx.running`` goes false, which is what a panel on a wall wants.

    Returns the number of complete cycles played.
    """
    from ..utils.scheduler import ActScheduler

    entries = selectable()
    if chosen is not None:
        wanted = set(chosen)
        entries = [e for e in entries
                   if e[0] in wanted or "%s:%s" % (e[1], e[0]) in wanted]
    builds, dwells, exits = (_deck(entries, k) for k in ("build", "dwell", "exit"))
    if not (builds and exits):
        raise RuntimeError(
            "a sign needs at least one build and one exit; got %d and %d"
            % (len(builds), len(exits))
        )

    sched = scheduler or ActScheduler()
    played = 0
    avoid = ()
    while ctx.running and (acts is None or played < acts):
        for key, deck in (("build", builds), ("dwell", dwells), ("exit", exits)):
            if not deck:
                continue          # a sign with no dwells is a sign that flashes
            name, family, fn, options = sched.pick(deck, key, avoid=avoid)
            avoid = (family,)
            if not await fn(ctx, **options):
                return played
        played += 1
    return played


#: name -> build. Mirrors :func:`scrollkit.effects.transitions.transition_factory`:
#: a name is what an app, a catalogue or a person selecting from a menu can hold.
BUILDS = {
    "swarm": swarm_build,
    "drip": drip_in,
    "wink": wink_in,
    "reveal": reveal_via,
}

#: name -> exit.
EXITS = {
    "unswarm": swarm_unbuild,
    "hide": hide_via,
}

#: name -> dwell. The middle of build -> dwell -> exit, and the deck a reference sign
#: has most of: twelve of its fifteen dwells are a treatment over a partition.
DWELLS = {
    "treatment": treatment_dwell,
}


def act_factory(name):
    """The act for a name, or ``None`` if the name is not one.

    ``None`` rather than a raise, matching ``transition_factory``: the caller decides
    whether an unknown name is a typo or a feature it does not have yet.
    """
    return BUILDS.get(name) or DWELLS.get(name) or EXITS.get(name)


def supported_acts(kind=None):
    """Act names, all of them or one deck: ``"build"``, ``"dwell"``, ``"exit"``."""
    if kind == "build":
        return tuple(BUILDS)
    if kind == "dwell":
        return tuple(DWELLS)
    if kind == "exit":
        return tuple(EXITS)
    return tuple(BUILDS) + tuple(DWELLS) + tuple(EXITS)
