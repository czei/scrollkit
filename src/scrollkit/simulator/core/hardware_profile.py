# Copyright (c) 2024-2026 Michael Czeiszperger
"""Hardware timing/memory profile for modeling real-device performance.

Single source of truth for the (DESKTOP-ONLY) hardware-realism simulation: how
slow the real CircuitPython device is and how little RAM it has.

IMPORTANT — the hard-coded numbers in the ``*_estimate()`` builders below are
ROUGH ENGINEERING ESTIMATES, used only as a fallback. When a board's calibrated
baseline JSON is present, ``profile_for()`` loads it in preference (via
``HardwareProfile.from_measurements()``) and flips confidence to
``CALIBRATED_FROM_DEVICE``. The shipped ``matrixportal_s3_baseline.json`` WAS
measured on a real MatrixPortal S3, so the default S3 profile is calibrated;
recapture with ``test/claude/calibrate_device.py``. Reports built from an
uncalibrated profile say so and round to one significant figure to avoid false
precision. Trust the RELATIVE breakdown (which category dominates) more than the
absolute FPS.

This module is part of the simulator package and is never imported on hardware.
"""

import json
import os
from dataclasses import dataclass


CONFIDENCE_ESTIMATE = "ROUGH_ESTIMATE_UNCALIBRATED"
CONFIDENCE_CALIBRATED = "CALIBRATED_FROM_DEVICE"

# Calibrated baselines (captured on a real board by test/claude/calibrate_device.py)
# ship next to this module, one JSON per board. When a board's file is present it's
# used in preference to that board's estimate. The S3 file keeps its historical name
# rather than following the canonical-id convention, so it's mapped explicitly.
# Override the location for the default board with SCROLLKIT_HW_BASELINE.
_DEFAULT_BOARD_ID = "adafruit_matrixportal_s3"
_BASELINE_FILENAMES = {
    "adafruit_matrixportal_s3": "matrixportal_s3_baseline.json",
    "pimoroni_interstate75_w": "pimoroni_interstate75_w_baseline.json",
}


@dataclass(frozen=True)
class HardwareProfile:
    """A device's modeled timing and memory characteristics."""

    name: str
    # --- Memory (bytes) ---
    usable_ram_bytes: int          # RAM free to the app after CP + displayio overhead
    base_app_ram_bytes: int        # modeled floor a running app costs
    bytes_per_label_px: float      # RAM per Label bitmap pixel
    # --- Timing (microseconds) ---
    pixel_write_us: float          # per matrix.set_pixel() during a group render
    full_refresh_us: float         # per display.refresh() (group render + panel update)
    bitmap_rebuild_us_per_px: float  # per pixel of a rebuilt text bitmap (the CP killer)
    gc_pause_us: float             # modeled garbage-collection stall
    gc_every_n_frames: int         # how often a GC pause is modeled
    # --- C bulk-op costs (fill_region / blit via bitmaptools) ---
    # Defaulted so existing callers/baselines are unaffected. Seeded from
    # device_benchmarks.json: fill_region ~147 us / 512 px (~0.287 us/px),
    # blit ~160 us / 256 px (~0.623 us/px). bulk_base_us is a conservative fixed
    # per-call C-dispatch overhead (over-counts slightly so the strict gate fails
    # safe). TODO: capture these at 2-3 sizes to fit base+slope rather than estimate.
    bulk_base_us: float = 12.0
    fill_region_us_per_px: float = 0.287
    blit_us_per_px: float = 0.623
    # --- Honesty ---
    confidence: str = CONFIDENCE_ESTIMATE
    source: str = "engineering estimate"

    @property
    def is_calibrated(self):
        return self.confidence == CONFIDENCE_CALIBRATED

    @classmethod
    def from_measurements(cls, path, base=None):
        """Build a CALIBRATED profile from a JSON file of measured values.

        The JSON may contain any subset of this dataclass's numeric fields; any
        omitted fall back to ``base`` (that board's estimate, or the MatrixPortal
        S3 estimate by default). Use after capturing real frame times / RAM on a
        device.
        """
        if base is None:
            base = matrixportal_s3_estimate()
        fields = {name: getattr(base, name) for name in base.__dataclass_fields__}
        with open(path) as f:
            data = json.load(f)
        for key, value in data.items():
            if key in fields and not key.startswith("_") and value is not None:
                fields[key] = value
        fields["confidence"] = CONFIDENCE_CALIBRATED
        if not data.get("source"):    # keep a descriptive source if the file gave one
            fields["source"] = str(path)
        return cls(**fields)


