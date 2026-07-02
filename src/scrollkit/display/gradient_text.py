# Copyright (c) 2024-2026 Michael Czeiszperger
"""Static directional gradient / palette text fill (indexed-bitmap renderer).

When ``StaticText`` / ``ScrollingText`` are given a ``palette``, their glyphs are
rasterised ONCE — through the shared :func:`~scrollkit.display.text_pixels.\
pixels_from_font_text` helper, so the *real* display font (terminalio by default)
is preserved — into an indexed ``Bitmap`` whose every lit pixel carries a palette
*index* equal to its position along the chosen axis. The text then shows / scrolls
by moving a ``TileGrid``: no glyph rebuild and **zero per-frame pixel writes**,
exactly like ``BitmapText``. The difference is that the palette here is a FIXED
ramp (a static gradient), not a per-frame animation — animated colour stays the
distinct concern of ``BitmapText`` + ``palette_effect``.

A displayio ``Label`` is physically one colour (a 2-entry indexed bitmap), so this
indexed-bitmap path is the only way to colour the normal font per-pixel. Runs
unchanged on the simulator and on CircuitPython via ``display.gfx`` (integer-only;
no per-frame allocation).
"""

from .colors import gradient, multi_gradient
from .text_fill import clamp_palette_steps, normalize_direction
from .text_pixels import font_text_ascent, font_text_width, pixels_from_font_text

__all__ = ["GradientTextLayer"]

# The Label path positions a line's baseline at screen row ``y + 4`` (the
# simulator's adafruit_display_text.Label applies a device-compat offset so the
# sim matches hardware). pixels_from_font_text rasterises with the run's baseline
# `ascent` rows below the top, so placing tile.y = y + 4 - ascent puts that
# baseline on the Label's baseline. The `ascent` term then cancels: every glyph
# pixel lands at `y + 4 - height - y_offset + gy`, identical to the flat Label
# path per glyph (descenders included). Pinned by test_gradient_text.py.
_BASELINE_DROP = 4


def _build_ramp(palette, steps):
    """A ``steps``-long tuple of ``0xRRGGBB`` from the user's palette stops.

    Two stops -> a straight :func:`gradient`; three or more -> a
    :func:`multi_gradient` across them; one (or none) -> a flat fill.
    """
    stops = tuple(palette) if palette else ()
    if len(stops) <= 1:
        c = stops[0] if stops else 0xFFFFFF
        return tuple(c for _ in range(max(1, steps)))
    if len(stops) == 2:
        return gradient(stops[0], stops[1], steps)
    return multi_gradient(stops, steps)


class GradientTextLayer:
    """Owns the indexed bitmap, palette and TileGrid for one gradient string.

    Build once (rasterise + positional index map, paid on the first frame), then
    reposition by setting :attr:`x`; :meth:`detach` removes the layer.
    ``StaticText`` / ``ScrollingText`` drive it via their ``palette=`` argument for
    the common case; use this class directly for custom positioning/animation.

    Args:
        text: The string to rasterise.
        y: Baseline row (screen coordinates; matches ``StaticText``/``ScrollingText``).
        palette: A tuple of ``0xRRGGBB`` gradient stops (1 = flat fill, 2 = a
            straight gradient, 3+ = a multi-stop gradient across the run).
        direction: ``"vertical"`` (default), ``"horizontal"``, or ``"diagonal"``.
        palette_steps: Ramp resolution (2..``MAX_PALETTE_STEPS``); ignored for a
            single-colour palette.
    """

    def __init__(self, text, y, palette, direction="vertical", palette_steps=8):
        self.text = text
        self.y = y
        self.palette = tuple(palette) if palette else ()
        self.direction = normalize_direction(direction)
        # A single-colour palette is a degenerate (flat) gradient: ramp length 1.
        # Otherwise clamp to 2..MAX_PALETTE_STEPS so steps + transparent(0) <= 16
        # keeps the bitmap at 4 bits/pixel.
        self.steps = 1 if len(self.palette) <= 1 else clamp_palette_steps(palette_steps)
        self.width = 0
        self._bitmap = None
        self._palette = None
        self._tile = None

    def build(self, display):
        """Rasterise the text into an indexed bitmap and add it as a layer."""
        gfx = display.gfx
        font = getattr(display, "font", None)
        # Top-origin rasterisation; the layer is positioned vertically via tile.y.
        pixels = pixels_from_font_text(font, self.text, x=0, y=0)
        advance = font_text_width(font, self.text)
        ascent = font_text_ascent(font, self.text)   # baseline row within the raster
        if pixels:
            max_x = max(p[0] for p in pixels)
            ys = [p[1] for p in pixels]
            min_y, max_y = min(ys), max(ys)
        else:
            max_x = min_y = max_y = 0
        # Full advance width (includes trailing spaces) so a horizontal ramp is
        # stable across the whole phrase; widen if any glyph overhangs its advance.
        width = max(1, advance, max_x + 1)
        height = max_y + 1

        ramp = _build_ramp(self.palette, self.steps)
        n = len(ramp)
        bitmap = gfx.Bitmap(width, height, n + 1)
        palette = gfx.Palette(n + 1)
        palette.make_transparent(0)                 # index 0 = transparent ground
        for i in range(n):
            palette[1 + i] = ramp[i]

        # Each lit pixel's palette index is its position along the axis (NO modulo,
        # so the ramp spans the whole word end-to-end rather than tiling). One O(1)
        # lookup per lit pixel, paid once at build.
        span_x = width - 1
        span_y = max_y - min_y
        last = n - 1
        for (px, py) in pixels:
            bitmap[px, py] = self._ramp_index(px, py, min_y, span_x, span_y, last) + 1

        tile = gfx.TileGrid(bitmap, pixel_shader=palette)
        tile.x = display.width                       # start off the right edge
        tile.y = self.y + _BASELINE_DROP - ascent    # baseline-align to the Label
        display.add_layer(tile)

        self._bitmap = bitmap
        self._palette = palette
        self._tile = tile
        self.width = width

    def _ramp_index(self, x, y, min_y, span_x, span_y, last):
        """Position -> ramp index 0..last for the configured direction."""
        if last <= 0:
            return 0
        d = self.direction
        if d == "horizontal":
            num, den = x, span_x
        elif d == "diagonal":
            num, den = x + (y - min_y), span_x + span_y
        else:                                        # vertical (default)
            num, den = (y - min_y), span_y
        if den <= 0:
            return 0
        ramp_i = num * last // den
        if ramp_i < 0:
            return 0
        if ramp_i > last:
            return last
        return ramp_i

    @property
    def x(self):
        return self._tile.x if self._tile is not None else 0

    @x.setter
    def x(self, value):
        if self._tile is not None:
            self._tile.x = value

    def detach(self, display):
        """Remove the layer (idempotent — remove_layer ignores an absent tile)."""
        if self._tile is not None:
            display.remove_layer(self._tile)
            self._tile = None


# 0.8.x compatibility alias: themeparkwaits (and any other pre-0.8.2 caller)
# imports the old private name directly. Kept until a future 0.9.0.
_GradientTextLayer = GradientTextLayer
