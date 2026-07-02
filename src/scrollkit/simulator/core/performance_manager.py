# Copyright (c) 2024-2026 Michael Czeiszperger
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

    __slots__ = ("pixel_writes_us", "refresh_us", "bitmap_rebuild_us", "gc_us",
                 "bulk_ops_us")

    def __init__(self):
        self.pixel_writes_us = 0.0
        self.refresh_us = 0.0
        self.bitmap_rebuild_us = 0.0
        self.gc_us = 0.0
        self.bulk_ops_us = 0.0     # C bulk ops (fill_region/blit) from the painters

    @property
    def total_us(self):
        return (self.pixel_writes_us + self.refresh_us
                + self.bitmap_rebuild_us + self.gc_us + self.bulk_ops_us)

    def as_dict(self):
        return {
            "pixel_writes_us": self.pixel_writes_us,
            "refresh_us": self.refresh_us,
            "bitmap_rebuild_us": self.bitmap_rebuild_us,
            "gc_us": self.gc_us,
            "bulk_ops_us": self.bulk_ops_us,
            "total_us": self.total_us,
        }


class PerformanceManager:
    """Cost accumulator behind the simulator's performance hooks."""

    def __init__(self, profile, enabled=True, throttle=False, history=120,
                 ambient_warnings=None, warn_interval=30, stutter_fps=10.0,
                 strict=False, target_fps=20.0, warmup_frames=2,
                 gate_window=8, transient_factor=2.0):
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
        # --- strict feasibility gate (opt-in; default off keeps the warning path)
        self.strict = strict
        self.target_fps = target_fps
        self.warmup_frames = warmup_frames   # leading frames exempt (one-time setup)
        self.gate_window = max(1, gate_window)
        self.transient_factor = transient_factor
        self.frame_budget_us = 1_000_000.0 / target_fps          # 50_000 at 20 fps
        self.transient_budget_us = self.frame_budget_us * transient_factor
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

    # --- hook called by the display span/rect painters + overlay --------------
    def account_bulk_op(self, kind, px):
        """A C bulk op (``fill_region`` / ``blit``) touched ``px`` clipped pixels.

        Cost = ``bulk_base_us`` (fixed per-call C dispatch) + ``px * slope`` for
        the op. The base over-counts slightly on purpose so the strict gate fails
        safe. ``px`` is the clipped/scanned pixel count (a fully-clipped no-op
        still pays the base).
        """
        px = max(0, px)
        if kind == "blit":
            slope = self.profile.blit_us_per_px
        else:  # "fill_region" (and any other bounded fill)
            slope = self.profile.fill_region_us_per_px
        self._frame.bulk_ops_us += self.profile.bulk_base_us + px * slope

    # --- frame bookkeeping ----------------------------------------------------
    def _end_frame(self):
        total_us = self._frame.total_us
        self._frames.append(self._frame)
        self._frame_index += 1
        # Reset the live frame BEFORE the strict gate can raise, so a caller that
        # catches FeasibilityError and keeps rendering doesn't accumulate the next
        # frame's cost onto the (already-appended) aborted frame and corrupt the
        # rolling history. The appended frame stays valid in self._frames.
        self._frame = FrameCost()
        # Strict feasibility gate (opt-in). Past the warmup grace, a sustained
        # over-budget run (steady-state median) or a single catastrophic frame
        # (transient ceiling) or a RAM breach raises FeasibilityError, stopping
        # the run at the offending frame. Default (strict=False) skips all of this
        # so the warning path below is unchanged.
        if self.strict and self._frame_index > self.warmup_frames:
            self._enforce_strict(total_us)
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

    def _enforce_strict(self, total_us):
        """Raise FeasibilityError if this frame busts the device budget."""
        from ...exceptions import FeasibilityError
        # 1) Transient ceiling: a single catastrophic frame (e.g. 2 full rebuilds).
        if total_us > self.transient_budget_us:
            raise FeasibilityError(self._budget_message(
                "single frame", total_us, self.transient_budget_us))
        # 2) Steady-state: the median over the rolling window must hold the budget.
        #    Only meaningful once the window is full, so an isolated rebuild spike
        #    is absorbed rather than triggering a false trip.
        totals = [f.total_us for f in self._frames]
        if len(totals) >= self.gate_window:
            window = totals[-self.gate_window:]
            med = self._median(window)
            if med > self.frame_budget_us:
                raise FeasibilityError(self._budget_message(
                    "median over %d frames" % self.gate_window, med,
                    self.frame_budget_us))
        # 3) RAM: must fit the usable device RAM.
        peak = self.estimated_peak_ram_bytes()
        if peak > self.profile.usable_ram_bytes:
            raise FeasibilityError(
                "[hw-strict] frame %d: modeled peak RAM ~%d KB exceeds the device's "
                "usable ~%d KB. Reduce content/effects."
                % (self._frame_index, peak // 1024,
                   self.profile.usable_ram_bytes // 1024))

    def _budget_message(self, scope, us, budget_us):
        fps = 1_000_000.0 / us if us > 0 else 0.0
        budget_fps = 1_000_000.0 / budget_us if budget_us > 0 else 0.0
        return ("[hw-strict] frame %d: %s ~%d ms/frame (~%d fps) exceeds the "
                "%d ms budget (%d fps); dominant: %s. Reuse Labels, avoid per-frame "
                "glyph rebuild, and express bounded work through the C bulk painters."
                % (self._frame_index, scope, round(us / 1000.0), round(fps),
                   round(budget_us / 1000.0), round(budget_fps),
                   self._dominant_component()))

    def _dominant_component(self):
        last = self._frames[-1] if self._frames else self._frame
        cats = last.as_dict()
        cats.pop("total_us", None)
        if not cats:
            return "unknown"
        return max(cats, key=lambda k: cats[k]).replace("_us", "")

    @staticmethod
    def _median(values):
        s = sorted(values)
        n = len(s)
        if n == 0:
            return 0.0
        mid = n // 2
        return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0

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
