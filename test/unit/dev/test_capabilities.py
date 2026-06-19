"""scrollkit.dev.capabilities() — the AI authoring catalog.

The catalog is introspected from live code so it can't drift; these tests pin
that it actually reflects the real Priority class, content classes, colors, and
display API rather than a hand-maintained copy.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.dev import capabilities
from scrollkit.dev.capabilities import as_text


def test_catalog_has_expected_sections():
    cat = capabilities()
    for key in ("panel", "content_types", "priorities", "effects",
                "named_colors", "display_api", "hardware", "verification"):
        assert key in cat, "missing section: %s" % key


def test_panel_is_64x32():
    panel = capabilities()["panel"]
    assert panel["width"] == 64 and panel["height"] == 32


def test_priorities_match_the_live_Priority_class():
    from scrollkit.display.strategy import Priority
    pr = capabilities()["priorities"]
    assert pr == {"IDLE": Priority.IDLE, "LOW": Priority.LOW,
                  "NORMAL": Priority.NORMAL, "HIGH": Priority.HIGH,
                  "URGENT": Priority.URGENT, "SYSTEM": Priority.SYSTEM}


def test_content_types_include_the_text_classes_with_params():
    types = {t["name"]: t for t in capabilities()["content_types"]}
    assert "StaticText" in types and "ScrollingText" in types
    scrolling_params = {p["name"] for p in types["ScrollingText"]["params"]}
    assert {"text", "y", "color", "speed"} <= scrolling_params


def test_named_colors_are_ints_and_red_is_ff0000():
    colors = capabilities()["named_colors"]
    assert colors["red"] == 0xFF0000
    assert colors["blue"] == 0x0000FF
    assert all(isinstance(v, int) for v in colors.values())


def test_display_api_lists_draw_text():
    names = {m["name"] for m in capabilities()["display_api"]}
    assert {"draw_text", "set_pixel", "fill", "clear", "show"} <= names


def test_effects_exclude_the_abstract_base():
    names = {e["name"] for e in capabilities()["effects"]}
    assert "Effect" not in names          # abstract base is filtered out
    assert "FadeInEffect" in names


def test_as_text_is_a_readable_summary():
    text = as_text()
    assert "ScrollKit capabilities" in text
    assert "ScrollingText" in text and "Priorities:" in text
