"""Models how slow the real CircuitPython hardware runs.

It works by ACCUMULATING modeled time per frame — it does NOT actually sleep
(unless ``throttle=True``), so the simulator and the headless test suite stay
fast. The accumulated time becomes an estimated *hardware* frame time / FPS in a
FeasibilityReport.

Wired into the previously-dead hooks in ``core/led_matrix.py`` plus one hook in
``adafruit_display_text/label.py`` (looked up lazily via the module-level active
manager, so there's zero cost and no constructor threading when it's off).

Desktop/simulator only — never imported on hardware.
"""

from collections import deque

from .hardware_profile import HardwareProfile  # noqa: F401  (re-exported for callers)


# --- module-level active manager (for the lazy Label hook) ---------------------
_active = None


def set_active(manager):
    """Register the manager the Label bitmap-rebuild hook should report to."""
    global _active
    _active = manager


def get_active():
    """Return the active PerformanceManager, or None when disabled (the default)."""
    return _active


class FrameCost:
    """Modeled microseconds for one frame, split by category."""

    __slots__ = ("pixel_writes_us", "refresh_us", "bitmap_rebuild_us", "gc_us")

    def __init__(self):
        self.pixel_writes_us = 0.0
        self.refresh_us = 0.0
        self.bitmap_rebuild_us = 0.0
        self.gc_us = 0.0

    @property
    def total_us(self):
        return (self.pixel_writes_us + self.refresh_us
                + self.bitmap_rebuild_us + self.gc_us)

    def as_dict(self):
        return {
            "pixel_writes_us": self.pixel_writes_us,
            "refresh_us": self.refresh_us,
            "bitmap_rebuild_us": self.bitmap_rebuild_us,
            "gc_us": self.gc_us,
            "total_us": self.total_us,
        }


class PerformanceManager:
    """Cost accumulator behind the simulator's performance hooks."""

    def __init__(self, profile, enabled=True, throttle=False, history=120,
                 ambient_warnings=None, warn_interval=30, stutter_fps=10.0):
        self.profile = profile
        self.enabled = enabled            # read by led_matrix hooks
        self.throttle = throttle          # if True, also real-sleep to crawl the window
        # Periodic console "this would stutter on hardware" nags. Default: follow
        # throttle (visceral mode), but can be toggled independently (so tests can
        # exercise the warning logic without actually sleeping).
        self.ambient_warnings = throttle if ambient_warnings is None else ambient_warnings
        self.warn_interval = warn_interval   # min frames between ambient nags
        self.stutter_fps = stutter_fps       # warn when modeled FPS drops below this
        self.last_warning = None             # most recent ambient nag (for UIs/tests)
        self._frame = FrameCost()
        self._frames = deque(maxlen=history)
        self._frame_index = 0
        self._last_warn_frame = 0
        self._max_bitmap_px = 0           # largest live text bitmap seen (RAM proxy)

    # --- hooks called by core/led_matrix.py (existing signatures) -------------
    def simulate_instruction_delay(self, n):
        """Per matrix.set_pixel(): n is a fixed weight, not a pixel count."""
        self._frame.pixel_writes_us += n * self.profile.pixel_write_us

    def simulate_io_operation(self, kind):
        """A display.refresh() — also the frame boundary (one refresh == one frame)."""
        if kind == "display_refresh":
            self._frame.refresh_us += self.profile.full_refresh_us
            self._end_frame()

    def simulate_gc_pause(self):
        if self._frame_index % self.profile.gc_every_n_frames == 0:
            self._frame.gc_us += self.profile.gc_pause_us

    # --- hook called by adafruit_display_text/label.py _update_text -----------
    def account_bitmap_rebuild(self, width_px, height_px):
        """A Label rebuilt its glyph bitmap (the dominant cost for scrolling text)."""
        px = max(0, width_px) * max(0, height_px)
        self._frame.bitmap_rebuild_us += px * self.profile.bitmap_rebuild_us_per_px
        if px > self._max_bitmap_px:
            self._max_bitmap_px = px

    # --- frame bookkeeping ----------------------------------------------------
    def _end_frame(self):
        total_us = self._frame.total_us
        self._frames.append(self._frame)
        self._frame_index += 1
        # Visceral mode: actually sleep the modeled frame time so the live window
        # crawls at hardware speed.
        if self.throttle and total_us > 0:
            import time
            try:
                time.sleep(total_us / 1_000_000.0)
            except (ValueError, OSError):
                pass
        if self.ambient_warnings:
            self._maybe_emit_ambient_warning(total_us)
        self._frame = FrameCost()

    def _maybe_emit_ambient_warning(self, frame_total_us):
        """Periodically nag when the modeled frame time implies a stuttery FPS.

        Rate-limited to one nag per ``warn_interval`` frames so it informs rather
        than floods. Routed through ``_emit`` so callers/tests can redirect it.
        """
        if frame_total_us <= 0:
            return
        if self._frame_index - self._last_warn_frame < self.warn_interval:
            return
        fps = 1_000_000.0 / frame_total_us
        if fps >= self.stutter_fps:
            return
        self._last_warn_frame = self._frame_index
        msg = ("[hw-sim] frame %d: ~%d ms/frame (~%d FPS) on the real device — "
               "this would stutter. (estimate)"
               % (self._frame_index, round(frame_total_us / 1000.0), round(fps)))
        self.last_warning = msg
        self._emit(msg)

    def _emit(self, msg):
        """Where ambient nags go. Overridable; defaults to stdout."""
        print(msg)

    # --- reporting ------------------------------------------------------------
    @property
    def frames(self):
        return list(self._frames)

    def estimated_peak_ram_bytes(self):
        """Rough modeled peak RAM: app floor + largest live text bitmap."""
        return int(self.profile.base_app_ram_bytes
                   + self._max_bitmap_px * self.profile.bytes_per_label_px)

    def report(self):
        from .feasibility import FeasibilityReport
        return FeasibilityReport.from_manager(self)
