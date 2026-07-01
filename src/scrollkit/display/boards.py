# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Board registry: how ScrollKit builds a panel on each supported board.

ScrollKit runs the *same* app on more than one HUB75 driver board. The boards
differ in exactly three places — how the RGB matrix is constructed on
CircuitPython, the default panel geometry, and the calibrated performance profile
(that last one lives in ``simulator/core/hardware_profile.py``). This module owns
the first two and the board-detection logic.

This module is imported **on the device** (by ``display/unified.py``), so it must
stay CircuitPython-safe: no ``dataclasses``, no runtime ``typing``, no
``os.environ`` (use ``os.getenv``). All hardware imports (``rgbmatrix``,
``adafruit_matrixportal``, ``board`` …) are **function-local** inside the
``make_matrix`` builders, which only run on the real board — so the module
imports cleanly on the desktop and in unit tests with no hardware present.

To add a board, see ``docs/guide/hardware.md`` (the "Adding new hardware" guide).
"""

import os
import sys

# Canonical board ids (the keys used everywhere: settings, baselines, profiles).
MATRIXPORTAL_S3 = "adafruit_matrixportal_s3"
INTERSTATE75_W = "pimoroni_interstate75_w"

DEFAULT_BOARD_ID = MATRIXPORTAL_S3


# --- per-board matrix constructors (run ONLY on CircuitPython hardware) --------
#
# Each returns the triple UnifiedDisplay stores: (hardware, display, matrix).
# Imports are function-local on purpose — see the module docstring.

__all__ = ['BoardSpec', 'BOARDS', 'resolve_board', 'detect_board_id', 'DEFAULT_BOARD_ID', 'MATRIXPORTAL_S3', 'INTERSTATE75_W']

def _make_matrix_s3(spec, width, height, bit_depth):
    """Adafruit MatrixPortal S3: the adafruit_matrixportal wrapper (unchanged)."""
    from adafruit_matrixportal.matrix import Matrix
    m = Matrix(width=width, height=height, bit_depth=bit_depth)
    return m, m.display, m


def _make_matrix_interstate75(spec, width, height, bit_depth):
    """Pimoroni Interstate 75 / 75 W: direct rgbmatrix + framebufferio.

    Prefers the board's own RGBMatrix convenience aliases
    (``board.MTX_COMMON`` / ``board.MTX_ADDRESS``) so no GPIO numbers are
    hard-coded; falls back to the explicit Interstate 75 pin names if a given
    build doesn't expose them.
    """
    import board
    import rgbmatrix
    import framebufferio

    common = getattr(board, "MTX_COMMON", None)      # rgb_pins, clock/latch/oe
    address = getattr(board, "MTX_ADDRESS", None)    # tuple of address pins
    if common is not None and address is not None:
        matrix = rgbmatrix.RGBMatrix(
            width=width, height=height, bit_depth=bit_depth,
            addr_pins=address[:spec.addr_pin_count], **common)
    else:
        matrix = rgbmatrix.RGBMatrix(
            width=width, height=height, bit_depth=bit_depth,
            rgb_pins=[board.R0, board.G0, board.B0,
                      board.R1, board.G1, board.B1],
            addr_pins=[board.ROW_A, board.ROW_B, board.ROW_C,
                       board.ROW_D, board.ROW_E][:spec.addr_pin_count],
            clock_pin=board.CLK, latch_pin=board.LAT,
            output_enable_pin=board.OE)
    display = framebufferio.FramebufferDisplay(matrix, auto_refresh=False)
    return matrix, display, matrix


class BoardSpec:
    """Static description of a supported board.

    Args:
        board_id: canonical id (the registry key).
        name: human-readable board name.
        default_width / default_height: panel geometry used when the app does
            not pass explicit dimensions.
        pitch: physical LED pitch in mm (cosmetic; used by the simulator render).
        addr_pin_count: HUB75 address lines (4 for 64-row panels, 5 for 64-tall).
        matrix_builder: callable ``(spec, width, height, bit_depth)`` returning
            ``(hardware, display, matrix)`` — runs only on CircuitPython.
    """

    def __init__(self, board_id, name, default_width, default_height, pitch,
                 addr_pin_count, matrix_builder):
        self.board_id = board_id
        self.name = name
        self.default_width = default_width
        self.default_height = default_height
        self.pitch = pitch
        self.addr_pin_count = addr_pin_count
        self._matrix_builder = matrix_builder

    def make_matrix(self, width, height, bit_depth):
        """Construct the RGB matrix on hardware (CircuitPython only)."""
        return self._matrix_builder(self, width, height, bit_depth)


BOARDS = {
    MATRIXPORTAL_S3: BoardSpec(
        MATRIXPORTAL_S3, "Adafruit MatrixPortal S3 (ESP32-S3)",
        default_width=64, default_height=32, pitch=3.0, addr_pin_count=4,
        matrix_builder=_make_matrix_s3),
    INTERSTATE75_W: BoardSpec(
        INTERSTATE75_W, "Pimoroni Interstate 75 W (RP2350)",
        default_width=64, default_height=32, pitch=3.0, addr_pin_count=4,
        matrix_builder=_make_matrix_interstate75),
}


# Map the on-device ``board.board_id`` (or ``os.uname().machine``) strings to a
# canonical id. The exact RP2350 "W" id should be confirmed on the real board;
# the substring fallback in _map_ondevice_id() catches naming variants.
_ONDEVICE_ID_MAP = {
    "adafruit_matrixportal_s3": MATRIXPORTAL_S3,
    "pimoroni_interstate75": INTERSTATE75_W,
    "pimoroni_interstate75_w": INTERSTATE75_W,
    "pimoroni_interstate75_rp2350": INTERSTATE75_W,
    "pimoroni_interstate75_w_rp2350": INTERSTATE75_W,
}


def _read_ondevice_id():
    """The raw board id string on CircuitPython; ``None`` on desktop."""
    if not (hasattr(sys, "implementation")
            and sys.implementation.name == "circuitpython"):
        return None
    try:
        import board
        bid = getattr(board, "board_id", None)
        if bid:
            return bid
    except Exception:
        pass
    try:
        return os.uname().machine
    except Exception:
        return None


def _map_ondevice_id(raw):
    """Resolve a raw on-device id (or any id string) to a canonical board id."""
    if not raw:
        return DEFAULT_BOARD_ID
    key = str(raw).strip().lower()
    if key in BOARDS:
        return key
    if key in _ONDEVICE_ID_MAP:
        return _ONDEVICE_ID_MAP[key]
    if "interstate75" in key or "interstate 75" in key:
        return INTERSTATE75_W
    if "matrixportal" in key:
        return MATRIXPORTAL_S3
    return DEFAULT_BOARD_ID


def detect_board_id():
    """Best-effort canonical board id for the board we're running on.

    On CircuitPython this reads ``board.board_id``; on the desktop there is no
    board, so it returns the default (MatrixPortal S3).
    """
    return _map_ondevice_id(_read_ondevice_id())


def resolve_board(board=None):
    """Return the :class:`BoardSpec` to use.

    Precedence: an explicit ``board`` argument, then the ``SCROLLKIT_HW_BOARD``
    environment variable, then auto-detection, then the default board. Accepts a
    canonical id or a raw on-device id; unknown ids fall back to the default.
    """
    chosen = board
    if not chosen:
        try:
            chosen = os.getenv("SCROLLKIT_HW_BOARD")
        except Exception:
            chosen = None
    if not chosen:
        chosen = detect_board_id()
    return BOARDS.get(_map_ondevice_id(chosen), BOARDS[DEFAULT_BOARD_ID])
