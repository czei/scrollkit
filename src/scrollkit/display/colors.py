# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Continuous 24-bit colour generators (device-safe, pure-integer math).

These expose the **full** colour space as functions an app or effect samples at any
resolution — deliberately NOT a catalogue of named palettes. The point is to escape
fixed mini-palettes (the old 6-colour rainbow ramp, the 16 named colours): generate
exactly the gradient/spectrum you want, at the resolution that suits the panel.

CircuitPython-safe: integer arithmetic, no ``colorsys``, no typing at runtime. Build a
ramp ONCE (at effect construction or import) and reuse it — none of these belong in a
per-frame loop. Every function takes/returns packed ``0xRRGGBB`` ints.

    spectrum(24)                  # 24 smooth hues around the wheel
    gradient(0x102840, 0x00CCFF, 16)   # 16 steps, deep blue -> cyan
    multi_gradient((0x330000, 0xFF4400, 0xFFF0A0), 32)  # fire ramp, 32 steps
    hsv(210, 0.8, 1.0)            # any hue/sat/value -> one colour
"""


def _clamp8(v):
    if v < 0:
        return 0
    if v > 255:
        return 255
    return v


def wheel(pos):
    """Full-saturation, full-value hue for ``pos`` 0..255 -> ``0xRRGGBB``.

    A continuous colour wheel (red -> green -> blue -> red), cheap integer math so it
    is safe to call on CircuitPython. Wraps, so ``pos`` may be any int.
    """
    pos = pos & 0xFF
    if pos < 85:
        return ((255 - pos * 3) << 16) | ((pos * 3) << 8)
    if pos < 170:
        pos -= 85
        return ((255 - pos * 3) << 8) | (pos * 3)
    pos -= 170
    return ((pos * 3) << 16) | (255 - pos * 3)


def spectrum(n):
    """``n`` evenly spaced full-saturation hues across the wheel (cyclic-friendly).

    Endpoints don't duplicate (positions are ``i*256//n``), so the ramp tiles/rotates
    without a visible seam — ideal for a rotating rainbow.
    """
    if n <= 0:
        return ()
    return tuple(wheel(i * 256 // n) for i in range(n))


def lerp(a, b, t):
    """Blend ``0xRRGGBB`` ``a`` -> ``b`` by ``t`` in 0.0..1.0."""
    if t <= 0:
        return a
    if t >= 1:
        return b
    ar = (a >> 16) & 0xFF
    ag = (a >> 8) & 0xFF
    ab = a & 0xFF
    br = (b >> 16) & 0xFF
    bg = (b >> 8) & 0xFF
    bb = b & 0xFF
    r = ar + int((br - ar) * t)
    g = ag + int((bg - ag) * t)
    bl = ab + int((bb - ab) * t)
    return (_clamp8(r) << 16) | (_clamp8(g) << 8) | _clamp8(bl)


def gradient(a, b, n):
    """``n`` colours interpolated from ``a`` to ``b`` (both inclusive)."""
    if n <= 0:
        return ()
    if n == 1:
        return (a,)
    return tuple(lerp(a, b, i / (n - 1)) for i in range(n))


def multi_gradient(stops, n):
    """``n`` colours interpolated across a sequence of ``stops`` (>= 1 colour)."""
    stops = tuple(stops)
    if not stops or n <= 0:
        return ()
    if len(stops) == 1:
        return tuple(stops[0] for _ in range(n))
    if n == 1:
        return (stops[0],)
    segs = len(stops) - 1
    out = []
    for i in range(n):
        pos = i * segs / (n - 1)        # 0 .. segs
        si = int(pos)
        if si >= segs:
            si = segs - 1
            t = 1.0
        else:
            t = pos - si
        out.append(lerp(stops[si], stops[si + 1], t))
    return tuple(out)


def scale(color, factor):
    """Scale a ``0xRRGGBB`` colour's brightness by ``factor`` (0.0-1.0). Integer-only.

    Effects call this once at construction to derive shades from a base colour, so
    there is no per-frame cost.
    """
    if factor <= 0.0:
        return 0
    f = 256 if factor >= 1.0 else int(factor * 256)
    r = (((color >> 16) & 0xFF) * f) >> 8
    g = (((color >> 8) & 0xFF) * f) >> 8
    b = ((color & 0xFF) * f) >> 8
    return (r << 16) | (g << 8) | b


def hsv(h, s=1.0, v=1.0):
    """HSV -> ``0xRRGGBB``. ``h`` in degrees (0..360, wraps), ``s``/``v`` in 0.0..1.0.

    The general-purpose generator when you want a specific hue at a chosen saturation
    and value rather than a point on the full-bright :func:`wheel`.
    """
    h = h % 360
    c = v * s
    x = c * (1 - abs((h / 60.0) % 2 - 1))
    m = v - c
    if h < 60:
        rp, gp, bp = c, x, 0.0
    elif h < 120:
        rp, gp, bp = x, c, 0.0
    elif h < 180:
        rp, gp, bp = 0.0, c, x
    elif h < 240:
        rp, gp, bp = 0.0, x, c
    elif h < 300:
        rp, gp, bp = x, 0.0, c
    else:
        rp, gp, bp = c, 0.0, x
    r = _clamp8(int((rp + m) * 255))
    g = _clamp8(int((gp + m) * 255))
    b = _clamp8(int((bp + m) * 255))
    return (r << 16) | (g << 8) | b
