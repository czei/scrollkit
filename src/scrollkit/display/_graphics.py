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
