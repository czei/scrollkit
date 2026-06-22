"""Integer easing/tween lookup tables (CircuitPython-safe).

Each named curve is a length-256 ``bytes`` table mapping a 0..255 progress to a
0..255 eased value, built **once** at import. ``ease()`` is a pure table lookup
— no float math and no allocation on the hot path. Six curves of 256 bytes each
is ~1.5 KB of static RAM.

Table values are clamped to 0..255; a curve that conceptually overshoots past the
endpoints (``OVERSHOOT``/``ELASTIC``) is clamped in storage, and an effect that
wants the overshoot expresses it by scaling the eased value itself.

The float math below runs at import only (once); the device imports this once and
then only ever indexes the tables.
"""

import math

# Curve ids (plain strings — no enum, CircuitPython-friendly).
LINEAR = "linear"
EASE_OUT_QUAD = "ease_out_quad"
EASE_IN_OUT = "ease_in_out"
OVERSHOOT = "overshoot"
BOUNCE = "bounce"
ELASTIC = "elastic"

CURVES = (LINEAR, EASE_OUT_QUAD, EASE_IN_OUT, OVERSHOOT, BOUNCE, ELASTIC)


def _clamp_byte(v):
    if v < 0:
        return 0
    if v > 255:
        return 255
    return int(round(v))


def _f_linear(t):
    return t


def _f_ease_out_quad(t):
    return 1.0 - (1.0 - t) * (1.0 - t)


def _f_ease_in_out(t):
    if t < 0.5:
        return 2.0 * t * t
    return 1.0 - 2.0 * (1.0 - t) * (1.0 - t)


def _f_overshoot(t):
    # Back ease-out: overshoots above 1.0 then settles (clamped in storage).
    c1 = 1.70158
    c3 = c1 + 1.0
    u = t - 1.0
    return 1.0 + c3 * u * u * u + c1 * u * u


def _f_bounce(t):
    # Standard ease-out bounce.
    n1 = 7.5625
    d1 = 2.75
    if t < 1.0 / d1:
        return n1 * t * t
    if t < 2.0 / d1:
        t -= 1.5 / d1
        return n1 * t * t + 0.75
    if t < 2.5 / d1:
        t -= 2.25 / d1
        return n1 * t * t + 0.9375
    t -= 2.625 / d1
    return n1 * t * t + 0.984375


def _f_elastic(t):
    # Ease-out elastic (lite). Endpoints pinned below.
    if t <= 0.0:
        return 0.0
    if t >= 1.0:
        return 1.0
    c4 = (2.0 * math.pi) / 3.0
    return math.pow(2.0, -10.0 * t) * math.sin((t * 10.0 - 0.75) * c4) + 1.0


_FUNCS = {
    LINEAR: _f_linear,
    EASE_OUT_QUAD: _f_ease_out_quad,
    EASE_IN_OUT: _f_ease_in_out,
    OVERSHOOT: _f_overshoot,
    BOUNCE: _f_bounce,
    ELASTIC: _f_elastic,
}


def _build(fn):
    out = bytearray(256)
    for p in range(256):
        t = p / 255.0
        out[p] = _clamp_byte(fn(t) * 255.0)
    out[0] = 0          # pin endpoints
    out[255] = 255
    return bytes(out)


_TABLES = {name: _build(fn) for name, fn in _FUNCS.items()}


def ease(curve, progress_0_255):
    """Return the eased 0..255 value for ``progress`` (0..255) on ``curve``.

    Pure ``bytes`` lookup: no floats, no allocation. Unknown curves fall back to
    linear. ``progress`` is clamped to 0..255.
    """
    table = _TABLES.get(curve)
    if table is None:
        table = _TABLES[LINEAR]
    p = progress_0_255
    if p < 0:
        p = 0
    elif p > 255:
        p = 255
    return table[p]


def interp(curve, a, b, progress_0_255):
    """Integer interpolation from ``a`` to ``b`` along ``curve`` (no floats)."""
    e = ease(curve, progress_0_255)
    return a + ((b - a) * e) // 255
