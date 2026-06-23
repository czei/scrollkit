"""Theatrical transitions on the overlay-mask primitive (Class 2 — fresh start).

The broken Wipe/Slide/Fade transitions were removed in the showcase cleanup; this
module is their proper replacement, built on :class:`OverlayMask`: cover the old
content, swap content while it is fully hidden, then reveal the new content.
Bounded mask writes per frame (no full-2048 Python loop), no per-frame allocation,
strict-feasible at 20 fps.

This file ships the full Class 2 pack on the shared :class:`Transition` base:
:class:`IrisSnap`, :class:`VenetianShutters`, :class:`MosaicResolve`,
:class:`CRTCollapse`, and :class:`LightSlitRewrite`. Each writes only a bounded set
of mask spans/blocks per frame.
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


class VenetianShutters(Transition):
    """Coarse horizontal bands that close (cover) then open (reveal) like blinds,
    each band staggered slightly for a mechanical feel. Per frame writes at most
    ``bands`` (+1) spans — bounded, never a full repaint.
    """

    def __init__(self, duration_frames=12, curve=EASE_IN_OUT, cover_color=0x000000,
                 bands=8):
        super().__init__(duration_frames, curve, cover_color)
        self.bands = max(2, bands)
        self._w = 0
        self._h = 0
        self._band_h = 1
        self._spread = 0

    async def start(self, display, swap_callback):
        self._w = display.width
        self._h = display.height
        self._band_h = (self._h + self.bands - 1) // self.bands
        # A small per-band delay so the bands don't all move in lockstep, scaled so
        # the last band still reaches full at progress 255.
        self._spread = max(1, 255 // (self.bands * 3))
        await super().start(display, swap_callback)

    def _band_progress(self, progress, k):
        denom = 255 - (self.bands - 1) * self._spread
        if denom < 1:
            denom = 1
        p = progress - k * self._spread
        if p < 0:
            p = 0
        p = p * 255 // denom
        if p > 255:
            p = 255
        return ease(self.curve, p)

    async def _paint_cover(self, progress):
        m = self._mask
        await m.clear()
        for k in range(self.bands):
            h = self._band_progress(progress, k) * self._band_h // 255
            if h > 0:
                top = k * self._band_h + (self._band_h - h) // 2
                await m.fill_rect(0, top, self._w, h, 1)

    async def _paint_reveal(self, progress):
        m = self._mask
        await m.fill_rect(0, 0, self._w, self._h, 1)   # fully covered...
        for k in range(self.bands):                    # ...open each band from its center
            h = self._band_progress(progress, k) * self._band_h // 255
            if h > 0:
                top = k * self._band_h + (self._band_h - h) // 2
                await m.clear_rect(0, top, self._w, h)


class MosaicResolve(Transition):
    """Blocks cover (then reveal) in a fixed pseudo-random order — a mosaic that
    dissolves in and out. Only the *newly* changed blocks are written each frame
    (~4-12), so per-frame work stays bounded. Deterministic given ``seed``.
    """

    def __init__(self, duration_frames=14, curve=EASE_IN_OUT, cover_color=0x000000,
                 block_w=8, block_h=4, seed=1):
        super().__init__(duration_frames, curve, cover_color)
        self.block_w = max(1, block_w)
        self.block_h = max(1, block_h)
        self.seed = seed
        self._cols = 0
        self._rows = 0
        self._order = ()
        self._covered = 0
        self._revealed = 0

    async def start(self, display, swap_callback):
        self._cols = max(1, display.width // self.block_w)
        self._rows = max(1, display.height // self.block_h)
        n = self._cols * self._rows
        # Fisher-Yates shuffle with a seeded LCG (integer state — no per-frame alloc).
        order = list(range(n))
        state = (self.seed * 2654435761 + 1) & 0x7FFFFFFF
        for i in range(n - 1, 0, -1):
            state = (state * 1103515245 + 12345) & 0x7FFFFFFF
            j = state % (i + 1)
            order[i], order[j] = order[j], order[i]
        self._order = tuple(order)
        self._covered = 0
        self._revealed = 0
        await super().start(display, swap_callback)

    def _block_rect(self, idx):
        r = idx // self._cols
        c = idx % self._cols
        return c * self.block_w, r * self.block_h, self.block_w, self.block_h

    async def _paint_cover(self, progress):
        target = ease(self.curve, progress) * len(self._order) // 255
        while self._covered < target:
            x, y, w, h = self._block_rect(self._order[self._covered])
            await self._mask.fill_rect(x, y, w, h, 1)
            self._covered += 1

    async def _paint_reveal(self, progress):
        target = ease(self.curve, progress) * len(self._order) // 255
        while self._revealed < target:
            x, y, w, h = self._block_rect(self._order[self._revealed])
            await self._mask.clear_rect(x, y, w, h)
            self._revealed += 1


class CRTCollapse(Transition):
    """A CRT power-off: the picture collapses to a center scanline (cover) then
    blooms back open from that line (reveal). Two growing/shrinking bars per frame
    — bounded.
    """

    def __init__(self, duration_frames=10, curve=EASE_IN_OUT, cover_color=0x000000):
        super().__init__(duration_frames, curve, cover_color)
        self._w = 0
        self._h = 0

    async def start(self, display, swap_callback):
        self._w = display.width
        self._h = display.height
        await super().start(display, swap_callback)

    async def _paint_cover(self, progress):
        m = self._mask
        await m.clear()
        half = self._h // 2
        covered = ease(self.curve, progress) * half // 255
        if covered > 0:
            await m.fill_rect(0, 0, self._w, covered, 1)               # top bar down
            await m.fill_rect(0, self._h - covered, self._w, covered, 1)  # bottom bar up
        # At full progress make sure the thin center line is closed too.
        if progress >= 255:
            await m.fill_rect(0, 0, self._w, self._h, 1)

    async def _paint_reveal(self, progress):
        m = self._mask
        await m.fill_rect(0, 0, self._w, self._h, 1)                   # fully covered...
        slit = ease(self.curve, progress) * self._h // 255            # ...bloom open from center
        if slit > 0:
            await m.clear_rect(0, (self._h - slit) // 2, self._w, slit)


class LightSlitRewrite(Transition):
    """A bright vertical scanner sweeps across, covering the old content on its way
    out and revealing the new content on its way back — the swap happens behind the
    slit at the turn. Per frame: a cover/clear span + the bright slit — bounded.
    """

    def __init__(self, duration_frames=12, curve=EASE_IN_OUT, cover_color=0x000000,
                 slit_px=3, slit_color=0xFFFFFF):
        super().__init__(duration_frames, curve, cover_color)
        self.slit_px = max(1, slit_px)
        self.slit_color = slit_color
        self._w = 0
        self._h = 0

    async def start(self, display, swap_callback):
        self._w = display.width
        self._h = display.height
        await super().start(display, swap_callback)
        self._mask.set_cover_color(2, self.slit_color)   # index 2 = the bright slit

    async def _paint_cover(self, progress):
        m = self._mask
        await m.clear()
        x = ease(self.curve, progress) * self._w // 255          # slit leading edge
        if x > 0:
            await m.fill_rect(0, 0, x, self._h, 1)               # cover everything passed
        await m.fill_rect(x, 0, self.slit_px, self._h, 2)        # the bright slit

    async def _paint_reveal(self, progress):
        m = self._mask
        await m.fill_rect(0, 0, self._w, self._h, 1)             # start fully covered
        x = ease(self.curve, progress) * self._w // 255
        if x > 0:
            await m.clear_rect(0, 0, x, self._h)                 # reveal what the slit passed
        await m.fill_rect(x, 0, self.slit_px, self._h, 2)        # the bright slit


# --- advertised feasibility metadata (US7 / FR-026) -------------------------
# hardware_safe: passes the strict gate at 20 fps; allocates_per_frame: MUST be
# False (no per-frame heap alloc); max_pixel_writes_per_frame: worst-case bounded
# mask write, all via the C bulk painter (never a 2048-px Python loop);
# modeled_frame_ms: <= the 50 ms (20 fps) device budget. On a 64x32 panel a full
# mask cover is 2048 px done as ONE bulk fill_region (~0.6 ms), not a loop.
IrisSnap.FEASIBILITY = {"hardware_safe": True, "allocates_per_frame": False,
                        "max_pixel_writes_per_frame": 2048, "modeled_frame_ms": 7.0}
VenetianShutters.FEASIBILITY = {"hardware_safe": True, "allocates_per_frame": False,
                                "max_pixel_writes_per_frame": 2048, "modeled_frame_ms": 8.0}
MosaicResolve.FEASIBILITY = {"hardware_safe": True, "allocates_per_frame": False,
                             "max_pixel_writes_per_frame": 512, "modeled_frame_ms": 6.0}
CRTCollapse.FEASIBILITY = {"hardware_safe": True, "allocates_per_frame": False,
                           "max_pixel_writes_per_frame": 2048, "modeled_frame_ms": 8.0}
LightSlitRewrite.FEASIBILITY = {"hardware_safe": True, "allocates_per_frame": False,
                                "max_pixel_writes_per_frame": 2048, "modeled_frame_ms": 8.0}
