# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Font/scale-aware text → lit-pixel composition (single source of truth).

``pixels_from_font_text`` renders a string with *any* loaded font at an integer
scale and returns the list of lit ``(x, y)`` pixels — the same ``[(x, y), ...]``
format the splash effects and the gradient text-fill renderer consume.  Because
the drip animation, the live on-screen image, *and* gradient text are all built
from this one function, the pixels are identical **by construction** — there is
nothing to "match" and no chance of desktop/device drift.

It is a pure function over the font's glyph bitmaps (no displayio Bitmap is
allocated, no ``gfx`` needed), so it runs unchanged on the simulator and on
CircuitPython.  The one real platform difference it papers over is the glyph
object shape:

* simulator ``font.get_glyph`` returns a **dict** (``'dx'`` is the advance,
  ``'x_offset'`` the left bearing, ``'y_offset'`` the baseline-relative vertical
  offset, ``'bitmap'`` the glyph bitmap);
* CircuitPython ``adafruit_bitmap_font`` returns an **object** (``.shift_x`` is
  the advance, ``.dx`` the left bearing, ``.dy`` the vertical offset, ``.bitmap``
  the glyph bitmap).

Glyphs are laid out left-to-right by advance and **baseline-aligned** (each glyph
sits at ``baseline - height - y_offset``, so descenders drop below the line and
short glyphs rest on it), matching ``adafruit_display_text.Label`` — so mixed-case
prose with descenders renders correctly, not just digits and ALL-CAPS runs. The
shared baseline sits ``font_text_ascent`` pixels below ``y`` (``y`` is the top of
the tallest glyph in the run).

