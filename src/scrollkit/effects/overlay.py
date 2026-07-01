# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Preallocated overlay-mask layer (Phase 3 primitive; substrate for transitions).

One reusable indexed Bitmap (transparent index 0) + Palette + TileGrid, added as a
display layer composited ABOVE content. A whole class of transitions becomes
"write a small pattern into the mask": cover regions with an opaque index, reveal
by setting them back to transparent. Allocated ONCE; every mutation touches only
dirty spans via the C bulk ops in ``display.gfx.bitmaptools`` — never a full-2048
Python loop, never a per-frame allocation. Runs unchanged on device and simulator.
"""


__all__ = ['OverlayMask']

class OverlayMask:
    """A reusable full-screen mask layer for cover -> swap -> reveal transitions.

    Index 0 is transparent (underlying content shows through); indices 1..N are
    opaque cover colors (index 1 defaults to black). Build once, reuse across
    transitions (``clear()`` resets it); ``detach()`` removes the layer.
    """

    def __init__(self, display, value_count=4):
        self._display = display
        gfx = display.gfx
        self._gfx = gfx
        self._w = display.width
        self._h = display.height
        self.bitmap = gfx.Bitmap(self._w, self._h, value_count)
        self.palette = gfx.Palette(value_count)
        self.palette.make_transparent(0)       # index 0 = transparent
        if value_count > 1:
            self.palette[1] = 0x000000          # default opaque cover = black
        self.tilegrid = gfx.TileGrid(self.bitmap, pixel_shader=self.palette)
        display.add_layer(self.tilegrid)

    # --- palette --------------------------------------------------------------
    def set_cover_color(self, index, color):
        """Set the color of an opaque cover index (1..N)."""
        self.palette[index] = color

    # --- bounded mutators (dirty-span only) -----------------------------------
    def _clip(self, x, y, w, h):
        x0 = x if x > 0 else 0
        y0 = y if y > 0 else 0
        x1 = x + w
        y1 = y + h
        if x1 > self._w:
            x1 = self._w
        if y1 > self._h:
            y1 = self._h
        if x1 < x0:
            x1 = x0
        if y1 < y0:
            y1 = y0
        return x0, y0, x1, y1

    def _account(self, kind, px):
        pm = getattr(self._display, "_perf", None)
        if pm is not None:
            pm.account_bulk_op(kind, px)

    async def fill_rect(self, x, y, w, h, index=1):
        """Cover a clipped rectangle with an opaque ``index`` via a C bulk op."""
        x0, y0, x1, y1 = self._clip(x, y, w, h)
        if x1 > x0 and y1 > y0:
            self._gfx.bitmaptools.fill_region(self.bitmap, x0, y0, x1, y1, index)
            self._account("fill_region", (x1 - x0) * (y1 - y0))

    async def fill_span(self, y, x0, x1, index=1):
        """Cover the single-row span ``[x0, x1)``."""
        await self.fill_rect(x0, y, x1 - x0, 1, index)

    async def clear_rect(self, x, y, w, h):
        """Reveal a clipped rectangle (set back to transparent index 0)."""
        await self.fill_rect(x, y, w, h, 0)

    async def clear(self):
        """Reset the whole mask to transparent (one bulk fill). Reusable."""
        self.bitmap.fill(0)
        self._account("fill_region", self._w * self._h)

    async def blit_pattern(self, x, y, pattern_bitmap, *, skip_index=0):
        """Stamp a small pattern bitmap into the mask (transparent ``skip_index``)."""
        self._gfx.bitmaptools.blit(self.bitmap, pattern_bitmap, x, y,
                                   skip_index=skip_index)
        self._account("blit", pattern_bitmap.width * pattern_bitmap.height)

    # --- lifecycle ------------------------------------------------------------
    def detach(self):
        """Remove the mask's layer from the display."""
        self._display.remove_layer(self.tilegrid)
