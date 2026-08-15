"""
ASCII pixel-art repair: make hand-authored art safe to convert.
Copyright (c) 2024-2026 Michael Czeiszperger

Art is authored as a tuple of strings, one character per LED, each character
naming a palette slot. Two typos are near-unavoidable when a human (or a model)
types a sprite by hand, and both crash from deep inside the conversion loop with
nothing on the panel and no clue which sprite is at fault:

* **A ragged row.** You add a character to row 4 and forget the others. A bitmap
  sized from ``rows[0]`` then throws ``IndexError: Pixel index (30, 4) out of
  bounds``.
* **An unmapped character.** A stray space, or a ``+`` invented for a highlight
  and never added to the slot map: ``KeyError: '+'``.

Neither is ambiguous about what the author meant. A short row means "nothing
else on this row", so it pads with transparent. An unmapped character means
"something IS here and I forgot to define it", so it becomes the first lit slot
rather than transparent -- substituting transparent would silently delete the
sprite it was drawing, which is a worse outcome than the crash. Whitespace is
the exception: a stray space is background, and is padded away.

:func:`normalize_art` repairs both and says what it repaired, rather than
refusing to draw.

This exists because it was measured. Across six documented model-written signs,
every first-attempt failure was one of these two typos and nothing else -- one
of them a single row of 25 characters where its two neighbours were 26, in a
598-line program with 34 sprites. Each cost a full regeneration round.
"""


def art_problems(rows, slots=None, name=None):
    """Return a list of human-readable problems with one sprite's rows.

    Empty list means the art converts cleanly. Use this to assert in a test;
    use :func:`normalize_art` to repair at import.
    """
    label = "%s: " % name if name else ""
    problems = []
    if not rows:
        return [label + "no rows"]
    widths = sorted(set(len(row) for row in rows))
    if len(widths) != 1:
        problems.append(label + "ragged rows, widths %s" % (widths,))
    if slots is not None:
        # sorted(), not set iteration order -- an unseeded ordering here would
        # make the message differ between Python builds.
        unknown = sorted(set("".join(rows)) - set(slots))
        if unknown:
            problems.append(label + "characters not in the slot map: %s"
                            % "".join(unknown))
    return problems


def _first_lit_char(slots, pad):
    """The character mapping to the lowest non-zero slot, or ``pad`` if none.

    This is what an unmapped, non-whitespace character becomes: the author drew
    something there, so draw something. min() over the items rather than set
    iteration, so the choice is stable across Python builds.
    """
    lit = [(slot, ch) for ch, slot in slots.items() if slot]
    return min(lit)[1] if lit else pad


def normalize_art(rows, slots=None, pad=".", name=None, report=None):
    """Return ``rows`` padded to a common width with unmapped characters replaced.

    ``rows``   -- tuple/list of strings, one character per LED.
    ``slots``  -- the character-to-palette-slot map. When given, unmapped
                  whitespace becomes ``pad`` and any other unmapped character
                  becomes the first lit slot's character. When ``None``, only
                  the width is repaired.
    ``pad``    -- the character to pad with. Must itself be in ``slots`` and
                  should map to the transparent slot (0).
    ``name``   -- sprite name, used only in the report.
    ``report`` -- called with one message per repair. Defaults to ``print`` so a
                  repair is never silent; pass ``lambda _m: None`` to silence it,
                  or a list's ``append`` to collect.

    Returns a tuple of equal-length strings, ready for the conversion loop::

        LOGO = normalize_art(LOGO, CHAR_TO_SLOT)
        bmp = gfx.Bitmap(len(LOGO[0]), len(LOGO), len(PALETTE))
        for y, row in enumerate(LOGO):
            for x, ch in enumerate(row):
                bmp[x, y] = CHAR_TO_SLOT[ch]

    Padding is on the right, which is what a truncated row means. Art that needs
    centring or left-padding has to say so -- this repairs typos, it does not
    lay anything out.
    """
    if report is None:
        report = print
    if not rows:
        return ()
    label = "%s: " % name if name else ""

    width = max(len(row) for row in rows)
    fixed = []
    ragged = 0
    for row in rows:
        if len(row) != width:
            ragged += 1
            row = row + pad * (width - len(row))
        fixed.append(row)
    if ragged:
        report("pixel_art: %spadded %d ragged row(s) to width %d"
               % (label, ragged, width))

    if slots is not None:
        unknown = sorted(set("".join(fixed)) - set(slots))
        if unknown:
            lit = _first_lit_char(slots, pad)
            # str.translate/maketrans are absent on CircuitPython; replace() is
            # not, and there are only ever a handful of stray characters.
            blanked, drawn = [], []
            for ch in unknown:
                sub = pad if ch.isspace() else lit
                fixed = [row.replace(ch, sub) for row in fixed]
                (blanked if sub == pad else drawn).append(ch)
            if blanked:
                report("pixel_art: %sunmapped whitespace %r -> %r (transparent)"
                       % (label, "".join(blanked), pad))
            if drawn:
                report("pixel_art: %sunmapped character(s) %s -> %r; map them "
                       "explicitly to pick their color"
                       % (label, "".join(drawn), lit))

    return tuple(fixed)


def normalize_all(art, slots=None, pad=".", report=None):
    """Normalize a whole ``{name: rows}`` map of sprites in one call.

    Returns a new dict; the input is not mutated::

        CAPS7 = normalize_all(CAPS7, CHAR_TO_SLOT)
    """
    out = {}
    for name in sorted(art):        # sorted so any report is reproducible
        out[name] = normalize_art(art[name], slots, pad=pad, name=name,
                                  report=report)
    return out