This module lives in ``display/`` (not ``effects/``) on purpose: it is depended
on by both ``display.gradient_text`` and the ``effects`` splash animations, and
``effects`` already imports from ``display``.  Homing it here keeps the
``display → effects`` direction from ever forming a cycle and stops the
RAM-heavy ``effects`` package (particles/splashes) from loading just to render
text.  ``effects/text_render.py`` re-exports these names for backwards
compatibility.
"""

# Advance used when a glyph is missing entirely (keeps spacing sane).
_MISSING_ADVANCE = 4


def _glyph_fields(glyph):
    """Normalise a glyph (dict on simulator, object on device) to a tuple.

    Returns ``(bitmap, width, height, x_bearing, y_offset, advance, sheet_x,
    sheet_y)`` or ``None`` when the glyph is absent.  ``bitmap`` may be ``None``
    (e.g. a space) — the caller still advances by ``advance``.

    ``y_offset`` is the BDF ``BBX`` vertical offset: the bitmap's bottom edge sits
    that many pixels above the baseline (so it is **negative for descenders**).
    The top of the glyph relative to the baseline is therefore
    ``baseline - height - y_offset`` — exactly what ``adafruit_display_text.Label``
    uses, so callers can baseline-align mixed-height text instead of top-aligning
    it.  On the simulator the glyph dict carries it as ``'y_offset'``; on
    CircuitPython the ``adafruit_bitmap_font`` glyph object carries it as ``.dy``
    (same sign convention — verify on hardware if in doubt).

    ``sheet_x/sheet_y`` are the glyph's pixel origin *within* ``bitmap``: 0,0 for
    per-glyph bitmaps (most BDF loads + the simulator), but non-zero for
    built-in/packed fonts whose glyphs all share one sprite-sheet bitmap addressed
    by ``tile_index`` (e.g. the device's ``terminalio`` font, where ``bitmap`` is
    the whole 570x12 sheet).
    """
    if glyph is None:
        return None
    if isinstance(glyph, dict):
        bmp = glyph.get("bitmap")
        gw = glyph.get("width", 0) or 0
        gh = glyph.get("height", 0) or 0
        xoff = glyph.get("x_offset", 0) or 0
        yoff = glyph.get("y_offset", 0) or 0  # simulator: BDF y-offset (baseline-rel)
        adv = glyph.get("dx")                 # simulator: 'dx' is the advance
        if adv is None:
            adv = glyph.get("shift_x", gw)
        return (bmp, gw, gh, xoff, yoff, adv if adv is not None else gw, 0, 0)
    bmp = getattr(glyph, "bitmap", None)
    gw = getattr(glyph, "width", 0) or 0
    gh = getattr(glyph, "height", 0) or 0
    xoff = getattr(glyph, "dx", 0) or 0       # device: '.dx' is the left bearing
    yoff = getattr(glyph, "dy", 0) or 0       # device: '.dy' is the BDF y-offset
    adv = getattr(glyph, "shift_x", None)     # device: '.shift_x' is the advance
    if adv is None:
        adv = gw
    # Packed sprite-sheet fonts (terminalio built-in): every glyph's '.bitmap' is
    # the same wide sheet; the glyph lives at tile '.tile_index'. Detect by the
    # sheet being wider than one glyph and resolve the tile's top-left origin.
    sheet_x = sheet_y = 0
    if bmp is not None and gw:
        try:
            bw = bmp.width
        except (AttributeError, TypeError):
            bw = gw
        if bw > gw:
            tile_index = getattr(glyph, "tile_index", 0) or 0
            tiles_per_row = bw // gw if gw else 1
            if tiles_per_row < 1:
                tiles_per_row = 1
            sheet_x = (tile_index % tiles_per_row) * gw
            sheet_y = (tile_index // tiles_per_row) * gh
    return (bmp, gw, gh, xoff, yoff, adv, sheet_x, sheet_y)


def _run_ascent(fields_list):
    """Rows above the baseline for the TALLEST glyph in a resolved run (unscaled).

    ``height + y_offset`` is a glyph's extent above the baseline; the run's ascent
    is the max of that. It is the baseline's row offset from the top of the run,
    and the smallest value that keeps every glyph (placed at
    ``ascent - height - y_offset``) at a non-negative row.
    """
    run = 0
    for fields in fields_list:
        if fields is not None:
            _b, _gw, gh, _x, yoff, _a, _sx, _sy = fields
            if gh and (gh + yoff) > run:
                run = gh + yoff
    return run


def pixels_from_font_text(font, text, x=0, y=0, scale=1):
    """Return ``[(x, y), ...]`` lit pixels for ``text`` in ``font`` at ``scale``.

    Glyphs are **baseline-aligned**: the run's shared baseline sits
    ``font_text_ascent(font, text, scale)`` pixels below ``y``, and each glyph is
    placed at ``baseline - height - y_offset`` (descenders drop below the line),
    matching ``adafruit_display_text.Label``. For an equal-height run (digits, an
    ALL-CAPS word) this is identical to plain top-alignment; for mixed-case prose
    with descenders it renders correctly instead of floating the short letters up.

    Args:
        font:  A loaded font exposing ``get_glyph(codepoint)`` (the display's
               ``self.font`` — terminalio by default).
        text:  String to render.
        x:     Left edge of the first glyph, in display pixels.
        y:     Top edge of the text (the top of the tallest glyph), in display px.
        scale: Integer magnification (>=1); each lit cell becomes a
               ``scale`` x ``scale`` block, matching ``draw_text_scaled``.

    Returns:
        List of ``(x, y)`` integer tuples for every lit pixel.

    Example — a 2x wait-time number, centred on a 64-wide display::

        from scrollkit.effects import pixels_from_font_text
        # width is len*advance*scale; centre it, then drip these pixels in.
        px = pixels_from_font_text(display.font, "45", x=20, y=8, scale=2)
    """
    if scale is None or scale < 1:
        scale = 1
    scale = int(scale)

    # Resolve every glyph once, then find the run's baseline (tallest glyph above
    # it) so shorter glyphs and descenders can be placed relative to it.
    resolved = [_glyph_fields(font.get_glyph(ord(ch)) if font is not None else None)
                for ch in text]
    ascent = _run_ascent(resolved)

    pixels = []
    pen_x = x
    for fields in resolved:
        if fields is None:
            pen_x += _MISSING_ADVANCE * scale
            continue
        bmp, gw, gh, xoff, yoff, adv, sheet_x, sheet_y = fields
        if bmp is not None and gw and gh:
            base_x = pen_x + xoff * scale
            # Top of this glyph on a baseline shared by the whole run.
            glyph_top = y + (ascent - gh - yoff) * scale
            for gx in range(gw):
                for gy in range(gh):
                    if bmp[sheet_x + gx, sheet_y + gy]:
                        px0 = base_x + gx * scale
                        py0 = glyph_top + gy * scale
                        for sx in range(scale):
                            for sy in range(scale):
                                pixels.append((px0 + sx, py0 + sy))
        pen_x += (adv if adv else gw) * scale
    return pixels


def font_text_ascent(font, text, scale=1):
    """Baseline row offset (px below ``y``) for ``text`` — i.e. how far below the
    top of the rendered run its shared baseline sits.

    Lets a caller that positions the rendered pixels itself (e.g. the gradient
    text layer) baseline-align them to the displayio ``Label`` path. Matches the
    baseline :func:`pixels_from_font_text` uses for the same arguments.
    """
    if scale is None or scale < 1:
        scale = 1
    scale = int(scale)
    resolved = [_glyph_fields(font.get_glyph(ord(ch)) if font is not None else None)
                for ch in text]
    return _run_ascent(resolved) * scale


def font_text_width(font, text, scale=1):
    """Total advance width (px) of ``text`` in ``font`` at ``scale``.

    Mirrors the layout ``pixels_from_font_text`` uses, so callers can centre the
    text (``x = (display.width - font_text_width(...)) // 2``) and get pixels
    that line up with a later ``draw_text_scaled`` of the same string.
    """
    if scale is None or scale < 1:
        scale = 1
    scale = int(scale)
    total = 0
    for ch in text:
        fields = _glyph_fields(font.get_glyph(ord(ch)) if font is not None else None)
        if fields is None:
            total += _MISSING_ADVANCE
            continue
        _bmp, gw, _gh, _xoff, _yoff, adv, _sx, _sy = fields
        total += adv if adv else gw
    return total * scale
