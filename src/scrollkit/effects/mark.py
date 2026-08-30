"""The mark an act reveals — pixels, a palette, and a layer you can show or hide.

Every build in :mod:`scrollkit.effects.acts` has the same shape: hide the mark, run an
overlay that shows its pixels arriving, then call ``ctx.show()`` to hand the real thing
back and drop the overlay. **That last step assumes something real is underneath.** An
app that owns its wordmark already has it — a set of glyph tiles it can un-hide — but
without one the drops land, the overlay detaches, and the panel goes black.

:class:`PixelMark` is the minimal version of that: give it lit cells and their colours
and it builds one bitmap, one palette and one tile, and shows or hides them. No layouts,
no glyph placement, no app.

    mark = PixelMark.from_text(display, "BLUE RIDGE COFFEE", y=12)
    mark.attach(display)
    ok = await drip_in(mark.context(display))

It satisfies the mark half of the act context — ``slots``, ``colors``, ``show``,
``hide`` — and :meth:`context` wires it to the runtime half. An app with its own tiles
should keep them and pass itself instead; this is for everything that has no app.
"""

from ..display.colors import dim_for as _dim

#: Used when the cells carry no per-pixel index and no colour was given.
_DEFAULT_COLOR = 0xFFB030


class PixelMark:
    """A fixed set of lit cells that can be put on screen and taken off again.

    Args:
        cells:  ``{(x, y): palette index}`` or any iterable of ``(x, y)``. A mapping
                colours each cell from ``colors``; a bare iterable is one flat tone.
        colors: The ramp the indices point into, low->high, ``0xRRGGBB`` each.
                Index 0 in the built palette is always transparent, so a cell's index
                ``i`` takes ``colors[i]`` and an index of 0 means "not lit".
        color:  The flat tone for cells that carry no index.
    """

    def __init__(self, cells, colors=None, color=None):
        self.slots = cells
        self.colors = colors
        self.color = color if color is not None else _DEFAULT_COLOR
        self._display = None
        self._tile = None
        self._bitmap = None

    @classmethod
    def from_text(cls, display, text, x=0, y=0, scale=1, color=None):
        """A mark from a line of text, in the display's own font.

        The cheapest possible mark, and the reason it exists: a deck of acts can be
        built and judged against a real wordmark before any custom art is drawn.
        """
        from ..display.text_pixels import pixels_from_font_text

        cells = pixels_from_font_text(display.font, text, x=x, y=y, scale=scale)
        return cls(cells, color=color)

    @classmethod
    def from_art(cls, rows, chars, x=0, y=0):
        """A mark from ASCII art: rows of characters, and what colour each one is.

        The format hand-authored pixel art already uses — a tuple of equal-length
        strings where a character names a colour — so a drawing goes on the panel
        without being converted into anything first.

        Args:
            rows:  Equal-length strings, one per row. Ragged rows are tolerated; a
                   short one simply has fewer lit cells, which is what a short row
                   means. See :func:`scrollkit.utils.pixel_art.normalize_art` for
                   repairing them properly.
            chars: ``{character: 0xRRGGBB}``. A character absent from this map is
                   NOT LIT — that is how "." and " " become background without being
                   special-cased, and it means an unmapped character is a hole rather
                   than a guess.
            x, y:  Where the art's top-left corner sits on the panel.

        The palette is built from the colours actually used, in first-seen order, so
        a mark carries only the entries it needs.
        """
        ramp = []
        index = {}
        cells = {}
        for row_y, row in enumerate(rows):
            for row_x, ch in enumerate(row):
                color = chars.get(ch)
                if color is None:
                    continue
                if ch not in index:
                    ramp.append(color)
                    index[ch] = len(ramp)
                cells[(x + row_x, y + row_y)] = index[ch]
        return cls(cells, colors=ramp)

    # -- the layer ----------------------------------------------------------

    def attach(self, display):
        """Build the mark's layer and add it to the display, hidden.

        Hidden rather than visible, because every act's first move is to clear the
        panel: attaching visible would flash the finished mark for one frame before
        the act that assembles it begins.
        """
        gfx = display.gfx
        indexed = hasattr(self.slots, "items")
        ramp = list(self.colors) if (indexed and self.colors) else None
        depth = (len(ramp) + 1) if ramp else 2

        bitmap = gfx.Bitmap(display.width, display.height, depth)
        palette = gfx.Palette(depth)
        palette.make_transparent(0)
        if ramp:
            for i, rgb in enumerate(ramp):
                palette[i + 1] = _dim(display, rgb)
        else:
            palette[1] = _dim(display, self.color)

        for cell in self.slots:
            x, y = cell
            if not (0 <= x < display.width and 0 <= y < display.height):
                continue
            if ramp:
                # An index of 0 is "not lit" in the source art; shifting by one keeps
                # slot 0 of the built palette as transparency.
                slot = self.slots[cell]
                if slot <= 0 or slot > len(ramp):
                    continue
                bitmap[x, y] = slot
            else:
                bitmap[x, y] = 1

        self._bitmap = bitmap
        self._tile = gfx.TileGrid(bitmap, pixel_shader=palette)
        self._tile.hidden = True
        display.add_layer(self._tile)
        self._display = display
        return self

    def detach(self):
        """Remove the layer (no-op if it was never attached, or already gone)."""
        if self._display is not None and self._tile is not None:
            self._display.remove_layer(self._tile)
            self._tile = None

    # -- the act context ----------------------------------------------------

    def show(self):
        if self._tile is not None:
            self._tile.hidden = False

    def hide(self):
        if self._tile is not None:
            self._tile.hidden = True

    def context(self, display=None, frame=None):
        """A context an act will accept, wired to this mark.

        The mark supplies ``slots``, ``colors``, ``show`` and ``hide``; the caller
        supplies the runtime half — the display, and how a frame gets presented.
        """
        from .acts import SimpleContext

        return SimpleContext(
            display if display is not None else self._display,
            self.slots,
            colors=self.colors,
            show=self.show,
            hide=self.hide,
            frame=frame,
        )
