"""scrollkit.dev.performance_guide() — device-measured perf trade-offs for the AI.

Pins that the guide loads the shipped benchmark table and exposes the key facts
the AI needs: the C-vs-interpreted pixel spread, the bit_depth/refresh ladder,
and the cardinal rules.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.dev import performance_guide, capabilities
from scrollkit.dev.performance import as_text


def test_guide_is_available_with_expected_sections():
    g = performance_guide()
    assert g["available"] is True
    for key in ("pixel_write_ns_per_px", "refresh", "allocation_ns",
                "compute_ns_per_op", "gc_collect_ns", "rules"):
        assert key in g


def test_c_is_faster_than_interpreted_per_pixel():
    pw = performance_guide()["pixel_write_ns_per_px"]
    # interpreted set-pixel >> C blit >> C fill (per pixel)
    assert pw["interpreted_setpixel"] > pw["c_bitmaptools_blit"] > pw["c_bitmap_fill"]
    assert pw["interpreted_setpixel"] > 10 * pw["c_bitmaptools_blit"]


def test_refresh_ladder_shows_bit_depth_6_is_slower():
    refresh = performance_guide()["refresh"]
    assert "bit_depth_4" in refresh and "bit_depth_6" in refresh
    assert refresh["bit_depth_6"]["full_refresh_ms"] > \
        2 * refresh["bit_depth_4"]["full_refresh_ms"]
    assert refresh["bit_depth_4"]["fps_ceiling"] > refresh["bit_depth_6"]["fps_ceiling"]


def test_rules_are_present_and_actionable():
    rules = performance_guide()["rules"]
    assert len(rules) >= 4
    joined = " ".join(rules).lower()
    assert "bit_depth" in joined and "label" in joined


def test_capabilities_includes_performance():
    perf = capabilities()["performance"]
    assert perf.get("available") is True


def test_as_text_is_readable():
    text = as_text()
    assert "performance" in text.lower()
    assert "refresh" in text.lower()
