"""Pixel-level metrics for headless verification (desktop-only, numpy).

Reads the simulator's true-color RGB888 buffer
(``matrix.pixel_buffer.get_buffer()`` -> ndarray ``(H, W, 3)`` uint8 — the same
array ``demos/.../rainbow.py::calibrate()`` inspects) and reduces it to a few
numbers an AI agent can reason about: is anything lit, how much of the panel is
covered, how many "bright" pixels there are, and a cheap signature for detecting
motion between frames.

These read the *logical* pixel buffer (pre-brightness, pre-LED-spacing), so the
numbers are independent of how the simulator happens to draw LEDs to the window.
"""

import numpy as np

# A pixel counts as "bright" when its channels sum above this — matches the
# ``r + g + b > 250`` rule the render smoke test uses.
BRIGHT_SUM_THRESHOLD = 250


def buffer_from_display(display):
    """Return the ``(H, W, 3)`` uint8 RGB buffer for a simulator display, or None.

    None when the display isn't a pixel-buffer simulator (e.g. a terminal or
    real hardware), so callers degrade gracefully instead of crashing.
    """
    matrix = getattr(display, "matrix", None)
    if matrix is None:
        return None
    pb = getattr(matrix, "pixel_buffer", None)
    if pb is None or not hasattr(pb, "get_buffer"):
        return None
    return pb.get_buffer()


def lit_mask(buffer):
    """Boolean ``(H, W)`` mask of pixels that are not pure black."""
    return np.any(buffer > 0, axis=2)


def bright_pixels(buffer, threshold=BRIGHT_SUM_THRESHOLD):
    """Count pixels whose ``R + G + B`` exceeds ``threshold``."""
    sums = buffer.astype(np.int32).sum(axis=2)
    return int(np.count_nonzero(sums > threshold))


def lit_pixels(buffer):
    """Count pixels that are lit at all (any channel > 0)."""
    return int(np.count_nonzero(lit_mask(buffer)))


def coverage(buffer):
    """Fraction (0..1) of the panel that is lit."""
    height, width = buffer.shape[0], buffer.shape[1]
    total = height * width
    if total == 0:
        return 0.0
    return lit_pixels(buffer) / total


def is_blank(buffer):
    """True when nothing at all is lit."""
    return lit_pixels(buffer) == 0


def signature(buffer):
    """Cheap content fingerprint for detecting change/motion between frames.

    Sensitive to any pixel change; stable within a process. Compare the
    signature of an early frame to a late frame to tell whether anything moved.
    """
    return hash(buffer.tobytes())


def snapshot(buffer):
    """All scalar metrics for one frame as a JSON-able dict.

    ``available`` is False (and everything zero/blank) when no pixel buffer was
    available, so the harness can report honestly rather than inventing numbers.
    """
    if buffer is None:
        return {"bright_pixels": 0, "lit_pixels": 0, "coverage": 0.0,
                "is_blank": True, "available": False}
    return {
        "bright_pixels": bright_pixels(buffer),
        "lit_pixels": lit_pixels(buffer),
        "coverage": round(coverage(buffer), 4),
        "is_blank": is_blank(buffer),
        "available": True,
    }
