#!/usr/bin/env python3
"""ScrollKit demo (MEDIUM) — GOLDEN REFERENCE: write your own transition.

This is the canonical, copy-me example of a hardware-feasible transition. Read it
top to bottom: it shows the THREE things every transition must get right, and the
ONE command that proves it.

  1. Subclass ``Transition`` and implement ``_paint_cover`` / ``_paint_reveal``.
     The base class runs the lifecycle for you: COVER (mask 0 -> fully hidden),
     then your ``swap_callback`` fires ONCE while fully covered (so a glyph rebuild
     lands on a hidden frame), then REVEAL (hidden -> 0). ``progress`` is an eased
     0..255 through each phase.
  2. Do only BOUNDED, BULK work per frame. Paint into the preallocated
     ``OverlayMask`` with ``fill_rect`` / ``clear_rect`` (C bulk ops) — never a
     per-pixel Python loop over the panel, never an allocation on the hot path.
  3. Declare a ``FEASIBILITY`` budget on the CLASS (not the function — CircuitPython
     can't set attributes on function objects), so tooling can introspect the cost.

Then PROVE it — the real safety gate is not a plugin sandbox, it is the headless
feasibility harness. Run this demo with ``--strict`` to enforce the ~20 fps device
budget live::

    python demos/medium/golden_transition.py --strict

or check any transition in a one-liner::

    PYTHONPATH=src python -c "from scrollkit.dev import run_headless; ..."

If a transition allocates per frame or busts the 50 ms/frame budget, strict mode
raises ``FeasibilityError`` instead of letting it ship and crawl on the device.

To make a transition a SELECTABLE built-in, add its class to ``_TRANSITION_MAP`` in
``scrollkit/effects/transitions.py`` and its name to
``scrollkit/config/transition_names.py`` (a unit test enforces the two stay in
lockstep). A custom transition like this one is plugged into the loop by overriding
``_get_transition`` (see ``GoldenTransitionDemo`` below).
"""

import sys
import os

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    import _demo_support as _support
except (AttributeError, ImportError):
    _support = None

import asyncio

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import StaticText
from scrollkit.effects.transitions import Transition


class GoldenWipe(Transition):
    """A center-out bar wipe: a band grows from the middle to hide the screen, then
    shrinks back to reveal the new content. At most two bounded rects per frame.

    Deliberately the SIMPLEST useful transition so the mechanics are obvious. The
    shipped transitions (IrisSnap, MosaicResolve, ...) have the exact same shape
    with fancier per-frame patterns.
    """

    def __init__(self, duration_frames=8, **kw):
        # duration_frames is the length of EACH phase (cover, then reveal).
        super().__init__(duration_frames, **kw)
        self._w = 0
        self._h = 0
        self._covered = 0          # current half-width covered, in pixels

    async def start(self, display, swap_callback):
        # Capture panel size and reset state, THEN let the base allocate the mask.
        self._w = display.width
        self._h = display.height
        self._covered = 0
        await super().start(display, swap_callback)

    async def _paint_cover(self, progress):
        # progress: eased 0..255. Target half-width grows to w/2 at peak cover.
        target = (self._w // 2) * progress // 255
        if target > self._covered:                       # only paint the delta
            cx = self._w // 2
            grow = target - self._covered
            # cover the two newly-exposed margins — bounded C bulk fills, no loop.
            await self._mask.fill_rect(cx - target, 0, grow, self._h)
            await self._mask.fill_rect(cx + self._covered, 0, grow, self._h)
            self._covered = target

    async def _paint_reveal(self, progress):
        # Shrink the band back to 0, clearing (revealing) from the outside in.
        target = (self._w // 2) - (self._w // 2) * progress // 255
        if target < self._covered:                       # only clear the delta
            cx = self._w // 2
            shrink = self._covered - target
            await self._mask.clear_rect(cx - self._covered, 0, shrink, self._h)
            await self._mask.clear_rect(cx + target, 0, shrink, self._h)
            self._covered = target


# FEASIBILITY lives on the CLASS (CircuitPython can't attach it to a function).
# hardware_safe: holds 20 fps; allocates_per_frame: MUST be False; the modeled
# device cost is well under the 50 ms / 20 fps budget. ``run_headless(strict=True)``
# is what actually enforces this.
GoldenWipe.FEASIBILITY = {"hardware_safe": True, "allocates_per_frame": False,
                          "max_pixel_writes_per_frame": 2048, "modeled_frame_ms": 4.0}


class GoldenTransitionDemo(ScrollKitApp):
    """Cycles two messages, using GoldenWipe for every swap.

    The ONLY thing needed to drive a custom (unregistered) transition through the
    real display loop is to override ``_get_transition()`` to return it. Built-in
    transitions are instead selected by name via the ``transition_style`` setting.
    """

    def __init__(self):
        super().__init__(enable_web=False, update_interval=3600)

    async def create_display(self):
        if _support is not None:
            return _support.simulator_display(getattr(self, "opts", None))
        from scrollkit.display.simulator import SimulatorDisplay
        return SimulatorDisplay(width=64, height=32)

    async def setup(self):
        if hasattr(self.display, "create_window"):
            await self.display.create_window("ScrollKit - Golden Transition (medium)")
        # Two short-lived items so the queue keeps advancing and the wipe fires.
        self.content_queue.add(StaticText("ALPHA", x=18, y=20, duration=1.5))
        self.content_queue.add(StaticText("BRAVO", x=18, y=20, duration=1.5))

    def _get_transition(self):
        # Run our custom transition on every content swap.
        return GoldenWipe()


if __name__ == "__main__":
    if _support is not None:
        _support.main(GoldenTransitionDemo(),
                      "ScrollKit golden-transition reference (medium)")
    else:
        asyncio.run(GoldenTransitionDemo().run())
