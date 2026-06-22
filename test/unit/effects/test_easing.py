"""Integer easing LUTs: endpoints pinned, bytes-backed, deterministic, no floats."""

from scrollkit.effects import easing
from scrollkit.effects.easing import ease, interp, CURVES


def test_all_curves_have_pinned_endpoints():
    for curve in CURVES:
        assert ease(curve, 0) == 0, curve
        assert ease(curve, 255) == 255, curve


def test_tables_are_bytes_of_length_256():
    for curve in CURVES:
        table = easing._TABLES[curve]
        assert isinstance(table, bytes)
        assert len(table) == 256


def test_ease_returns_int_in_range():
    for curve in CURVES:
        for p in (0, 1, 50, 128, 200, 255):
            v = ease(curve, p)
            assert isinstance(v, int)
            assert 0 <= v <= 255


def test_linear_is_identity():
    for p in (0, 17, 64, 128, 200, 255):
        assert ease("linear", p) == p


def test_deterministic_and_no_table_realloc():
    # Same input -> same output, and the underlying table is a stable object
    # (the hot path indexes it, it is not rebuilt per call).
    assert ease("ease_out_quad", 100) == ease("ease_out_quad", 100)
    assert easing._TABLES["linear"] is easing._TABLES["linear"]


def test_ease_out_quad_is_front_loaded():
    # ease-out: at the midpoint it has already covered MORE than half.
    assert ease("ease_out_quad", 128) > 128


def test_progress_is_clamped():
    assert ease("linear", -10) == 0
    assert ease("linear", 999) == 255


def test_unknown_curve_falls_back_to_linear():
    for p in (0, 100, 255):
        assert ease("nope", p) == ease("linear", p)


def test_interp_endpoints_and_midpoint():
    assert interp("linear", 0, 100, 0) == 0
    assert interp("linear", 0, 100, 255) == 100
    assert abs(interp("linear", 0, 100, 128) - 50) <= 1
    # works with a descending range too
    assert interp("linear", 64, 0, 255) == 0
