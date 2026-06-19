"""Hardware timing/memory profile for modeling real-device performance.

Single source of truth for the (DESKTOP-ONLY) hardware-realism simulation: how
slow the real CircuitPython device is and how little RAM it has.

IMPORTANT — these numbers are ROUGH ENGINEERING ESTIMATES, not measurements. No
timing has been captured on a real MatrixPortal S3 yet. Replace them with real
numbers via ``HardwareProfile.from_measurements()`` once captured (see
``test/memory_baseline.py``). Reports built from an uncalibrated profile say so
and round to one significant figure to avoid false precision. Trust the RELATIVE
breakdown (which category dominates) more than the absolute FPS.

This module is part of the simulator package and is never imported on hardware.
"""

import json
import os
from dataclasses import dataclass


CONFIDENCE_ESTIMATE = "ROUGH_ESTIMATE_UNCALIBRATED"
CONFIDENCE_CALIBRATED = "CALIBRATED_FROM_DEVICE"

# A calibrated baseline captured on a real MatrixPortal S3 ships next to this
# module (written by test/claude/calibrate_device.py). When present it's used in
# preference to the estimate. Override the location with SCROLLKIT_HW_BASELINE.
_BASELINE_FILENAME = "matrixportal_s3_baseline.json"


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
    # --- Honesty ---
    confidence: str = CONFIDENCE_ESTIMATE
    source: str = "engineering estimate"

    @property
    def is_calibrated(self):
        return self.confidence == CONFIDENCE_CALIBRATED

    @classmethod
    def from_measurements(cls, path):
        """Build a CALIBRATED profile from a JSON file of measured values.

        The JSON may contain any subset of this dataclass's numeric fields; any
        omitted fall back to the MatrixPortal S3 estimate. Use after capturing
        real frame times / RAM on a device.
        """
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


def baseline_path():
    """Path to the shipped device baseline JSON (may not exist)."""
    return os.environ.get(
        "SCROLLKIT_HW_BASELINE",
        os.path.join(os.path.dirname(__file__), _BASELINE_FILENAME))


def matrixportal_s3_profile():
    """The MatrixPortal S3 profile to use by default.

    Returns a CALIBRATED profile built from the shipped device baseline when one
    is present (the common case now that real numbers have been captured), and
    falls back to the labeled ROUGH ESTIMATE otherwise. This is what the
    simulator and capability catalog use.
    """
    path = baseline_path()
    try:
        if path and os.path.exists(path):
            return HardwareProfile.from_measurements(path)
    except Exception:
        pass
    return matrixportal_s3_estimate()
