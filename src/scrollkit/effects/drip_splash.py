# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Drip-splash animation — LEDs drip in from an edge (default the top) into place.

The inverse of :func:`scrollkit.effects.show_reveal_splash`.  The screen starts
blank; every lit pixel of the target image appears at the top of its column
(y=0) and falls straight down, one row at a time, until it reaches its
destination row — where it stops.  Pixels accumulate column-by-column until the
full text/image is assembled.

Within a column the *bottom-most* target launches first, so a higher-stopping
drop can never overtake an already-settled one.  This preserves gaps (the holes
in a ``:`` or the space between glyphs) with no per-drop collision checks.

Each frame is one cheap whole-bitmap ``fill(0)`` (a single C call, ~9 µs on the
MatrixPortal S3) followed by a per-pixel write for every visible drop — far
cheaper than per-region bulk ops for sparse moving pixels.  A drop's position is
a pure function of the frame number, so there is no per-frame allocation and no
clear/redraw bookkeeping.

The overlay's background (index 0) is **transparent**, so a drip composites over
whatever else is on screen (e.g. a scrolling label) rather than blacking it out.
Uses ``display.gfx`` (the same graphics context :class:`OverlayMask` uses) rather
than a bare ``import displayio``, so the simulator's displayio is used on desktop
and the hardware one on CircuitPython.

Two ways to use it:

* :func:`show_drip_splash` — a blocking convenience for setup-time splashes; it
  runs the whole animation, holds, and removes the overlay.
* :class:`DripReveal` — a *frame-driven* core for use inside a running display
  loop (call :meth:`DripReveal.step` once per frame).  After it completes you can
  leave the overlay in place so the assembled image stays on screen as the live
  content, then update the value by starting a fresh ``DripReveal``.

Typical usage::

    from scrollkit.effects import show_drip_splash, pixels_from_text

    px = pixels_from_text("PIXEL", x=17, y=8)
    px += pixels_from_text("RAIN", x=20, y=20)
    await show_drip_splash(display, px, color=0x00CCFF)
