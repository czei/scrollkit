"""Reveal-splash animation — all LEDs on, wink off non-text pixels to reveal art.

Drop-in library version of the ThemeParkWaits reveal animation.  The caller
supplies the list of pixels that should remain on (the "text" or "logo"); the
rest wink off in random order until the image is revealed, then hold briefly.

Pixel-exact via displayio Bitmap so Label y-origin issues don't apply.  Uses
``display.gfx`` (the same graphics context OverlayMask uses) rather than a bare
``import displayio`` — this guarantees the simulator's displayio is used on
desktop and the hardware one on CircuitPython.

Typical usage::

    from scrollkit.effects import show_reveal_splash, pixels_from_text

    # Build a pixel list from text using the built-in 5x7 font.
    px = pixels_from_text("SCROLL", x=14, y=8)
    px += pixels_from_text("KIT", x=23, y=20)
    await show_reveal_splash(display, px)

    # Or supply your own pixel-art coordinates.
    await show_reveal_splash(display, my_logo_pixels, color=0x00FF88)
"""

import asyncio
import random


def _simple_shuffle(lst):
    """In-place Fisher-Yates shuffle — random.shuffle is not on CircuitPython."""
    for i in range(len(lst) - 1, 0, -1):
        j = random.randint(0, i)
        lst[i], lst[j] = lst[j], lst[i]


def pixels_from_text(text, x=0, y=0):
    """Return ``[(col, row), ...]`` for ``text`` rendered in the built-in 5×7 font.

    The coordinates are absolute display pixels: each glyph starts at ``x`` and
    advances 6 px (5 wide + 1 gap) per character; glyphs are 7 rows tall
    starting at ``y``.  Pixels that fall outside the font table (unknown chars)
    are silently skipped.

    Args:
        text: String to render (case-insensitive; unknown chars are skipped).
        x:    Left edge of the first character in display pixels.
        y:    Top edge of the text in display pixels.

    Returns:
        List of ``(x, y)`` integer tuples for every lit pixel.

    Example — "SCROLL" centred on the top half of a 64×32 display::

        px = pixels_from_text("SCROLL", x=14, y=8)
    """
    from ..display.bitmap_text import FONT_5x7 as _FONT_5x7  # lazy — keep device RAM low
    pixels = []
    cx = x
    for ch in text:
        rows = _FONT_5x7.get(ch.upper())
        if rows is not None:
            for ry, row in enumerate(rows):
                for rx, cell in enumerate(row):
                    if cell != " ":
                        pixels.append((cx + rx, y + ry))
        cx += 6  # CELL_W = glyph(5) + gap(1)
    return pixels


async def show_reveal_splash(
    display,
    pixels,
    color=0xFFFF00,
    off_per_frame=14,
    hold_seconds=2.0,
):
    """Play a reveal animation on ``display``.

    All LEDs start on (``color``), then non-``pixels`` LEDs wink off in
    random order ``off_per_frame`` at a time until only the ``pixels`` remain.
    The image then holds for ``hold_seconds`` before the overlay is removed.

    Args:
        display:       A ScrollKit ``UnifiedDisplay`` (must be initialised).
        pixels:        Iterable of ``(x, y)`` tuples — pixels that stay on.
                       Everything else will be turned off during the reveal.
        color:         24-bit RGB fill color (default: yellow 0xFFFF00).
        off_per_frame: Pixels turned off per animation step (speed knob).
                       14 is calibrated for the 64×32 MatrixPortal S3 at ~20 fps.
        hold_seconds:  Seconds to hold the revealed image before finishing.
    """
    gfx = display.gfx
    w, h = display.width, display.height

    bitmap = gfx.Bitmap(w, h, 2)
    palette = gfx.Palette(2)
    palette[0] = 0x000000
    palette[1] = color
    tilegrid = gfx.TileGrid(bitmap, pixel_shader=palette)
    display.add_layer(tilegrid)

    target_set = set(pixels)

    # Fill all pixels on in one C bulk call (never a per-pixel Python loop).
    try:
        bitmap.fill(1)
    except (AttributeError, TypeError):
        for x in range(w):
            for y in range(h):
                bitmap[x, y] = 1

    # Non-target pixels to wink off, in random order.
    to_off = [(x, y) for x in range(w) for y in range(h)
              if (x, y) not in target_set]
    _simple_shuffle(to_off)

    await display.show()

    while to_off:
        batch = min(off_per_frame, len(to_off))
        for _ in range(batch):
            px = to_off.pop()
            bitmap[px[0], px[1]] = 0
        await display.show()
        await asyncio.sleep(0.02)

    await display.show()
    await asyncio.sleep(hold_seconds)
    display.remove_layer(tilegrid)
