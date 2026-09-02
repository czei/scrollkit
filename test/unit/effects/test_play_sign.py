"""A whole sign: art, a deck, and a scheduler — plan 003 step 6.

What a sign IS, in this design, is not a written sequence. A reference sign's 1,755
acts are 13 builds x 15 dwells x 9 exits drawn from by a picker, and it does not
visibly repeat because the picker leads with the least-recently-seen and never plays
two of a family back to back. So the visitor chooses a DECK and the runtime chooses
the order.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import asyncio

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.effects import acts as A  # noqa: E402
from scrollkit.effects.mark import PixelMark  # noqa: E402

CELLS = {(x, 14): 1 for x in range(10, 50)}
CELLS.update({(x, 15): 1 for x in range(10, 50)})
RAMP = (0xB02318, 0xFFB030, 0xFFF1D8, 0xD4481E, 0xE8873C)


async def _ctx(budget=6000):
    from scrollkit.display.simulator import SimulatorDisplay

    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    mark = PixelMark(CELLS, colors=RAMP).attach(d)
    state = {"frames": 0}

    async def frame():
        state["frames"] += 1
        if state["frames"] > budget:
            return False
        await d.show()
        return True

    return mark.context(d, frame=frame), state, mark


def test_the_menu_is_one_entry_per_choice():
    entries = A.selectable()
    kinds = {k for _n, k, _f, _fn, _o in entries}
    assert kinds == {"build", "dwell", "exit"}
    assert len(entries) > 30, "seven functions, about forty choices"
    # Every entry is runnable as it stands: a name and the arguments that make it real.
    for name, _kind, _family, fn, options in entries:
        assert callable(fn), name
        assert isinstance(options, dict), name


def test_two_treatments_over_the_same_partition_share_a_family():
    """The scheduler's `avoid` is only worth anything if families mean something.

    Treatments are grouped by PARTITION because two treatments animating the same
    grouping of pixels genuinely do look alike — that is the judgement a viewer makes,
    and it is the one the picker needs.
    """
    dwells = A._deck(A.selectable(), "dwell")
    families = {}
    for name, family, _fn, _o in dwells:
        families.setdefault(family, []).append(name)
    shared = [names for names in families.values() if len(names) > 1]
    assert shared, "some treatments do share a partition"


def test_a_sign_plays_build_dwell_exit_and_comes_back_for_more():
    async def go():
        ctx, state, mark = await _ctx()
        played = await A.play_sign(ctx, acts=2)
        return played, state["frames"], mark._tile.hidden

    played, frames, hidden = asyncio.run(go())
    assert played == 2, "two complete cycles"
    assert frames > 50
    # A cycle ends on an exit, so the mark is gone. A sign that ended mid-build would
    # leave the panel in a state no act chose.
    assert hidden is True


def test_a_choice_is_kind_AND_name():
    """The same name is often two different choices.

    Every transition is both a build and an exit, so someone who kept "Pixel Dissolve"
    to END on did not thereby ask for it to OPEN with. Selecting by bare name played
    it as both, which is a sign the visitor did not choose.
    """
    async def go():
        ctx, _state, _mark = await _ctx()
        seen = []
        real = A.reveal_via

        async def spy(c, **kw):
            seen.append(kw.get("transition"))
            return await real(c, **kw)

        A.reveal_via = spy
        try:
            await A.play_sign(
                ctx,
                chosen=["build:Iris Snap", "dwell:VelvetSweep", "exit:Pixel Dissolve"],
                acts=3)
        finally:
            A.reveal_via = real
        return seen

    seen = asyncio.run(go())
    assert seen and set(seen) == {"Iris Snap"}, seen


def test_a_deck_with_no_exit_is_refused_rather_than_played_half():
    async def go():
        ctx, _s, _m = await _ctx()
        return await A.play_sign(ctx, chosen=["build:Iris Snap"], acts=1)

    with pytest.raises(RuntimeError, match="at least one build and one exit"):
        asyncio.run(go())


def test_a_stopping_sign_stops_between_acts():
    """`running` going false has to end the sign, not merely the current act."""
    async def go():
        ctx, state, _m = await _ctx()

        async def frame():
            state["frames"] += 1
            if state["frames"] > 40:
                ctx.running = False
            return True

        ctx._frame = frame
        return await A.play_sign(ctx), state["frames"]

    played, frames = asyncio.run(go())
    assert frames < 400, "it stopped promptly rather than finishing its deck"
    assert played >= 0


def test_names_that_are_not_on_the_menu_are_ignored_not_fatal():
    """A deck is a preference. One stale entry should not stop a sign."""
    async def go():
        ctx, _s, _m = await _ctx()
        return await A.play_sign(
            ctx, chosen=["Iris Snap", "no such act", "Pixel Dissolve"], acts=1)


def test_a_bare_name_is_the_forgiving_reading():
    """It selects every kind with that name — which is what someone means when they
    have not said otherwise, and is why the test above has to be explicit."""
    async def go():
        ctx, _s, _m = await _ctx()
        return await A.play_sign(ctx, chosen=["Iris Snap"], acts=1)

    assert asyncio.run(go()) == 1, "one name, used as both the build and the exit"

    assert asyncio.run(go()) == 1
