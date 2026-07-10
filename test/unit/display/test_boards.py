"""Board abstraction: detection, selection, per-board profile, matrix dispatch.

These verify the board-agnostic plumbing on the desktop, with no real hardware,
so the Interstate 75 W path can be exercised before the board physically arrives.
The on-device matrix constructors are checked by mocking the CircuitPython
hardware modules (rgbmatrix / framebufferio / board / adafruit_matrixportal).
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import sys
import types

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display import boards
from scrollkit.display.boards import (
    BOARDS, MATRIXPORTAL_S3, INTERSTATE75_W, resolve_board, detect_board_id)
from scrollkit.simulator.core.hardware_profile import profile_for


# --- detection / mapping -----------------------------------------------------

def test_map_ondevice_id_canonical_and_variants():
    assert boards._map_ondevice_id("adafruit_matrixportal_s3") == MATRIXPORTAL_S3
    assert boards._map_ondevice_id("pimoroni_interstate75_w") == INTERSTATE75_W
    assert boards._map_ondevice_id("pimoroni_interstate75_w_rp2350") == INTERSTATE75_W
    # substring fallback catches naming variants / human strings
    assert boards._map_ondevice_id("Pimoroni Interstate 75 W") == INTERSTATE75_W
    assert boards._map_ondevice_id("some_matrixportal_s3_clone") == MATRIXPORTAL_S3


def test_map_ondevice_id_unknown_and_none_default_to_s3():
    assert boards._map_ondevice_id("totally_unknown_board") == MATRIXPORTAL_S3
    assert boards._map_ondevice_id(None) == MATRIXPORTAL_S3


def test_read_ondevice_id_is_none_on_desktop():
    # We're not on CircuitPython, so there's no board to read.
    assert boards._read_ondevice_id() is None


def test_detect_board_id_defaults_to_s3_on_desktop():
    assert detect_board_id() == MATRIXPORTAL_S3


# --- resolve_board precedence: explicit > env > detect > default -------------

def test_resolve_board_default_is_s3(monkeypatch):
    monkeypatch.delenv("SCROLLKIT_HW_BOARD", raising=False)
    assert resolve_board().board_id == MATRIXPORTAL_S3


def test_resolve_board_explicit_wins(monkeypatch):
    monkeypatch.setenv("SCROLLKIT_HW_BOARD", MATRIXPORTAL_S3)
    assert resolve_board(INTERSTATE75_W).board_id == INTERSTATE75_W


def test_resolve_board_env_override(monkeypatch):
    monkeypatch.setenv("SCROLLKIT_HW_BOARD", INTERSTATE75_W)
    assert resolve_board().board_id == INTERSTATE75_W


def test_resolve_board_unknown_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("SCROLLKIT_HW_BOARD", raising=False)
    assert resolve_board("nonsense_board").board_id == MATRIXPORTAL_S3


# --- per-board performance profile ------------------------------------------

def test_s3_profile_is_calibrated_and_roomy():
    p = profile_for(MATRIXPORTAL_S3)
    assert p.is_calibrated            # the S3 baseline JSON ships in the package


def test_i75w_profile_is_uncalibrated_estimate_with_less_ram():
    i75 = profile_for(INTERSTATE75_W)
    s3 = profile_for(MATRIXPORTAL_S3)
    assert not i75.is_calibrated
    assert "ESTIMATE" in i75.name
    # RP2350 on-chip SRAM is far smaller than the S3's PSRAM-backed budget.
    assert i75.usable_ram_bytes < s3.usable_ram_bytes


# --- on-device matrix construction (mocked hardware) ------------------------

def test_make_matrix_s3_uses_adafruit_matrixportal():
    class FakeMatrix:
        def __init__(self, width, height, bit_depth):
            self.args = (width, height, bit_depth)
            self.display = object()

    matrix_mod = types.ModuleType("adafruit_matrixportal.matrix")
    matrix_mod.Matrix = FakeMatrix
    pkg = types.ModuleType("adafruit_matrixportal")
    pkg.matrix = matrix_mod

    with pytest.MonkeyPatch().context() as mp:
        mp.setitem(sys.modules, "adafruit_matrixportal", pkg)
        mp.setitem(sys.modules, "adafruit_matrixportal.matrix", matrix_mod)
        hw, disp, mx = BOARDS[MATRIXPORTAL_S3].make_matrix(64, 32, 4)

    assert isinstance(hw, FakeMatrix)
    assert hw.args == (64, 32, 4)
    assert disp is hw.display
    assert mx is hw


def test_make_matrix_i75w_uses_rgbmatrix_with_board_aliases():
    captured = {}

    class FakeRGBMatrix:
        def __init__(self, **kw):
            captured.update(kw)

    class FakeFramebufferDisplay:
        def __init__(self, matrix, auto_refresh=True):
            self.matrix = matrix
            self.auto_refresh = auto_refresh

    board_mod = types.ModuleType("board")
    board_mod.MTX_COMMON = {"rgb_pins": ["R0", "G0", "B0"],
                            "clock_pin": "CLK", "latch_pin": "LAT",
                            "output_enable_pin": "OE"}
    board_mod.MTX_ADDRESS = ("A", "B", "C", "D", "E")
    rgbmatrix_mod = types.ModuleType("rgbmatrix")
    rgbmatrix_mod.RGBMatrix = FakeRGBMatrix
    fb_mod = types.ModuleType("framebufferio")
    fb_mod.FramebufferDisplay = FakeFramebufferDisplay

    with pytest.MonkeyPatch().context() as mp:
        mp.setitem(sys.modules, "board", board_mod)
        mp.setitem(sys.modules, "rgbmatrix", rgbmatrix_mod)
        mp.setitem(sys.modules, "framebufferio", fb_mod)
        hw, disp, mx = BOARDS[INTERSTATE75_W].make_matrix(64, 32, 4)

    assert isinstance(hw, FakeRGBMatrix)
    assert captured["width"] == 64 and captured["height"] == 32
    assert captured["bit_depth"] == 4
    # addr pins sliced to the spec's addr_pin_count (4 for a 64x32 panel)
    assert captured["addr_pins"] == ("A", "B", "C", "D")
    # rgb/clock/latch/oe come straight from board.MTX_COMMON
    assert captured["rgb_pins"] == ["R0", "G0", "B0"]
    assert isinstance(disp, FakeFramebufferDisplay)
    assert mx is hw


def test_make_matrix_i75w_falls_back_to_named_pins():
    captured = {}

    class FakeRGBMatrix:
        def __init__(self, **kw):
            captured.update(kw)

    class FakeFramebufferDisplay:
        def __init__(self, matrix, auto_refresh=True):
            self.matrix = matrix
            self.auto_refresh = auto_refresh

    board_mod = types.ModuleType("board")
    for name in ("R0", "G0", "B0", "R1", "G1", "B1", "ROW_A", "ROW_B",
                 "ROW_C", "ROW_D", "ROW_E", "CLK", "LAT", "OE"):
        setattr(board_mod, name, name)
    rgbmatrix_mod = types.ModuleType("rgbmatrix")
    rgbmatrix_mod.RGBMatrix = FakeRGBMatrix
    fb_mod = types.ModuleType("framebufferio")
    fb_mod.FramebufferDisplay = FakeFramebufferDisplay

    with pytest.MonkeyPatch().context() as mp:
        mp.setitem(sys.modules, "board", board_mod)
        mp.setitem(sys.modules, "rgbmatrix", rgbmatrix_mod)
        mp.setitem(sys.modules, "framebufferio", fb_mod)
        hw, disp, mx = BOARDS[INTERSTATE75_W].make_matrix(64, 32, 4)

    assert isinstance(hw, FakeRGBMatrix)
    assert captured["rgb_pins"] == ["R0", "G0", "B0", "R1", "G1", "B1"]
    assert captured["addr_pins"] == ["ROW_A", "ROW_B", "ROW_C", "ROW_D"]
    assert captured["clock_pin"] == "CLK"
    assert captured["latch_pin"] == "LAT"
    assert captured["output_enable_pin"] == "OE"
    assert isinstance(disp, FakeFramebufferDisplay)
    assert mx is hw


# --- UnifiedDisplay wiring (desktop; no hardware) ---------------------------

def test_unified_display_back_compat_defaults_to_s3():
    from scrollkit.display.unified import UnifiedDisplay
    d = UnifiedDisplay()
    assert d.width == 64 and d.height == 32
    assert d._board_id == MATRIXPORTAL_S3

    d2 = UnifiedDisplay(64, 32)         # positional, the historical call
    assert d2.width == 64 and d2.height == 32
    assert d2._board_id == MATRIXPORTAL_S3


def test_unified_display_selects_board():
    from scrollkit.display.unified import UnifiedDisplay
    d = UnifiedDisplay(board=INTERSTATE75_W)
    assert d._board_id == INTERSTATE75_W
    assert d.width == 64 and d.height == 32   # board default geometry


def test_unified_display_hw_sim_uses_selected_board_profile(monkeypatch):
    import asyncio
    from scrollkit.display.unified import UnifiedDisplay
    monkeypatch.setenv("SCROLLKIT_HW_SIM", "1")
    monkeypatch.delenv("SCROLLKIT_HW_BOARD", raising=False)

    d = UnifiedDisplay(board=INTERSTATE75_W)
    asyncio.run(d.initialize())
    assert d._perf is not None
    assert "Interstate" in d._perf.profile.name
    assert not d._perf.profile.is_calibrated
