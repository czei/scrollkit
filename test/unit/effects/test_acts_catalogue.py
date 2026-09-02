"""Every act the menu offers actually runs.

A menu whose entries do not all work is worse than a shorter menu: the reader cannot
tell which half is real, so they stop trusting any of it. These tests therefore run
EVERY name the module advertises — thirteen transitions as builds, the same thirteen as
exits, every driveable treatment, and the bespoke handful — rather than a sample.

They are also the promotion's proof. `reveal_via`, `hide_via` and `treatment_dwell`
exist so a reference sign's twenty-four library-driven acts reach a deck without being
written out one by one; if a name in the catalogue cannot be driven over a plain mark,
that claim is false for that name.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import asyncio

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.effects import acts as A  # noqa: E402
from scrollkit.effects.mark import PixelMark  # noqa: E402
from scrollkit.effects.acts import transitions_available  # noqa: E402
from scrollkit.effects import palette_treatments as T  # noqa: E402
from scrollkit.effects.palette_treatments import TREATMENT_CLASSES  # noqa: E402

CELLS = {(x, 12): 1 for x in range(8, 40)}
CELLS.update({(x, 13): 1 for x in range(8, 40)})
CELLS.update({(10, 14): 2, (12, 14): 2, (14, 14): 3})
RAMP = (0xB02318, 0xFFB030, 0xFFF1D8, 0xD4481E, 0xE8873C, 0x571007, 0x3A1206)


async def _ctx():
    from scrollkit.display.simulator import SimulatorDisplay

    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    mark = PixelMark(CELLS, colors=RAMP).attach(d)
    state = {"frames": 0}

    async def frame():
        state["frames"] += 1
        # Bounded hard: a transition or treatment that never completes must fail this
        # suite loudly rather than hang it.
        if state["frames"] > 4000:
            return False
        await d.show()
        return True

    return mark.context(d, frame=frame), state, mark


def _run(act, **kw):
    async def go():
        ctx, state, mark = await _ctx()
        ok = await act(ctx, **kw)
        return ok, state["frames"], mark._tile.hidden

    return asyncio.run(go())


@pytest.mark.parametrize("name", transitions_available())
def test_every_transition_works_as_a_build(name):
    ok, frames, hidden = _run(A.reveal_via, transition=name)
    assert ok is True, f"{name} did not complete"
    assert frames > 1, f"{name} presented no frames"
    assert hidden is False, f"{name} finished without the mark on screen"


@pytest.mark.parametrize("name", transitions_available())
def test_every_transition_works_as_an_exit(name):
    ok, frames, hidden = _run(A.hide_via, transition=name)
    assert ok is True, f"{name} did not complete"
    assert frames > 1
    assert hidden is True, f"{name} finished with the mark still there"


@pytest.mark.parametrize("name", A.treatments_available())
def test_every_offered_treatment_drives_over_a_plain_mark(name):
    ok, frames, hidden = _run(A.treatment_dwell, treatment=name)
    assert ok is True, f"{name} did not complete"
    assert frames > 1
    assert hidden is False, "a dwell hands the mark back"


def test_the_route_treatments_are_refused_rather_than_offered_broken():
    """RouteCircuit and PacketTrace need a mark's own stroke paths.

    They are excluded from `treatments_available` and raise a message that says why,
    which is the honest handling: a menu entry that cannot work is worse than an
    absent one, and a silent no-op is worse than both.
    """
    assert "RouteCircuit" not in A.treatments_available()
    assert "PacketTrace" not in A.treatments_available()
    with pytest.raises(RuntimeError, match="stroke paths"):
        _run(A.treatment_dwell, treatment="RouteCircuit")


def test_an_unknown_treatment_names_the_ones_that_exist():
    with pytest.raises(RuntimeError, match="VelvetSweep"):
        _run(A.treatment_dwell, treatment="VelvetSwep")


def test_an_unknown_transition_names_the_ones_that_exist():
    with pytest.raises(RuntimeError, match="Iris Snap"):
        _run(A.reveal_via, transition="Iris Snapp")


def test_a_content_driven_transition_is_refused_rather_than_offered_broken():
    """Drop from Sky animates a content Label through the display process.

    Its start() never calls the swap callback, so a mark handed to it simply stays
    hidden and the act reports success — the worst kind of failure. Excluded from the
    menu, and named as absent if asked for by name.
    """
    from scrollkit.effects.transitions import supported_names

    assert "Drop from Sky" in supported_names(), "it is still a valid transition_style"
    assert "Drop from Sky" not in transitions_available()
    with pytest.raises(RuntimeError, match="drive a mark"):
        _run(A.reveal_via, transition="Drop from Sky")


def test_wink_leaves_the_mark_up():
    ok, _frames, hidden = _run(A.wink_in, hold_seconds=0.05)
    assert ok is True
    assert hidden is False


def test_the_menu_is_bigger_than_the_functions_that_serve_it():
    """The whole point of the promotion, as an assertion.

    Seven act functions, but a visitor choosing from them has 40 distinct selections:
    each transition is a build AND an exit, and each treatment is its own dwell. A
    reference sign's thirty-seven acts were mostly this, written out longhand.
    """
    selectable = (2 * len(transitions_available())
                  + len(A.treatments_available())
                  + len(A.BUILDS) - 1        # reveal is counted above
                  + len(A.EXITS) - 1)        # hide is counted above
    assert len(A.supported_acts()) < 10
    assert selectable >= 35, selectable


# -- EXTRA_ARGS is declared, so it has to be checked -------------------------
#
# `_treatment_extras` used to read `inspect.signature(cls.__init__)`, which cannot
# drift but also cannot run: CircuitPython has no `inspect`, and the `except
# (TypeError, ValueError)` around it did not catch ImportError, so every entry point
# that calls it raised on the board. The declaration is the device-safe replacement;
# this is the test that keeps it honest.


def _required_positionals(cls):
    """Names of `__init__` params after (self, fx, theme) that have no default."""
    import inspect

    params = list(inspect.signature(cls.__init__).parameters.values())[3:]
    out = []
    for param in params:
        if param.default is not param.empty:
            break
        if param.kind in (param.VAR_POSITIONAL, param.VAR_KEYWORD):
            break
        out.append(param.name)
    return tuple(out)


@pytest.mark.parametrize("cls", TREATMENT_CLASSES, ids=lambda c: c.__name__)
def test_extra_args_matches_the_real_signature(cls):
    assert cls.EXTRA_ARGS == _required_positionals(cls), (
        "%s.EXTRA_ARGS is out of step with its own __init__" % cls.__name__)


def test_the_device_path_does_not_introspect_signatures():
    """The regression, as the board would meet it.

    Stubbing `inspect` out of __import__ is how this class of bug is testable at all
    without hardware: the simulator imports the same CPython stdlib the library is
    NOT allowed to rely on.
    """
    import builtins
    import sys

    real_import = builtins.__import__

    def no_inspect(name, *args, **kwargs):
        if name == "inspect":
            raise ImportError("no module named 'inspect'")
        return real_import(name, *args, **kwargs)

    saved = sys.modules.pop("inspect", None)
    builtins.__import__ = no_inspect
    try:
        assert len(A.treatments_available()) == 11
        assert len(A.selectable()) == 39
        assert A._treatment_extras(T.GradientDwell, RAMP) == (RAMP[0], RAMP[-1])
        assert A._treatment_extras(T.RouteCircuit, RAMP) is None
    finally:
        builtins.__import__ = real_import
        if saved is not None:
            sys.modules["inspect"] = saved
