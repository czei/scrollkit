"""Conformance test for the simulator ``bitmaptools`` shim.

Replays a fixed battery of ``fill_region`` / ``blit`` operations through the shim
and asserts byte-identical output against the committed golden corpus
``bitmaptools_golden.json`` (authored from the CircuitPython semantics; recapture
on a real board with ``test/claude/bitmaptools_golden.py``).

Desktop-only: this NEVER reaches for a board. If the golden fixture is missing it
fails with a clear message rather than skipping.
"""

import json
import os

import pytest

pytest.importorskip("numpy")

from scrollkit.simulator import bitmaptools
from scrollkit.simulator.displayio import Bitmap

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "bitmaptools_golden.json")

W, H, VC = 8, 4, 16


def _golden():
    if not os.path.exists(GOLDEN_PATH):
        raise AssertionError(
            "Missing golden fixture %s — it is a committed CI fixture, not "
            "device-captured at test time. Recapture with "
            "test/claude/bitmaptools_golden.py on a board." % GOLDEN_PATH)
    with open(GOLDEN_PATH) as f:
        return json.load(f)


def _fresh():
    return Bitmap(W, H, VC)


def _src(rows):
    """Build a small source Bitmap from a list of x-rows (``_buffer[y][x]``)."""
    h = len(rows)
    w = len(rows[0])
    b = Bitmap(w, h, VC)
    for y in range(h):
        for x in range(w):
            b[x, y] = rows[y][x]
    return b


def _buf(b):
    return [[int(b[x, y]) for x in range(W)] for y in range(H)]


# The battery — one builder per golden key. Each returns the resulting 8x4 buffer.
def _case_fill_region_basic():
    b = _fresh(); bitmaptools.fill_region(b, 1, 1, 4, 3, 5); return _buf(b)


def _case_fill_region_clip_right():
    b = _fresh(); bitmaptools.fill_region(b, 6, 0, 20, 2, 7); return _buf(b)


def _case_fill_region_negative():
    b = _fresh(); bitmaptools.fill_region(b, -3, -1, 2, 2, 9); return _buf(b)


def _case_fill_region_empty():
    b = _fresh(); bitmaptools.fill_region(b, 3, 3, 3, 5, 4); return _buf(b)


def _case_fill_region_inverted():
    # x1 > x2 -> no-op on CircuitPython (NOT a reordered fill).
    b = _fresh(); bitmaptools.fill_region(b, 4, 0, 1, 2, 5); return _buf(b)


def _case_fill_region_full():
    b = _fresh(); bitmaptools.fill_region(b, 0, 0, 8, 4, 2); return _buf(b)


def _case_blit_basic():
    b = _fresh()
    bitmaptools.blit(b, _src([[1, 2], [3, 4]]), 3, 1)
    return _buf(b)


def _case_blit_skip_index():
    b = _fresh()
    bitmaptools.blit(b, _src([[0, 2], [3, 0]]), 1, 0, skip_index=0)
    return _buf(b)


def _case_blit_clip_negative():
    b = _fresh()
    bitmaptools.blit(b, _src([[1, 2], [3, 4]]), -1, -1)
    return _buf(b)


CASES = {
    "fill_region_basic": _case_fill_region_basic,
    "fill_region_clip_right": _case_fill_region_clip_right,
    "fill_region_negative": _case_fill_region_negative,
    "fill_region_empty": _case_fill_region_empty,
    "fill_region_inverted": _case_fill_region_inverted,
    "fill_region_full": _case_fill_region_full,
    "blit_basic": _case_blit_basic,
    "blit_skip_index": _case_blit_skip_index,
    "blit_clip_negative": _case_blit_clip_negative,
}


@pytest.mark.parametrize("name", sorted(CASES))
def test_shim_matches_golden(name):
    golden = _golden()
    assert name in golden, "golden fixture missing case: %s" % name
    assert CASES[name]() == golden[name]


def test_every_golden_case_is_exercised():
    golden = _golden()
    keys = {k for k in golden if not k.startswith("_")}
    assert keys == set(CASES), "battery and golden are out of sync"