"""

import asyncio


class DripReveal:
    """Frame-driven drip-in of a fixed set of target pixels from an edge.

    Build it with the target ``pixels`` (e.g. from :func:`pixels_from_font_text`)
    and a ``direction`` ("top" default — drops fall down; or "bottom"/"left"/"right"
    to enter from that edge), call :meth:`start` once with the display, then
    :meth:`step` once per frame.
    :meth:`step` renders the current frame into a transparent overlay and returns
    ``True`` when the image is fully assembled.  The overlay persists until
    :meth:`detach` is called, so a completed reveal can stay on screen as the live
    image (the assembled pixels are exactly the target pixels — there is nothing
    to swap in).
    """

    _DIRECTIONS = ("top", "bottom", "left", "right")

    def __init__(self, pixels, color=0xFFFF00, fall_speed=1, stagger=2, direction="top"):
        self.pixels = pixels
        self.color = color
        self.fall_speed = fall_speed if fall_speed > 1 else 1
        self.stagger = stagger if stagger > 0 else 0
        # Edge the drops enter from: "top" (default, fall down), "bottom" (rise up),
        # "left" (slide right), or "right" (slide left). Top keeps the original look.
        self.direction = direction if direction in self._DIRECTIONS else "top"
        self._display = None
        self._bitmap = None
        self._tile = None
        self._drops = []
        self._last_frame = 0
        self._frame = 0
        self._started = False
        self._w = 0
        self._h = 0

    def start(self, display):
        """Create the transparent overlay layer and compute the drop schedule."""
        gfx = display.gfx
        w, h = display.width, display.height
        self._w, self._h = w, h
        self._bitmap = gfx.Bitmap(w, h, 2)
        palette = gfx.Palette(2)
        palette.make_transparent(0)          # composite over content below
        palette[1] = self.color
        self._tile = gfx.TileGrid(self._bitmap, pixel_shader=palette)
        display.add_layer(self._tile)
        self._display = display

        # Group pixels by the FIXED axis (the column for top/bottom, the row for
        # left/right); each drop travels along the other axis from the entry edge to
        # its target. The pixel that travels FARTHEST in a group launches first so a
        # drop never has to pass a settled one (gaps preserved, no collision checks).
        vertical = self.direction in ("top", "bottom")
        from_low = self.direction in ("top", "left")   # enters from coordinate 0
        span = h if vertical else w
        groups = {}
        for (x, y) in self.pixels:
            if 0 <= x < w and 0 <= y < h:
                fixed = x if vertical else y
                target = y if vertical else x
                groups.setdefault(fixed, []).append(target)
        drops = []
        last_frame = 0
        for fixed, targets in groups.items():
            targets.sort(reverse=from_low)             # farthest-travelling first
            for k, t in enumerate(targets):
                launch = k * self.stagger
                drops.append((fixed, t, launch))
                dist = t if from_low else (span - 1 - t)
                settle = launch + (dist + self.fall_speed - 1) // self.fall_speed
                if settle > last_frame:
                    last_frame = settle
        self._drops = drops
        self._last_frame = last_frame
        self._frame = 0
        self._started = True

    @property
    def has_pixels(self):
        """True if there is anything to drip (start() must run first)."""
        return bool(self._drops)

    @property
    def is_complete(self):
        """True once every drop has reached its target."""
        return self._started and self._frame > self._last_frame

    def step(self):
        """Render the current frame into the overlay and advance one frame.

        Does NOT call ``display.show()`` — the caller (or the display loop) owns
        that.  Returns ``True`` when the reveal is complete.
        """
        if not self._started or self.is_complete:
            return True
        b = self._bitmap
        f = self._frame
        fs = self.fall_speed
        try:
            b.fill(0)
        except (AttributeError, TypeError):
            for xx in range(self._w):
                for yy in range(self._h):
                    b[xx, yy] = 0
        vertical = self.direction in ("top", "bottom")
        from_low = self.direction in ("top", "left")
        span = self._h if vertical else self._w
        for (fixed, t, launch) in self._drops:
            if f < launch:
                continue                     # not released yet
            moved = (f - launch) * fs
            if from_low:
                cur = moved if moved < t else t          # 0 -> t, then settled
            else:
                cur = (span - 1) - moved
                if cur < t:
                    cur = t                              # max -> t, then settled
            if vertical:
                b[fixed, cur] = 1
            else:
                b[cur, fixed] = 1
        self._frame += 1
        return self.is_complete

    def detach(self):
        """Remove the overlay layer from the display (no-op if already gone)."""
        if self._display is not None and self._tile is not None:
            self._display.remove_layer(self._tile)
            self._tile = None


async def show_drip_splash(
    display,
    pixels,
    color=0xFFFF00,
    fall_speed=1,
    stagger=2,
    hold_seconds=2.0,
    direction="top",
):
    """Play a drip-in animation on ``display`` (blocking convenience wrapper).

    Every pixel in ``pixels`` enters from one edge (the top by default — drops fall
    down their column) and settles at its target position; the assembled image then
    holds for ``hold_seconds`` before the overlay is removed.  Built on
    :class:`DripReveal`.

    Args:
        display:      A ScrollKit display (``UnifiedDisplay``/``SimulatorDisplay``).
        pixels:       Iterable of ``(x, y)`` tuples — the target image.  Build one
                      with :func:`pixels_from_text` / :func:`pixels_from_font_text`
                      or supply pixel art.
        color:        24-bit RGB color of the drops (default: yellow 0xFFFF00).
        fall_speed:   Rows a drop descends per frame (>=1).  Higher = faster fall.
        stagger:      Frames between successive drops launching in the same
                      column (>=0).  Higher = a sparser, more deliberate drip;
                      0 launches a whole column at once.
        hold_seconds: Seconds to hold the finished image before finishing.
        direction:    Edge the drops enter from — ``"top"`` (default, fall down),
                      ``"bottom"`` (rise up), ``"left"`` (slide right), or ``"right"``
                      (slide left).

    Returns:
        ``True`` when the animation finished normally; ``False`` if it was cut
        short because the display reported a close (the simulator window was
        closed).  On hardware ``show()`` never reports a close, so this is
        always ``True`` there.  Callers that loop the effect can stop on
        ``False``.
    """
    reveal = DripReveal(pixels, color=color, fall_speed=fall_speed, stagger=stagger,
                        direction=direction)
    reveal.start(display)
    if not reveal.has_pixels:
        reveal.detach()
        return True

    while not reveal.is_complete:
        reveal.step()
        if await display.show() is False:    # simulator window closed
            reveal.detach()
            return False
        await asyncio.sleep(0.02)

    await asyncio.sleep(hold_seconds)
    reveal.detach()
    return True


# --- advertised feasibility metadata (US7 / FR-026) -------------------------
# Per frame: one whole-bitmap C fill (~9 us) + one per-pixel write per launched
# drop (~7 us each). Total writes are bounded by the lit-pixel count of the
# image (a few hundred for typical text), so even a dense 512-px image is
# ~9 us + 512*7 us ~= 3.6 ms — well inside the 50 ms (20 fps) budget. No
# per-frame allocation (the drop list is built once; positions are recomputed).
# NOTE: FEASIBILITY is attached to the CLASS only. CircuitPython/MicroPython does
# not allow setting attributes on function objects, so the convenience wrapper
# does NOT carry it (callers read DripReveal.FEASIBILITY). Setting it on a
# function crashes `import scrollkit.effects` on-device.
_FEASIBILITY = {
    "hardware_safe": True,
    "allocates_per_frame": False,
    "max_pixel_writes_per_frame": 512,
    "modeled_frame_ms": 4.0,
}
DripReveal.FEASIBILITY = _FEASIBILITY
