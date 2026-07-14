# Copyright (c) 2024-2026 Michael Czeiszperger
"""Swirl entrance: sprites spiral in around a center onto their targets.

Each sprite enters far offscreen at its target's polar angle plus a
``swirl`` of extra arc, then eases inward and unwinds onto its exact
target position — staggered, so a word assembles as a rotating spiral.

NOT a named Transition on purpose: ``transition_factory(name)`` must
construct transitions with zero content knowledge, and a swirl inherently
needs a per-sprite target list. Use it directly, like
:class:`scrollkit.effects.swarm_reveal.SwarmReveal`:

    entries = [(tile, x, y, w, h) for ...]
    swirl = SwirlIn(entries)
    while not swirl.is_complete:
        swirl.step()
        await display.show()

It owns no layers (the caller's tiles are moved in place, un-hidden at
each sprite's stagger onset, and left exactly on target), so there is no
start/detach. Promoted from the DarkOwl LED logo app (2026).
"""

import math

__all__ = ["SwirlIn"]


def _ease_out_cubic(t):
    """Cubic ease-out on t in 0..1 (the source app's flight curve)."""
    inv = 1.0 - t
    return 1.0 - inv * inv * inv


class SwirlIn:
    """Frame-driven spiral assembly of positioned sprites.

    Args:
        entries:            Sequence of ``(tile, target_x, target_y, w, h)``
                            — the sprite, its final position, and its size
                            (used to spiral the sprite's CENTER).
        center:             ``(cx, cy)`` the spiral's pivot.
        entry_radius:       Radius sprites enter at (offscreen).
        swirl:              Extra radians of arc unwound on the way in.
        frames_per_sprite:  Frames each sprite's flight takes.
        stagger:            Frames between consecutive sprites' onsets.
    """

    FEASIBILITY = {
        "hardware_safe": True,
        "allocates_per_frame": False,
        "max_pixel_writes_per_frame": 0,
        "modeled_frame_ms": 1.0,
        "note": "2 trig calls + one tile move per sprite per frame",
    }

    def __init__(self, entries, center=(31.5, 15.0), entry_radius=46.0,
                 swirl=2.4, frames_per_sprite=34, stagger=6):
        cx, cy = center
        self._cx = cx
        self._cy = cy
        self._r0 = entry_radius
        self._swirl = swirl
        self._per = frames_per_sprite
        self._entries = []
        for i, (tile, tx, ty, w, h) in enumerate(entries):
            tcx = tx + w / 2.0
            tcy = ty + h / 2.0
            dx = tcx - cx
            dy = tcy - cy
            r1 = math.sqrt(dx * dx + dy * dy)
            a1 = math.atan2(dy, dx)
            self._entries.append((tile, tx, ty, w, h, r1, a1, i * stagger))
        last_start = (len(self._entries) - 1) * stagger if self._entries else 0
        self._total = frames_per_sprite + last_start
        self._frame = 0
        self._complete = not self._entries

    @property
    def is_complete(self):
        return self._complete

    def step(self):
        """Advance one frame; move every active sprite. True when done."""
        if self._complete:
            return True
        f = self._frame
        for tile, tx, ty, w, h, r1, a1, begin in self._entries:
            if f < begin:
                continue
            t = f - begin
            if t >= self._per:
                tile.x, tile.y = tx, ty       # snapped exactly on target
                tile.hidden = False
                continue
            e = _ease_out_cubic(min(1.0, t / self._per))
            r = self._r0 + (r1 - self._r0) * e
            a = a1 + self._swirl * (1.0 - e)
            tile.x = int(round(self._cx + r * math.cos(a) - w / 2.0))
            tile.y = int(round(self._cy + r * math.sin(a) - h / 2.0))
            tile.hidden = False
        self._frame = f + 1
        if self._frame > self._total:
            for tile, tx, ty, _w, _h, _r1, _a1, _b in self._entries:
                tile.x, tile.y = tx, ty       # pixel-exact final placement
                tile.hidden = False
            self._complete = True
        return self._complete
