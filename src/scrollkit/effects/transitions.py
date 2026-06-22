"""Theatrical transitions on the overlay-mask primitive (Class 2 — fresh start).

The broken Wipe/Slide/Fade transitions were removed in the showcase cleanup; this
module is their proper replacement, built on :class:`OverlayMask`: cover the old
content, swap content while it is fully hidden, then reveal the new content.
Bounded mask writes per frame (no full-2048 Python loop), no per-frame allocation,
strict-feasible at 20 fps.

This file currently ships the **IrisSnap proving spike** for the foundation; the
rest of the Class 2 pack (venetian shutters, mosaic resolve, CRT collapse,
light-slit rewrite) lands in its own feature on top of this same base.
"""

from .easing import ease, EASE_IN_OUT
from .overlay import OverlayMask


class Transition:
    """Base cover -> swap-while-covered -> reveal transition over an OverlayMask.

    Two phases of ``duration_frames`` each: the cover phase drives mask coverage
    0 -> full, then ``swap_callback`` runs ONCE while fully covered (so any glyph
    rebuild it triggers lands on a hidden frame), then the reveal phase drives
    coverage full -> 0. Subclasses implement ``_paint_cover`` / ``_paint_reveal``.
    """

    def __init__(self, duration_frames=12, curve=EASE_IN_OUT, cover_color=0x000000):
        self.half = max(1, duration_frames)
        self.curve = curve
        self.cover_color = cover_color
        self._frame = 0
        self._mask = None
        self._swap = None
        self._swapped = False
        self._is_complete = False

    async def start(self, display, swap_callback):
        """Begin the transition. ``swap_callback`` runs once, while fully covered."""
        if self._mask is not None:        # don't leak a prior mask's layer
            self._mask.detach()
        self._mask = OverlayMask(display)
        self._mask.set_cover_color(1, self.cover_color)
        self._swap = swap_callback
        self._frame = 0
        self._swapped = False
        self._is_complete = False
        await self._mask.clear()

    async def render(self, display):
        if self._is_complete:
            return
        if self._frame < self.half:
            await self._paint_cover(self._progress(self._frame))
        else:
            if not self._swapped:
                await self._run_swap()
                self._swapped = True
            await self._paint_reveal(self._progress(self._frame - self.half))
        self._frame += 1
        if self._frame >= self.half * 2:
            await self._mask.clear()      # fully revealed
            self._mask.detach()           # remove the mask layer (no leak)
            self._is_complete = True

    async def _run_swap(self):
        if self._swap is None:
            return
        res = self._swap()
        if hasattr(res, "__await__"):     # support sync or async swap callbacks
            await res

    def _progress(self, f):
        """Eased 0..255 progress through one phase."""
        raw = 0 if self.half <= 1 else min(255, f * 255 // (self.half - 1))
        return ease(self.curve, raw)

    @property
    def is_complete(self):
        return self._is_complete

    @property
    def fully_covered(self):
        """True at the cover/reveal boundary (mask hides all content)."""
        return self._frame == self.half

    def detach(self):
        """Remove the transition's overlay layer from the display."""
        if self._mask is not None:
            self._mask.detach()

    # subclasses implement (progress 0->255):
    async def _paint_cover(self, progress):   # uncovered -> covered
        raise NotImplementedError

    async def _paint_reveal(self, progress):  # covered -> revealed
        raise NotImplementedError


class IrisSnap(Transition):
    """Chunky diamond aperture. A diamond of cover grows to hide the screen, then a
    diamond hole grows to reveal it. Per frame writes at most ``height`` spans,
    driven by a precomputed per-row radius table — bounded, never a full repaint.
    """

    def __init__(self, duration_frames=10, curve=EASE_IN_OUT, cover_color=0x000000):
        super().__init__(duration_frames, curve, cover_color)
        self._w = 0
        self._h = 0
        self._cx = 0
        self._dy = ()       # per-row |y - cy|: the radius->span lookup table
        self._rmax = 1

    async def start(self, display, swap_callback):
        self._w = display.width
        self._h = display.height
        self._cx = self._w // 2
        cy = self._h // 2
        self._dy = tuple(abs(y - cy) for y in range(self._h))
        self._rmax = (self._w // 2) + (self._h // 2) + 1
        await super().start(display, swap_callback)

    def _radius(self, progress):
        return (progress * self._rmax) // 255

    async def _paint_cover(self, progress):
        m = self._mask
        await m.clear()
        r = self._radius(progress)
        cx = self._cx
        for y in range(self._h):
            hw = r - self._dy[y]
            if hw >= 0:
                await m.fill_span(y, cx - hw, cx + hw + 1, 1)

    async def _paint_reveal(self, progress):
        m = self._mask
        await m.fill_rect(0, 0, self._w, self._h, 1)   # cover everything...
        r = self._radius(progress)
        cx = self._cx
        for y in range(self._h):                       # ...then punch the diamond hole
            hw = r - self._dy[y]
            if hw >= 0:
                await m.clear_rect(cx - hw, y, 2 * hw + 1, 1)
