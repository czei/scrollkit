# Copyright (c) 2024-2026 Michael Czeiszperger
"""Shared display-graphics primitives (mixed into Simulator + Unified displays).

One code path, both platforms. Provides:
- ``GraphicsContext`` (``display.gfx``): the platform-resolved Bitmap / Palette /
  TileGrid / Group / bitmaptools, built once and cached.
- The content/layer group split (D11): ``_content_group`` (Labels + fill, emptied
  per frame) sits BELOW ``_layer_group`` (overlay-mask / bitmap-text / paint
  canvas, persistent across frames), so an effect layer can never be hidden by
  per-frame label churn.
- Bounded span/rect painters (``fill_rect`` / ``fill_span`` / ``clear_rect``) that
  write a persistent full-screen paint canvas through ``bitmaptools.fill_region``
  (a C bulk op) — never a full-2048 Python loop — and account the cost.
- The shared per-frame surface: ``clear()`` (label-slot reset + paint wipe),
  ``set_pixel()`` (a 1x1 ``fill_rect`` into the paint canvas, so pixels survive
  the displayio re-render on BOTH platforms — this is what the particle system
  renders through) and ``fill()`` (a cached full-screen background TileGrid at
  the bottom of the content group). One implementation, hardware == simulator.
- ``measure_text`` via real font glyph advances (not ``len(text) * 6``).

CircuitPython-safe: no runtime ``typing``, no desktop-only imports here.
"""


class GraphicsContext:
    """Platform-resolved graphics primitives, held by reference (no allocation).

    Built once per display in ``initialize()`` and returned by ``display.gfx`` so
    effects build bitmaps/palettes/tilegrids and run C bulk ops through ONE code
    path. On CircuitPython these are the real built-ins; on desktop they are the
    ``scrollkit.simulator`` equivalents (including the ``bitmaptools`` shim).
    """

    __slots__ = ("Bitmap", "Palette", "TileGrid", "Group", "bitmaptools")

    def __init__(self, Bitmap, Palette, TileGrid, Group, bitmaptools):
        self.Bitmap = Bitmap
        self.Palette = Palette
        self.TileGrid = TileGrid
        self.Group = Group
        self.bitmaptools = bitmaptools


def _glyph_advance(glyph):
    """Pull the horizontal advance from a glyph (dict or object), or None."""
    if glyph is None:
        return None
    if isinstance(glyph, dict):
        for key in ("dx", "shift_x", "width"):
            if key in glyph and glyph[key] is not None:
                return glyph[key]
        return None
    for key in ("dx", "shift_x", "width"):
        val = getattr(glyph, key, None)
        if val is not None:
            return val
    return None


