"""Palette-animated bitmap text (Class 3 — the proving spike for the foundation).

A ScrollKit-native fixed-cell 5x7 font is rendered ONCE into an indexed Bitmap
whose lit pixels carry palette *indices* (a colour-ramp position). The text scrolls
by moving a TileGrid; the animation comes from rewriting a few palette entries each
frame — near-zero per-frame pixel work and NO glyph rebuild. Runs unchanged on
device and simulator via ``display.gfx``.

This ships the minimal ``BitmapText`` + ``RainbowChase`` proving the foundation
API; the full font and the other palette effects (neon-tube crawl, chrome sheen,
hazard stripes) land in their own feature.
"""

from .content import DisplayContent, LOOP_FPS

# Minimal 5x7 glyph subset (enough for the proving messages). Each glyph is 7 rows
# of a 5-char mask ('#' = lit). Stored compactly; missing chars render blank.
_GLYPHS = {
    " ": ["     ", "     ", "     ", "     ", "     ", "     ", "     "],
    "A": [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
    "C": [" ### ", "#   #", "#    ", "#    ", "#    ", "#   #", " ### "],
    "E": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    "I": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"],
    "K": ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    "N": ["#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "R": ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    "S": [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    "W": ["#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"],
}

GLYPH_W = 5
GLYPH_H = 7
CELL_W = GLYPH_W + 1     # one column of spacing between glyphs

# Colour ramp for the rainbow-chase animation (indices 1..RAMP in the palette;
# index 0 is the transparent background).
RAMP = 6
_RAINBOW = (0xFF0000, 0xFF7F00, 0xFFFF00, 0x00FF00, 0x0000FF, 0x8B00FF)


def _glyph(ch):
    return _GLYPHS.get(ch.upper())


class RainbowChase:
    """Palette effect: rotate the colour ramp so a rainbow travels through the
    letters. Pure palette rewrites — no glyph rebuild. ``period`` advances the
    phase every N frames (>1 = a calmer, slower chase)."""

    def __init__(self, step=1, period=1):
        self.step = step
        self.period = period if period > 1 else 1
        self._phase = 0
        self._tick = 0

    def apply(self, palette):
        for i in range(RAMP):
            palette[1 + i] = _RAINBOW[(i + self._phase) % RAMP]
        self._tick += 1
        if self._tick >= self.period:
            self._tick = 0
            self._phase = (self._phase + self.step) % RAMP


class BitmapText(DisplayContent):
    """A message rendered once into an indexed bitmap, scrolled via a TileGrid,
    with an optional per-frame palette effect."""

    def __init__(self, text, y=0, palette_effect=None, scroll_speed=30,
                 max_width_px=192, priority=2):
        super().__init__(duration=None, priority=priority)
        self.text = text
        self.y = y
        self.palette_effect = palette_effect if palette_effect is not None else RainbowChase()
        self.scroll_speed = scroll_speed
        self.max_width_px = max_width_px
        self._built = False
        self._display = None
        self._bitmap = None
        self._palette = None
        self._tile = None
        self._pos_q = 0          # 1/16-px scroll accumulator
        self._width = 0

    def _delta_q(self):
        return int(round(self.scroll_speed * 16 / LOOP_FPS))

    def _build(self, display):
        gfx = display.gfx
        width = min(self.max_width_px, max(1, len(self.text) * CELL_W))
        self._width = width
        bitmap = gfx.Bitmap(width, GLYPH_H, RAMP + 1)
        palette = gfx.Palette(RAMP + 1)
        palette.make_transparent(0)              # background transparent
        for i in range(RAMP):
            palette[1 + i] = _RAINBOW[i]
        # Render every glyph ONCE; each lit pixel's palette index is its column
        # position in the ramp, so rotating the palette makes the colour chase.
        cx = 0
        for ch in self.text:
            rows = _glyph(ch)
            if rows is not None:
                for ry in range(GLYPH_H):
                    row = rows[ry]
                    for rx in range(GLYPH_W):
                        ax = cx + rx
                        if ax < width and row[rx] != " ":
                            bitmap[ax, ry] = (ax % RAMP) + 1
            cx += CELL_W
            if cx >= width:
                break
        tile = gfx.TileGrid(bitmap, pixel_shader=palette)
        tile.x = display.width                   # start off the right edge
        tile.y = self.y
        display.add_layer(tile)
        self._bitmap = bitmap
        self._palette = palette
        self._tile = tile
        self._pos_q = display.width << 4
        self._built = True

    async def render(self, display):
        self._display = display                  # remembered so stop() can detach
        if not self._built:
            self._build(display)                 # one-time (frame 0)
        # Animate by rewriting palette entries — NO glyph rebuild, ~zero pixel work.
        if self.palette_effect is not None:
            self.palette_effect.apply(self._palette)
        # Scroll by moving the TileGrid.
        self._pos_q -= self._delta_q()
        self._tile.x = self._pos_q >> 4
        if (self._pos_q >> 4) < -self._width:
            self._pos_q = display.width << 4     # loop the scroll

    @property
    def is_complete(self):
        return False

    async def stop(self):
        """Remove the bitmap-text layer when the content is taken off the queue."""
        await super().stop()
        if getattr(self, "_display", None) is not None:
            self.detach(self._display)
            self._display = None

    def detach(self, display):
        if self._tile is not None:
            display.remove_layer(self._tile)
