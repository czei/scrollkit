# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Palette-animated bitmap text (Class 3 — the proving spike for the foundation).

A ScrollKit-native fixed-cell 5x7 font is rendered ONCE into an indexed Bitmap
whose lit pixels carry palette *indices* (a colour-ramp position). The text scrolls
by moving a TileGrid; the animation comes from rewriting a few palette entries each
frame — near-zero per-frame pixel work and NO glyph rebuild. Runs unchanged on
device and simulator via ``display.gfx``.

This ships ``BitmapText`` plus the full palette-animation set (rainbow chase, neon
tube crawl, chrome sheen, hazard stripes) and the complete printable-ASCII 5x7 font.
"""

from .content import DisplayContent, LOOP_FPS
from .colors import scale as _scale, spectrum, gradient

# Full printable-ASCII 5x7 font (table-driven; no BDF). Each glyph is 7 rows of a
# 5-char mask ('#' = lit). Missing chars render blank. Lookup folds to upper-case.
FONT_5x7 = {
    " ": ["     ", "     ", "     ", "     ", "     ", "     ", "     "],
    "A": [" ### ", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "B": ["#### ", "#   #", "#   #", "#### ", "#   #", "#   #", "#### "],
    "C": [" ### ", "#   #", "#    ", "#    ", "#    ", "#   #", " ### "],
    "D": ["#### ", "#   #", "#   #", "#   #", "#   #", "#   #", "#### "],
    "E": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#####"],
    "F": ["#####", "#    ", "#    ", "#### ", "#    ", "#    ", "#    "],
    "G": [" ### ", "#   #", "#    ", "# ###", "#   #", "#   #", " ### "],
    "H": ["#   #", "#   #", "#   #", "#####", "#   #", "#   #", "#   #"],
    "I": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"],
    "J": ["  ###", "   # ", "   # ", "   # ", "#  # ", "#  # ", " ##  "],
    "K": ["#   #", "#  # ", "# #  ", "##   ", "# #  ", "#  # ", "#   #"],
    "L": ["#    ", "#    ", "#    ", "#    ", "#    ", "#    ", "#####"],
    "M": ["#   #", "## ##", "# # #", "#   #", "#   #", "#   #", "#   #"],
    "N": ["#   #", "##  #", "# # #", "#  ##", "#   #", "#   #", "#   #"],
    "O": [" ### ", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "P": ["#### ", "#   #", "#   #", "#### ", "#    ", "#    ", "#    "],
    "Q": [" ### ", "#   #", "#   #", "#   #", "# # #", "#  # ", " ## #"],
    "R": ["#### ", "#   #", "#   #", "#### ", "# #  ", "#  # ", "#   #"],
    "S": [" ####", "#    ", "#    ", " ### ", "    #", "    #", "#### "],
    "T": ["#####", "  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "  #  "],
    "U": ["#   #", "#   #", "#   #", "#   #", "#   #", "#   #", " ### "],
    "V": ["#   #", "#   #", "#   #", "#   #", "#   #", " # # ", "  #  "],
    "W": ["#   #", "#   #", "#   #", "# # #", "# # #", "## ##", "#   #"],
    "X": ["#   #", "#   #", " # # ", "  #  ", " # # ", "#   #", "#   #"],
    "Y": ["#   #", "#   #", " # # ", "  #  ", "  #  ", "  #  ", "  #  "],
    "Z": ["#####", "    #", "   # ", "  #  ", " #   ", "#    ", "#####"],
    "0": [" ### ", "#   #", "#  ##", "# # #", "##  #", "#   #", " ### "],
    "1": ["  #  ", " ##  ", "  #  ", "  #  ", "  #  ", "  #  ", "#####"],
    "2": [" ### ", "#   #", "    #", "   # ", "  #  ", " #   ", "#####"],
    "3": ["#####", "   # ", "  #  ", "   # ", "    #", "#   #", " ### "],
    "4": ["   # ", "  ## ", " # # ", "#  # ", "#####", "   # ", "   # "],
    "5": ["#####", "#    ", "#### ", "    #", "    #", "#   #", " ### "],
    "6": [" ### ", "#    ", "#    ", "#### ", "#   #", "#   #", " ### "],
    "7": ["#####", "    #", "   # ", "  #  ", " #   ", " #   ", " #   "],
    "8": [" ### ", "#   #", "#   #", " ### ", "#   #", "#   #", " ### "],
    "9": [" ### ", "#   #", "#   #", " ####", "    #", "    #", " ### "],
    "!": ["  #  ", "  #  ", "  #  ", "  #  ", "  #  ", "     ", "  #  "],
    "?": [" ### ", "#   #", "    #", "   # ", "  #  ", "     ", "  #  "],
    ".": ["     ", "     ", "     ", "     ", "     ", " ##  ", " ##  "],
    ",": ["     ", "     ", "     ", "     ", "     ", "  #  ", " #   "],
    ":": ["     ", "  #  ", "  #  ", "     ", "  #  ", "  #  ", "     "],
    ";": ["     ", "  #  ", "  #  ", "     ", "  #  ", "  #  ", " #   "],
    "'": ["  #  ", "  #  ", "     ", "     ", "     ", "     ", "     "],
    '"': [" # # ", " # # ", "     ", "     ", "     ", "     ", "     "],
    "-": ["     ", "     ", "     ", "#####", "     ", "     ", "     "],
    "+": ["     ", "  #  ", "  #  ", "#####", "  #  ", "  #  ", "     "],
    "=": ["     ", "     ", "#####", "     ", "#####", "     ", "     "],
    "_": ["     ", "     ", "     ", "     ", "     ", "     ", "#####"],
    "/": ["    #", "    #", "   # ", "  #  ", " #   ", "#    ", "#    "],
    "\\": ["#    ", "#    ", " #   ", "  #  ", "   # ", "    #", "    #"],
    "*": ["     ", " # # ", "  #  ", "#####", "  #  ", " # # ", "     "],
    "#": [" # # ", " # # ", "#####", " # # ", "#####", " # # ", " # # "],
    "%": ["##  #", "##  #", "   # ", "  #  ", " #   ", "#  ##", "#  ##"],
    "&": [" ##  ", "#  # ", "#  # ", " ##  ", "# # #", "#  # ", " ## #"],
    "@": [" ### ", "#   #", "# ###", "# # #", "# ###", "#    ", " ### "],
    "$": ["  #  ", " ####", "# #  ", " ### ", "  # #", "#### ", "  #  "],
    "(": ["  #  ", " #   ", "#    ", "#    ", "#    ", " #   ", "  #  "],
    ")": ["  #  ", "   # ", "    #", "    #", "    #", "   # ", "  #  "],
    "<": ["   # ", "  #  ", " #   ", "#    ", " #   ", "  #  ", "   # "],
    ">": [" #   ", "  #  ", "   # ", "    #", "   # ", "  #  ", " #   "],
}

# Backwards-compatible alias for the table.
_GLYPHS = FONT_5x7

GLYPH_W = 5
GLYPH_H = 7
CELL_W = GLYPH_W + 1     # one column of spacing between glyphs

# Colour resolution of the palette effects. RAMP is how many palette slots BitmapText
# animates, so it sets how smoothly a gradient spreads across the letters — wider ==
# smoother (still pure palette rewrites: no per-frame allocation and zero PIXEL writes,
# so feasibility is unchanged). 16 is a smooth spread that stays well inside the panel's
# 4-bit-per-channel (4096-colour) reality. (Index 0 is the transparent background.)
RAMP = 16
# A smooth full-spectrum hue wheel of RAMP stops, built ONCE at import (zero per-frame
# cost). Replaces the old six fixed primaries, so rainbow text sweeps the whole spectrum
# instead of stepping through six blocks.
_RAINBOW = spectrum(RAMP)

# Public ramp + a tiny chase helper, so content can use the SAME flowing rainbow as
# the palette effects without the legacy EffectsEngine.get_rainbow_color().
RAINBOW = _RAINBOW


def rainbow_color(step):
    """A flowing rainbow colour for integer ``step`` (wraps around the ramp)."""
    return _RAINBOW[step % RAMP]


def _glyph(ch):
    return FONT_5x7.get(ch.upper())


# Brightness curves for the single-hue palette effects, GENERATED at RAMP length so
# they scale with the palette resolution (no hard-coded 6-tuples to fall out of sync
# when RAMP changes). Built once when the effect is constructed.
def _ramp_profile(n):
    """A dark -> full brightness curve of length ``n`` (sheen: dim base to highlight)."""
    if n <= 1:
        return (1.0,)
    lo = 0.12
    return tuple(lo + (1.0 - lo) * i / (n - 1) for i in range(n))


def _peak_profile(n):
    """A dim -> bright -> dim brightness curve of length ``n`` (mono-chase highlight)."""
    if n <= 1:
        return (1.0,)
    lo = 0.12
    return tuple(lo + (1.0 - lo) * (1.0 - abs(2.0 * i / (n - 1) - 1.0))
                 for i in range(n))


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


class NeonTubeCrawl:
    """A bright pulse crawls along an otherwise-dim neon tube of one colour: one ramp
    slot glows at full ``color`` while the rest hold a dimmed version of it. Pass
    ``glow``/``base`` to set the two shades directly instead. Pure palette rewrites —
    no glyph rebuild. ``period`` advances the pulse every N frames."""

    def __init__(self, color=0x66FFCC, glow=None, base=None, period=2):
        self.glow = glow if glow is not None else color
        self.base = base if base is not None else _scale(color, 0.18)
        self.period = period if period > 1 else 1
        self._phase = 0
        self._tick = 0

    def apply(self, palette):
        for i in range(RAMP):
            palette[1 + i] = self.glow if i == self._phase else self.base
        self._tick += 1
        if self._tick >= self.period:
            self._tick = 0
            self._phase = (self._phase + 1) % RAMP


class ChromeSheen:
    """A metallic sheen: a dark→bright ramp of ``color`` (default silver/white) with a
    highlight band that sweeps across the letters as the ramp rotates. Pass
    ``highlight`` to make the sheen a smooth TWO-colour gradient (dim ``color`` → full
    ``highlight``, e.g. steel-blue → white) instead of a single-hue brightness ramp.
    Pure palette rewrites — no glyph rebuild."""

    # brightness profile, dark -> full; the highlight sits at the bright end. Generated
    # at RAMP length so the gradient stays smooth as the palette resolution widens.
    _PROFILE = _ramp_profile(RAMP)

    def __init__(self, color=0xFFFFFF, highlight=None, period=1):
        self.color = color
        self.highlight = highlight
        self.period = period if period > 1 else 1
        if highlight is None:
            self._ramp = tuple(_scale(color, f) for f in self._PROFILE)
        else:
            # dim base of `color` -> full `highlight`: a smooth two-colour sheen ramp.
            self._ramp = gradient(_scale(color, self._PROFILE[0]), highlight, RAMP)
        self._phase = 0
        self._tick = 0

    def apply(self, palette):
        for i in range(RAMP):
            palette[1 + i] = self._ramp[(i + self._phase) % RAMP]
        self._tick += 1
        if self._tick >= self.period:
            self._tick = 0
            self._phase = (self._phase + 1) % RAMP


class HazardStripes:
    """Marching hazard stripes: an accent ``color`` alternating with a ``dark`` ground,
    shifting one slot each step. Pass ``a``/``b`` to set the two colours directly.
    Pure palette rewrites — no glyph rebuild."""

    def __init__(self, color=0xFFCC00, dark=0x101010, a=None, b=None, period=2):
        self.a = a if a is not None else color
        self.b = b if b is not None else dark
        self.period = period if period > 1 else 1
        self._phase = 0
        self._tick = 0

    def apply(self, palette):
        for i in range(RAMP):
            palette[1 + i] = self.a if ((i + self._phase) % 2 == 0) else self.b
        self._tick += 1
        if self._tick >= self.period:
            self._tick = 0
            self._phase = (self._phase + 1) % 2


class MonoChase:
    """A single bright band of one ``color`` chases through the letters — RainbowChase,
    but monochrome (one hue at varying brightness). Pure palette rewrites — no glyph
    rebuild. ``period`` advances the chase every N frames."""

    # a brightness peak (dim -> bright -> dim) that sweeps around the ramp. Generated at
    # RAMP length so the sweep stays smooth as the palette resolution widens.
    _PROFILE = _peak_profile(RAMP)

    def __init__(self, color=0xFFFFFF, period=1):
        self.color = color
        self.period = period if period > 1 else 1
        self._ramp = tuple(_scale(color, f) for f in self._PROFILE)
        self._phase = 0
        self._tick = 0

    def apply(self, palette):
        for i in range(RAMP):
            palette[1 + i] = self._ramp[(i + self._phase) % RAMP]
        self._tick += 1
        if self._tick >= self.period:
            self._tick = 0
            self._phase = (self._phase + 1) % RAMP


# Content pairing: palette effects animate the colours of bitmap text, so they read
# well whether the text is held static or scrolling (surfaced in capabilities()/docs).
RainbowChase.PAIRS_WITH = ("static", "scrolling")
NeonTubeCrawl.PAIRS_WITH = ("static", "scrolling")
ChromeSheen.PAIRS_WITH = ("static", "scrolling")
HazardStripes.PAIRS_WITH = ("static", "scrolling")
MonoChase.PAIRS_WITH = ("static", "scrolling")

_PALETTE_EFFECTS = (RainbowChase, NeonTubeCrawl, ChromeSheen, HazardStripes, MonoChase)


def palette_effects_for(presentation):
    """The palette-effect CLASSES suited to `presentation` ('static' | 'scrolling').

    Each returned class is used as ``BitmapText(text, palette_effect=cls())``. These
    animate colour over bitmap text and read well static or scrolling. Reads the live
    PAIRS_WITH tags, so it stays current as palette effects are added or retagged.

        cls = random.choice(palette_effects_for("scrolling"))
        app.content_queue.add(BitmapText("OPEN", palette_effect=cls()))
    """
    return tuple(cls for cls in _PALETTE_EFFECTS
                 if presentation in getattr(cls, "PAIRS_WITH", ()))


class BitmapText(DisplayContent):
    """A message rendered once into an indexed bitmap, scrolled via a TileGrid,
    with an optional per-frame palette effect."""

    def __init__(self, text, y=0, palette_effect=None, scroll_speed=30,
                 max_width_px=192, priority=2, complete_after_passes=None):
        """Args (beyond the obvious):

            complete_after_passes: if set (e.g. 1), ``is_complete`` becomes True
                after the text has fully scrolled across that many times, so the
                banner can advance a ContentQueue instead of looping forever.
                Default None keeps the persistent-banner behaviour (never
                completes on its own). Completion is keyed on SCROLL POSITION, not
                wall-clock, so a heavy concurrent effect that drops the frame rate
                can't end a pass early (cutting the text off mid-scroll).
        """
        super().__init__(duration=None, priority=priority)
        self.text = text
        self.y = y
        self.palette_effect = palette_effect if palette_effect is not None else RainbowChase()
        self.scroll_speed = scroll_speed
        self.max_width_px = max_width_px
        self.complete_after_passes = complete_after_passes
        self._passes = 0         # full scroll passes completed (frame-based)
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

    async def start(self):
        """Reset so the layer is rebuilt and pass-completion replays when this
        content cycles back through a ContentQueue.

        The library's previous BitmapText never reset ``_built``, so a banner that
        was ``stop()``-ed (which detaches its TileGrid) would not re-add the layer
        when shown again — it went invisible on the second cycle. Rebuilding on
        each start() makes it queue-safe.
        """
        await super().start()
        self._built = False
        self._passes = 0

    async def render(self, display):
        self._display = display                  # remembered so stop() can detach
        was_built = self._built
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
            # The wrap (position jumping back to the right edge) marks one full
            # pass. Counted from scroll POSITION (frame-based), not wall-clock, so
            # a low frame rate never ends a pass early. Skip the build frame.
            if was_built:
                self._passes += 1

    @property
    def is_complete(self):
        if self._is_complete:
            return True
        if self.complete_after_passes is not None:
            return self._passes >= self.complete_after_passes
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


# --- advertised feasibility metadata (US7 / FR-026) -------------------------
# The glyph bitmap is rendered ONCE; animation is pure palette rewrites (<= RAMP
# entries) and scrolling moves the TileGrid.x — so per-frame PIXEL writes are zero
# and there is no per-frame allocation. Strict-feasible at 20 fps.
BitmapText.FEASIBILITY = {"hardware_safe": True, "allocates_per_frame": False,
                          "max_pixel_writes_per_frame": 0, "modeled_frame_ms": 5.0}
