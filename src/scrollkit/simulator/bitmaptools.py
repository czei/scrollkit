# Copyright (c) 2024-2026 Michael Czeiszperger
"""Desktop emulation of CircuitPython's ``bitmaptools`` C module.

ScrollKit's span/rect painters, overlay-mask, and bitmap-text all express bounded
work through ``bitmaptools.fill_region`` / ``bitmaptools.blit`` so the SAME code
runs on the device (where ``bitmaptools`` is a built-in) and on the desktop
simulator (where this shim provides it). The display resolves which module to use
via ``display.gfx``.

Semantics mirror the device for the subset ScrollKit uses:
- ``fill_region`` fills the HALF-OPEN rectangle ``[x1, x2) x [y1, y2)`` clipped to
  the bitmap; an empty/inverted region is a no-op.
- ``blit`` copies a source sub-rectangle into the destination at ``(x, y)`` with
  ``skip_index`` transparency, clipped at all four edges (incl. negative offsets).

Desktop-only — never imported on CircuitPython (the device uses the real module).
A golden corpus captured on a real board pins this shim's fidelity
(``test/unit/display/test_bitmaptools_shim.py``); if it ever diverges, fix the
shim, never the shared effect logic.
"""


def fill_region(bitmap, x1, y1, x2, y2, value):
    """Fill the half-open rectangle ``[x1, x2) x [y1, y2)`` with ``value``.

    Clipped to the bitmap. Matching CircuitPython, an inverted or empty region
    (``x1 >= x2`` or ``y1 >= y2``) is a no-op — the bounds are NOT reordered, so
    the simulator and device agree.
    """
    if x1 >= x2 or y1 >= y2:
        return
    w = bitmap.width
    h = bitmap.height
    xa = x1 if x1 > 0 else 0
    ya = y1 if y1 > 0 else 0
    xb = x2 if x2 < w else w
    yb = y2 if y2 < h else h
    if xb <= xa or yb <= ya:
        return
    bitmap._buffer[ya:yb, xa:xb] = value


def blit(dest, source, x, y, *, x1=0, y1=0, x2=None, y2=None, skip_index=None):
    """Copy ``source`` (sub-rect ``[x1,x2) x [y1,y2)``) into ``dest`` at ``(x, y)``.

    Honors ``skip_index`` transparency and clips at every edge, including negative
    destination offsets. Delegates to the simulator ``Bitmap.blit``, which already
    implements the CircuitPython clipping/transparency rules.
    """
    dest.blit(x, y, source, x1=x1, y1=y1, x2=x2, y2=y2, skip_index=skip_index)