def matrixportal_s3_estimate():
    """Rough ESTIMATE for the Adafruit MatrixPortal S3 (ESP32-S3) + 64x32 panel.

    Premise (documented assumption): CircuitPython on the S3 is roughly two orders
    of magnitude slower than desktop pygame. Simple scrolling text runs ~15-25
    FPS; busy multi-element frames drop to single digits. RAM free to an app is on
    the order of ~180 KB after CircuitPython, displayio, and the Adafruit
    libraries. Every value below is an estimate, flagged UNCALIBRATED.
    """
    return HardwareProfile(
        name="Adafruit MatrixPortal S3 (64x32) [ESTIMATE]",
        # Memory: ~180 KB free; an app floors around ~40 KB; a 2-color Label
        # bitmap costs ~0.5 byte/px (packed bits + object overhead).
        usable_ram_bytes=180_000,
        base_app_ram_bytes=40_000,
        bytes_per_label_px=0.5,
        # Timing: interpreted per-pixel writes are slow; the dominant cost for
        # scrolling text is rebuilding the glyph bitmap every frame (per-pixel
        # Python loop), which is why bitmap_rebuild_us_per_px is large.
        pixel_write_us=5.0,
        full_refresh_us=5_000.0,
        bitmap_rebuild_us_per_px=75.0,
        gc_pause_us=15_000.0,
        gc_every_n_frames=30,
    )


def interstate75w_estimate():
    """Rough ESTIMATE for the Pimoroni Interstate 75 W (RP2350) + 64x32 panel.

    UNCALIBRATED — no timing has been captured on a real Interstate 75 W yet.
    Premise (documented assumption): the RP2350 (dual Cortex-M33 @ ~150 MHz)
    drives HUB75 via PIO/DMA, so refresh is efficient, but it has only ~520 KB
    on-chip SRAM and — unlike the S3's 2 MB PSRAM — no large PSRAM by default,
    so RAM free to an app is far tighter (the RAM feasibility gate matters more
    here). Interpreted-Python cost is in the same order as the S3. Replace every
    value below by running test/claude/calibrate_device.py --board
    pimoroni_interstate75_w once the board is in hand.
    """
    return HardwareProfile(
        name="Pimoroni Interstate 75 W (64x32) [ESTIMATE]",
        # Memory: ~520 KB SRAM, no PSRAM; after CircuitPython + displayio + the
        # rgbmatrix framebuffer, an app has on the order of ~200 KB.
        usable_ram_bytes=200_000,
        base_app_ram_bytes=40_000,
        bytes_per_label_px=0.5,
        # Timing: PIO/DMA refresh estimated similar to the S3; interpreted
        # per-pixel/glyph work slightly higher at the lower clock.
        pixel_write_us=5.0,
        full_refresh_us=5_000.0,
        bitmap_rebuild_us_per_px=80.0,
        gc_pause_us=15_000.0,
        gc_every_n_frames=30,
    )


def _estimate_for(board_id):
    """That board's labeled ROUGH ESTIMATE profile (default: S3)."""
    if board_id == "pimoroni_interstate75_w":
        return interstate75w_estimate()
    return matrixportal_s3_estimate()


def baseline_path(board_id=_DEFAULT_BOARD_ID):
    """Path to a board's shipped device baseline JSON (may not exist).

    ``SCROLLKIT_HW_BASELINE`` overrides the path for the default board.
    """
    if board_id == _DEFAULT_BOARD_ID:
        env = os.environ.get("SCROLLKIT_HW_BASELINE")
        if env:
            return env
    filename = _BASELINE_FILENAMES.get(board_id, "%s_baseline.json" % board_id)
    return os.path.join(os.path.dirname(__file__), filename)


def profile_for(board_id=_DEFAULT_BOARD_ID):
    """The performance profile for ``board_id``.

    Returns a CALIBRATED profile built from that board's shipped baseline when one
    is present, and falls back to the labeled ROUGH ESTIMATE otherwise. This is
    what the simulator and capability catalog use.
    """
    estimate = _estimate_for(board_id)
    path = baseline_path(board_id)
    try:
        if path and os.path.exists(path):
            return HardwareProfile.from_measurements(path, base=estimate)
    except Exception:
        pass
    return estimate


def matrixportal_s3_profile():
    """The default (MatrixPortal S3) profile. Back-compat alias for ``profile_for``."""
    return profile_for(_DEFAULT_BOARD_ID)
