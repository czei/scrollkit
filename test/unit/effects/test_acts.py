"""Acts run over a mark they know nothing about.

The point of the module under test is portability, so these tests give it the least an
app could possibly hand it — a set of cells and four callbacks — and check that a real
build assembles a real mark. If an act needs anything else, it fails here rather than in
the app that tried to reuse it.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import asyncio

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.effects.acts import (  # noqa: E402
    BUILDS, EXITS, SimpleContext, act_factory, drip_in, supported_acts,
    swarm_build, swarm_unbuild,
)

#: A mark, as an app would hand one over: lit cells with a palette index each.
MARK = {(10, 12): 1, (11, 12): 1, (12, 12): 2, (13, 12): 2,
        (10, 13): 1, (13, 13): 3, (11, 14): 1, (12, 14): 2}


async def _display():
    from scrollkit.display.simulator import SimulatorDisplay

    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    return d


def _run(act, **kw):
    """Run one act over MARK; return (ok, shown, hidden, frames)."""
    async def go():
        d = await _display()
        seen = {"show": 0, "hide": 0, "frames": 0}

        async def frame():
            seen["frames"] += 1
            await d.show()
            return True

        ctx = SimpleContext(
            d, MARK,
            show=lambda: seen.__setitem__("show", seen["show"] + 1),
            hide=lambda: seen.__setitem__("hide", seen["hide"] + 1),
            frame=frame,
        )
        ok = await act(ctx, **kw)
        return ok, seen["show"], seen["hide"], seen["frames"]

    return asyncio.run(go())


@pytest.mark.parametrize("direction", ["top", "bottom", "left", "right"])
def test_drip_in_assembles_the_mark_from_any_edge(direction):
    ok, shown, hidden, frames = _run(drip_in, direction=direction)
    assert ok is True
    assert hidden == 1, "the act clears what was there before it starts"
    assert shown == 1, "and hands the mark back at the end"
    assert frames > 1, "it presented frames rather than snapping"


def test_swarm_build_assembles_and_shows():
    ok, shown, hidden, frames = _run(swarm_build, num_birds=12)
    assert ok is True
    assert (hidden, shown) == (1, 1)
    assert frames > 1


def test_an_exit_does_not_show_the_mark_at_the_end():
    """The one asymmetry between a build and an exit, and it has to be in the act.

    A build ends with the mark on screen; an exit ends with it gone. An exit that
    called show() would put back exactly what it just carried away.
    """
    ok, shown, _hidden, _frames = _run(swarm_unbuild, num_birds=12)
    assert ok is True
    assert shown == 0


def test_a_stopping_sign_ends_the_act_early():
    """`running` going false has to end the act, not merely be noticed.

    One of the two acts this module replaced checked `running` and the other did not.
    The one that did not would keep a stopping sign on screen for another two thousand
    frames.
    """
    async def go():
        d = await _display()
        state = {"frames": 0}
        ctx = SimpleContext(d, MARK)

        async def frame():
            state["frames"] += 1
            if state["frames"] == 3:
                ctx.running = False
            await d.show()
            return True

        ctx._frame = frame
        ok = await drip_in(ctx)
        return ok, state["frames"]

    ok, frames = asyncio.run(go())
    assert ok is False, "an interrupted act reports that it did not finish"
    assert frames < 20, "and stops promptly rather than running its cap out"


def test_a_dead_surface_ends_the_act():
    """`frame()` returning False is not advisory — the surface is gone."""
    async def go():
        d = await _display()
        state = {"n": 0}

        async def frame():
            state["n"] += 1
            return state["n"] < 3

        ctx = SimpleContext(d, MARK, frame=frame)
        return await drip_in(ctx), state["n"]

    ok, n = asyncio.run(go())
    assert ok is False
    assert n == 3


def test_an_act_takes_a_plain_iterable_of_cells():
    """Colour information is optional: many marks are one flat tone.

    A mapping gives each cell its own ramp stop; a bare set still has to work, because
    an app that has not built a palette yet still has a shape to reveal.
    """
    async def go():
        d = await _display()
        ctx = SimpleContext(d, set(MARK))
        return await drip_in(ctx)

    assert asyncio.run(go()) is True


def test_the_registry_names_every_act():
    from scrollkit.effects.acts import DWELLS

    assert act_factory("drip") is drip_in
    assert act_factory("swarm") is swarm_build
    assert act_factory("unswarm") is swarm_unbuild
    assert act_factory("no such act") is None
    assert set(supported_acts("build")) == set(BUILDS)
    assert set(supported_acts("dwell")) == set(DWELLS)
    assert set(supported_acts("exit")) == set(EXITS)
    # Three decks, because an act is build -> dwell -> exit and the middle one is
    # where a reference sign keeps most of its variety.
    assert set(supported_acts()) == set(BUILDS) | set(DWELLS) | set(EXITS)