class GraphicsMixin:
    """Mixed into the display implementations. Expects the subclass to provide
    ``self._width``, ``self._height``, ``self.font``, ``self._perf`` and to call
    ``_init_graphics()`` from ``initialize()`` once ``self.main_group`` exists."""

    PAINT_VALUE_COUNT = 256

    # --- setup ----------------------------------------------------------------
    def _init_graphics(self, displayio_mod, bitmaptools_mod):
        """Create the content/layer sub-groups inside main_group and cache gfx.

        Call from ``initialize()`` after ``self.main_group`` is created and set as
        the display's root group.
        """
        self._content_group = displayio_mod.Group()
        self._layer_group = displayio_mod.Group()
        self.main_group.append(self._content_group)   # below
        self.main_group.append(self._layer_group)     # above
        self._gfx = GraphicsContext(
            displayio_mod.Bitmap, displayio_mod.Palette, displayio_mod.TileGrid,
            displayio_mod.Group, bitmaptools_mod)
        # The full-screen paint canvas is created lazily on the first painter call
        # so apps that never paint pay nothing.
        self._paint_bitmap = None
        self._paint_palette = None
        self._paint_tile = None
        self._paint_colors = None
        # Full-screen background for fill(), also lazy (one Bitmap/Palette/
        # TileGrid ever — the palette color is mutated per call, never realloc'd).
        self._bg_bitmap = None
        self._bg_palette = None
        self._bg_tile = None

    # --- gfx ------------------------------------------------------------------
    @property
    def gfx(self):
        """The cached :class:`GraphicsContext` (identity-stable; no per-access alloc)."""
        gfx = getattr(self, "_gfx", None)
        if gfx is None:
            raise RuntimeError("display.gfx is unavailable until initialize() runs")
        return gfx

    # --- layers (D11) ---------------------------------------------------------
    def add_layer(self, tilegrid):
        """Composite ``tilegrid`` above all content (idempotent)."""
        lg = getattr(self, "_layer_group", None)
        if lg is None:
            return
        for i in range(len(lg)):
            if lg[i] is tilegrid:
                return
        lg.append(tilegrid)

    def remove_layer(self, tilegrid):
        """Remove a layer added via :meth:`add_layer` (idempotent)."""
        lg = getattr(self, "_layer_group", None)
        if lg is None:
            return
        for i in range(len(lg)):
            if lg[i] is tilegrid:
                lg.pop(i)
                return

    # --- bounded painters -----------------------------------------------------
    def _ensure_paint(self):
        if self._paint_bitmap is not None:
            return
        gfx = self.gfx
        bm = gfx.Bitmap(self._width, self._height, self.PAINT_VALUE_COUNT)
        pal = gfx.Palette(self.PAINT_VALUE_COUNT)
        if hasattr(pal, "make_transparent"):
            pal.make_transparent(0)          # unpainted shows underlying content
        tile = gfx.TileGrid(bm, pixel_shader=pal)
        self._paint_bitmap = bm
        self._paint_palette = pal
        self._paint_tile = tile
        self._paint_colors = {}              # 0xRRGGBB -> palette index (0 reserved)
        self.add_layer(tile)

    def _paint_index(self, color):
        idx = self._paint_colors.get(color)
        if idx is not None:
            return idx
        idx = len(self._paint_colors) + 1
        if idx >= self.PAINT_VALUE_COUNT:
            # Palette saturated: reuse the last slot for this color WITHOUT caching
            # it, so the most recently painted color is always the correct one
            # (caching here would alias several colors to one mutable slot).
            idx = self.PAINT_VALUE_COUNT - 1
            self._paint_palette[idx] = color
            return idx
        self._paint_palette[idx] = color
        self._paint_colors[color] = idx
        return idx

    def _clip_rect(self, x, y, w, h):
        x0 = x if x > 0 else 0
        y0 = y if y > 0 else 0
        x1 = x + w
        y1 = y + h
        if x1 > self._width:
            x1 = self._width
        if y1 > self._height:
            y1 = self._height
        if x1 < x0:
            x1 = x0
        if y1 < y0:
            y1 = y0
        return x0, y0, x1, y1

    def _account_bulk(self, x0, y0, x1, y1):
        pm = getattr(self, "_perf", None)
        if pm is not None:
            pm.account_bulk_op("fill_region", (x1 - x0) * (y1 - y0))

    async def fill_rect(self, x, y, w, h, color):
        """Fill the clipped rectangle with ``color`` via a C bulk op."""
        self._ensure_paint()
        idx = self._paint_index(color)
        x0, y0, x1, y1 = self._clip_rect(x, y, w, h)
        if x1 > x0 and y1 > y0:
            self.gfx.bitmaptools.fill_region(self._paint_bitmap, x0, y0, x1, y1, idx)
            self._account_bulk(x0, y0, x1, y1)

    async def fill_span(self, y, x0, x1, color):
        """Fill the single-row span ``[x0, x1)`` with ``color``."""
        await self.fill_rect(x0, y, x1 - x0, 1, color)

    async def clear_rect(self, x, y, w, h):
        """Clear the clipped rectangle back to transparent via a C bulk op."""
        self._ensure_paint()
        x0, y0, x1, y1 = self._clip_rect(x, y, w, h)
        if x1 > x0 and y1 > y0:
            self.gfx.bitmaptools.fill_region(self._paint_bitmap, x0, y0, x1, y1, 0)
            self._account_bulk(x0, y0, x1, y1)

    # --- the shared per-frame surface (one code path, both platforms) ---------
    def _hide_unused_labels(self):
        """Hide pooled Labels that weren't drawn this frame (frame drew fewer)."""
        pool = getattr(self, "_label_pool", None) or ()
        for i in range(getattr(self, "_label_idx", 0), len(pool)):
            lbl = pool[i]
            if hasattr(lbl, "hidden"):
                lbl.hidden = True
        pool = getattr(self, "_scaled_pool", None) or ()
        for i in range(getattr(self, "_scaled_idx", 0), len(pool)):
            lbl = pool[i]
            if hasattr(lbl, "hidden"):
                lbl.hidden = True

    async def clear(self):
        """Clear the display (start a new frame).

        Resets the per-frame Label slot indices so draw_text() reuses pooled
        Labels instead of allocating (labels not redrawn this frame are hidden
        in show()), wipes the bounded-painter canvas so fill_rect()/set_pixel()
        drawings don't ghost across frames (immediate-mode, one C bulk fill),
        and hides the fill() background. Persistent effect layers live in
        _layer_group and are deliberately NOT touched. No per-pixel loops, no
        raw-matrix writes: the displayio refresh in show() re-renders the whole
        group each frame on both platforms.
        """
        self._label_idx = 0
        self._scaled_idx = 0
        if getattr(self, "_paint_bitmap", None) is not None:
            self._paint_bitmap.fill(0)
        if getattr(self, "_bg_tile", None) is not None:
            self._bg_tile.hidden = True

    async def set_pixel(self, x, y, color):
        """Set a single foreground pixel (drawn on top of other content).

        A 1x1 fill_rect into the persistent paint-canvas LAYER, so the pixel is
        part of the displayio tree and survives show()'s re-render on hardware
        AND desktop (a raw matrix write would be wiped by refresh, and the
        hardware matrix has no pixel API at all). This is the primitive the
        particle system renders through; each write is a bounded C bulk op that
        the hardware feasibility model accounts for.
        """
        if getattr(self, "_gfx", None) is None:
            return   # not initialized yet — mirror the old silent no-op
        if 0 <= x < self._width and 0 <= y < self._height:
            await self.fill_rect(x, y, 1, 1, color)

    def _ensure_bg(self):
        gfx = self.gfx
        if self._bg_bitmap is None:
            self._bg_bitmap = gfx.Bitmap(self._width, self._height, 1)
            self._bg_palette = gfx.Palette(1)
            self._bg_tile = gfx.TileGrid(self._bg_bitmap,
                                         pixel_shader=self._bg_palette)
            # Bottom of the CONTENT group: behind every label, below the
            # persistent effect layers. Inserted once; fill()/clear() toggle
            # .hidden and mutate the palette — never another allocation.
            self._content_group.insert(0, self._bg_tile)

    async def fill(self, color):
        """Fill the display background with a solid color (behind labels).

        Immediate-mode like draw_text(): lasts until the next clear(). Backed
        by one cached full-screen TileGrid whose 1-entry palette is mutated per
        call — no per-frame allocation, works identically on hardware and
        desktop (the old paths wrote to the raw matrix, which the hardware
        wrapper doesn't expose and the desktop refresh wiped).
        """
        if getattr(self, "_gfx", None) is None or self._content_group is None:
            return
        self._ensure_bg()
        self._bg_palette[0] = color
        self._bg_tile.hidden = False

    # --- measurement ----------------------------------------------------------
    def measure_text(self, text, font=None):
        """Rendered pixel width from summed font glyph advances (not ``len*6``).

        Empty string is 0; a missing/advance-less glyph contributes the font's
        space advance (else a documented 6). A font with no ``get_glyph`` API
        falls back to a coarse ``len*6`` estimate (last resort).
        """
        if not text:
            return 0
        if font is None:
            font = getattr(self, "font", None)
        get = getattr(font, "get_glyph", None) if font is not None else None
        if get is None:
            return len(text) * 6
        try:
            repl = _glyph_advance(get(" "))
        except Exception:
            repl = None
        if repl is None:
            repl = 6
        total = 0
        for ch in text:
            try:
                adv = _glyph_advance(get(ch))
            except Exception:
                adv = None
            total += adv if adv is not None else repl
        return total
