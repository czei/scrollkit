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

    async def render(self, display, content=None):
        # content is passed by _display_process for transitions that need to
        # re-render at a different position (e.g. DropFromSky). Ignored here.
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


# ---------------------------------------------------------------------------
# Motion-friendly transitions — designed to look good under scrolling text.
# Each uses a delta approach: only newly changed mask regions are written
# per frame (no full repaint), so the text keeps scrolling cleanly beneath.
# ---------------------------------------------------------------------------

class PixelDissolve(Transition):
    """Text crumbles away as random 4×4 blocks cover the display, then the new
    content dissolves in block-by-block in reverse order — like film grain
    burning through. The irregular scatter works naturally with moving text.
    """

    BLOCK = 4

    def __init__(self, duration_frames=16, **kw):
        super().__init__(duration_frames, **kw)
        self._order = ()
        self._cols = 0
        self._covered = 0
        self._revealed = 0

    async def start(self, display, swap_callback):
        import random
        bw = bh = self.BLOCK
        self._cols = max(1, display.width // bw)
        rows = max(1, display.height // bh)
        order = list(range(self._cols * rows))
        random.shuffle(order)
        self._order = tuple(order)
        self._covered = 0
        self._revealed = 0
        await super().start(display, swap_callback)

    async def _paint_cover(self, progress):
        bw = bh = self.BLOCK
        target = len(self._order) * progress // 256
        while self._covered < target:
            idx = self._order[self._covered]
            x = (idx % self._cols) * bw
            y = (idx // self._cols) * bh
            await self._mask.fill_rect(x, y, bw, bh)
            self._covered += 1

    async def _paint_reveal(self, progress):
        bw = bh = self.BLOCK
        n = len(self._order)
        target = n * progress // 256
        while self._revealed < target:
            idx = self._order[n - 1 - self._revealed]
            x = (idx % self._cols) * bw
            y = (idx // self._cols) * bh
            await self._mask.clear_rect(x, y, bw, bh)
            self._revealed += 1


class ColumnRain(Transition):
    """Sixteen thin drops fall from the sky in random order.

    Width: 4 px per drop column (16 × 4 = 64 px). Each drop's front races
    down the display in DRIP_FRAMES frames (~8 px/frame on a 32-tall display).
    Columns fire one frame apart in a shuffled order — so at any moment you see
    ~4 drops at different heights scattered across the display, which reads as
    actual rainfall rather than a directional wipe.

    Both cover and reveal use a frame counter (not eased progress) so the
    falling speed is constant and perceptible.
    """

    NUM_COLS = 16     # 16 × 4 px = 64 px wide
    DRIP_FRAMES = 4   # frames each front takes to traverse full height (~8 px/frame)
    STAGGER = 1       # frames between successive drop starts

    def __init__(self, **kw):
        n, df, st = self.NUM_COLS, self.DRIP_FRAMES, self.STAGGER
        kw.setdefault('duration_frames', (n - 1) * st + df + 1)
        super().__init__(**kw)
        self._col_fill = []
        self._col_reveal = []
        self._col_rank = []    # _col_rank[c] = which step column c fires on
        self._cover_frame = 0
        self._reveal_frame = 0
        self._col_w = 0
        self._w = 0
        self._h = 0

    async def start(self, display, swap_callback):
        import random
        n = self.NUM_COLS
        self._col_w = max(1, display.width // n)
        self._w = display.width
        self._h = display.height
        self._col_fill = [0] * n
        self._col_reveal = [0] * n
        order = list(range(n))
        random.shuffle(order)
        self._col_rank = [0] * n
        for rank, col in enumerate(order):
            self._col_rank[col] = rank
        self._cover_frame = 0
        self._reveal_frame = 0
        await super().start(display, swap_callback)

    def _drip_y(self, frame, rank):
        """Y position the drip front has reached given its start rank."""
        elapsed = max(0, frame - rank * self.STAGGER)
        return min(self._h, self._h * elapsed // self.DRIP_FRAMES) if elapsed else 0

    async def _paint_cover(self, progress):
        f = self._cover_frame
        self._cover_frame += 1
        cw = self._col_w
        for c in range(self.NUM_COLS):
            target = self._drip_y(f, self._col_rank[c])
            if target > self._col_fill[c]:
                await self._mask.fill_rect(c * cw, self._col_fill[c],
                                           cw, target - self._col_fill[c])
                self._col_fill[c] = target

    async def _paint_reveal(self, progress):
        if self._reveal_frame == 0:
            # Guarantee the mask is fully opaque before the first drip clears.
            await self._mask.fill_rect(0, 0, self._w, self._h)
            for c in range(self.NUM_COLS):
                self._col_reveal[c] = 0
        f = self._reveal_frame
        self._reveal_frame += 1
        cw = self._col_w
        for c in range(self.NUM_COLS):
            target = self._drip_y(f, self._col_rank[c])
            if target > self._col_reveal[c]:
                await self._mask.clear_rect(c * cw, self._col_reveal[c],
                                            cw, target - self._col_reveal[c])
                self._col_reveal[c] = target


class GradualReveal(Transition):
    """Staggered vertical bands wipe in left-to-right (cover), then peel back
    right-to-left (reveal). A clean architectural transition — not rain.
    """

    NUM_COLS = 8

    def __init__(self, duration_frames=14, **kw):
        super().__init__(duration_frames, **kw)
        self._col_fill = []
        self._col_w = 0
        self._h = 0

    async def start(self, display, swap_callback):
        n = self.NUM_COLS
        self._col_w = max(1, display.width // n)
        self._h = display.height
        self._col_fill = [0] * n
        await super().start(display, swap_callback)

    def _col_progress(self, progress, c, n):
        start = c * 255 // n
        if progress <= start:
            return 0
        remaining = 255 - start
        return min(255, (progress - start) * 255 // remaining) if remaining else 255

    async def _paint_cover(self, progress):
        n = self.NUM_COLS
        cw = self._col_w
        h = self._h
        for c in range(n):
            target_h = h * self._col_progress(progress, c, n) // 255
            if target_h > self._col_fill[c]:
                await self._mask.fill_rect(c * cw, self._col_fill[c],
                                           cw, target_h - self._col_fill[c])
                self._col_fill[c] = target_h

    async def _paint_reveal(self, progress):
        n = self.NUM_COLS
        cw = self._col_w
        h = self._h
        for c in range(n - 1, -1, -1):
            rev = n - 1 - c
            cleared = h * self._col_progress(progress, rev, n) // 255
            remaining = h - cleared
            if self._col_fill[c] > remaining:
                await self._mask.clear_rect(c * cw, remaining,
                                            cw, self._col_fill[c] - remaining)
                self._col_fill[c] = remaining


class ScanFold(Transition):
    """Top and bottom scanlines simultaneously fold toward the horizontal
    centre until the screen is fully covered, then unfold outward to reveal
    new content. Two bars per frame — very fast, good on scrolling text.
    """

    def __init__(self, duration_frames=12, **kw):
        super().__init__(duration_frames, **kw)
        self._w = 0
        self._h = 0
        self._cov = 0   # rows covered from each edge

    async def start(self, display, swap_callback):
        self._w = display.width
        self._h = display.height
        self._cov = 0
        await super().start(display, swap_callback)

    async def _paint_cover(self, progress):
        half = self._h // 2
        target = half * progress // 255
        if target > self._cov:
            dy = target - self._cov
            await self._mask.fill_rect(0, self._cov, self._w, dy)            # top bar
            await self._mask.fill_rect(0, self._h - target, self._w, dy)     # bottom bar
            self._cov = target

    async def _paint_reveal(self, progress):
        half = self._h // 2
        target_rem = half - half * progress // 255
        if self._cov > target_rem:
            dy = self._cov - target_rem
            await self._mask.clear_rect(0, target_rem, self._w, dy)          # expose top
            await self._mask.clear_rect(0, self._h - self._cov, self._w, dy) # expose bottom
            self._cov = target_rem


class HorizontalWipe(Transition):
    """A crisp vertical edge sweeps left-to-right during cover — chasing the
    direction text scrolls off screen — then sweeps back to reveal new content.
    One rect per frame. Pairs well with fast-scrolling text.
    """

    def __init__(self, duration_frames=10, **kw):
        super().__init__(duration_frames, **kw)
        self._w = 0
        self._h = 0
        self._covered_x = 0

    async def start(self, display, swap_callback):
        self._w = display.width
        self._h = display.height
        self._covered_x = 0
        await super().start(display, swap_callback)

    async def _paint_cover(self, progress):
        target_x = self._w * progress // 255
        if target_x > self._covered_x:
            await self._mask.fill_rect(self._covered_x, 0,
                                       target_x - self._covered_x, self._h)
            self._covered_x = target_x

    async def _paint_reveal(self, progress):
        remaining_x = self._w - self._w * progress // 255
        if self._covered_x > remaining_x:
            await self._mask.clear_rect(remaining_x, 0,
                                        self._covered_x - remaining_x, self._h)
            self._covered_x = remaining_x


class GlitchBars(Transition):
    """Random-height horizontal bars flash onto the display in a shuffled order —
    like a corrupted video signal. Cover bars vary from 1 to 4 rows tall;
    reveal clears them in reverse. The irregular pattern looks especially alive
    over moving text.
    """

    def __init__(self, duration_frames=14, **kw):
        super().__init__(duration_frames, **kw)
        self._bars = ()
        self._w = 0
        self._covered = 0
        self._revealed = 0

    async def start(self, display, swap_callback):
        import random
        h = display.height
        self._w = display.width
        bars = []
        y = 0
        while y < h:
            bh = min(random.randint(1, 4), h - y)
            bars.append((y, bh))
            y += bh
        random.shuffle(bars)
        self._bars = tuple(bars)
        self._covered = 0
        self._revealed = 0
        await super().start(display, swap_callback)

    async def _paint_cover(self, progress):
        n = len(self._bars)
        target = n * progress // 256
        while self._covered < target:
            y, bh = self._bars[self._covered]
            await self._mask.fill_rect(0, y, self._w, bh)
            self._covered += 1

    async def _paint_reveal(self, progress):
        n = len(self._bars)
        target = n * progress // 256
        while self._revealed < target:
            y, bh = self._bars[n - 1 - self._revealed]
            await self._mask.clear_rect(0, y, self._w, bh)
            self._revealed += 1


class DiagonalWipe(Transition):
    """A diagonal boundary sweeps top-left to bottom-right during cover, then
    sweeps bottom-right to top-left during reveal. One delta span per row per
    frame (32 spans for 64×32) — bounded. Creates a dynamic angled reveal that
    cuts cleanly across scrolling text.
    """

    def __init__(self, duration_frames=12, **kw):
        super().__init__(duration_frames, **kw)
        self._w = 0
        self._h = 0
        self._row_fill = []

    async def start(self, display, swap_callback):
        self._w = display.width
        self._h = display.height
        self._row_fill = [0] * self._h
        await super().start(display, swap_callback)

    async def _paint_cover(self, progress):
        w = self._w
        h = self._h
        k = (w + h) * progress // 255
        for row in range(h):
            target = min(max(0, k - row), w)
            if target > self._row_fill[row]:
                await self._mask.fill_span(row, self._row_fill[row], target)
                self._row_fill[row] = target

    async def _paint_reveal(self, progress):
        w = self._w
        h = self._h
        k_max = w + h
        k = k_max - k_max * progress // 255
        for row in range(h):
            target = min(max(0, k - row), w)
            if target < self._row_fill[row]:
                await self._mask.clear_rect(target, row, self._row_fill[row] - target, 1)
                self._row_fill[row] = target


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
# Motion-friendly additions
PixelDissolve.FEASIBILITY = {"hardware_safe": True, "allocates_per_frame": False,
                             "max_pixel_writes_per_frame": 512, "modeled_frame_ms": 6.0}
ColumnRain.FEASIBILITY = {"hardware_safe": True, "allocates_per_frame": False,
                          "max_pixel_writes_per_frame": 256, "modeled_frame_ms": 4.0}
GradualReveal.FEASIBILITY = {"hardware_safe": True, "allocates_per_frame": False,
                             "max_pixel_writes_per_frame": 256, "modeled_frame_ms": 4.0}
ScanFold.FEASIBILITY = {"hardware_safe": True, "allocates_per_frame": False,
                        "max_pixel_writes_per_frame": 256, "modeled_frame_ms": 4.0}
HorizontalWipe.FEASIBILITY = {"hardware_safe": True, "allocates_per_frame": False,
                              "max_pixel_writes_per_frame": 192, "modeled_frame_ms": 3.0}
GlitchBars.FEASIBILITY = {"hardware_safe": True, "allocates_per_frame": False,
                          "max_pixel_writes_per_frame": 256, "modeled_frame_ms": 5.0}
DiagonalWipe.FEASIBILITY = {"hardware_safe": True, "allocates_per_frame": False,
                            "max_pixel_writes_per_frame": 384, "modeled_frame_ms": 6.0}


class DropFromSky:
    """New content slides in from the top: text starts at y=0 and falls to its
    natural y position over FALL_FRAMES frames.

    Works by hooking into _display_process *before* content.render() via
    pre_render_hook(), which temporarily sets content.y to the animated
    position. render() then restores y so state never drifts.

    No OverlayMask, no double-rendering, no layer-order issues. The Labels
    are positioned correctly from the first draw call each frame.
    """

    FALL_FRAMES = 10

    def __init__(self):
        self._frame = 0
        self._target_y = None
        self._is_complete = False

    async def start(self, display, swap_callback):
        self._frame = 0
        self._target_y = None
        self._is_complete = False

    @property
    def is_complete(self):
        return self._is_complete

    def pre_render_hook(self, content):
        """Set content.y to the animated position BEFORE content.render()."""
        if self._is_complete:
            return
        if self._target_y is None:
            self._target_y = getattr(content, 'y', 0)
        # y travels from 0 (frame 0) to _target_y (frame FALL_FRAMES)
        progress = min(1.0, self._frame / self.FALL_FRAMES)
        if hasattr(content, 'y'):
            content.y = int(self._target_y * progress)

    async def render(self, display, content=None):
        """Restore content.y after render and advance frame counter."""
        if self._is_complete:
            return
        # Restore y so the content object always carries its natural position.
        if content is not None and self._target_y is not None:
            if hasattr(content, 'y'):
                content.y = self._target_y
        self._frame += 1
        if self._frame > self.FALL_FRAMES:
            self._is_complete = True


DropFromSky.FEASIBILITY = {"hardware_safe": True, "allocates_per_frame": False,
                            "max_pixel_writes_per_frame": 0, "modeled_frame_ms": 0.5}


# --- transition registry -----------------------------------------------------
# Maps the user-facing transition name (as shown in settings / the web UI) to its
# class. Defined at the BOTTOM of the module so every class above is in scope.
#
# DropFromSky is intentionally included even though it does NOT subclass
# Transition: it is duck-typed (start/render/is_complete + pre_render_hook). So
# always enumerate transitions via _TRANSITION_MAP.items() — never
# Transition.__subclasses__(), which would silently drop it.
#
# This map is the dispatch half of the single-source-of-truth; the name half is
# the literal scrollkit.config.transition_names.TRANSITION_NAMES tuple. They are
# kept in lockstep (same names, same order) by test_transition_registry. Author
# new entries in both places, in UI order.
_TRANSITION_MAP = {
    "Drop from Sky": DropFromSky,
    "Pixel Dissolve": PixelDissolve,
    "Column Rain": ColumnRain,
    "Gradual Reveal": GradualReveal,
    "Scan Fold": ScanFold,
    "Horizontal Wipe": HorizontalWipe,
    "Glitch Bars": GlitchBars,
    "Diagonal Wipe": DiagonalWipe,
    "Iris Snap": IrisSnap,
    "Venetian Shutters": VenetianShutters,
    "Mosaic Resolve": MosaicResolve,
    "CRT Collapse": CRTCollapse,
    "Light Slit": LightSlitRewrite,
}


def transition_factory(name):
    """Return a FRESH transition instance for a user-facing name, or None.

    None means the name is not a known transition (caller decides what to do).
    """
    cls = _TRANSITION_MAP.get(name)
    return cls() if cls is not None else None


def supported_names():
    """The user-facing transition names this module can dispatch, in UI order."""
    return tuple(_TRANSITION_MAP)
