"""Turn accumulated modeled frame costs into a human/AI-readable feasibility report.

Answers: "would this app actually run on the real hardware?" — estimated hardware
FPS, where the per-frame time goes, estimated peak RAM vs budget, and actionable
warnings. Always labels itself as an estimate when the profile is uncalibrated.

Desktop/simulator only.
"""

import math


def _one_sig_fig(x):
    """Round to one significant figure (so '~5 FPS', not '5.37 FPS')."""
    if x <= 0:
        return 0
    d = math.floor(math.log10(x))
    factor = 10 ** d
    return round(x / factor) * factor


def _median(values):
    s = sorted(values)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


class FeasibilityReport:
    """Estimated hardware performance for a run, built from a PerformanceManager."""

    def __init__(self, profile_name, confidence, source, calibrated,
                 est_hw_fps, median_frame_ms, worst_frame_ms, breakdown_ms,
                 est_peak_ram_bytes, ram_budget_bytes, warnings):
        self.profile_name = profile_name
        self.confidence = confidence
        self.source = source
        self.calibrated = calibrated
        self.est_hw_fps = est_hw_fps          # None if no frames were rendered
        self.median_frame_ms = median_frame_ms
        self.worst_frame_ms = worst_frame_ms
        self.breakdown_ms = breakdown_ms      # {category: ms} averaged per frame
        self.est_peak_ram_bytes = est_peak_ram_bytes
        self.ram_budget_bytes = ram_budget_bytes
        self.warnings = warnings

    # ------------------------------------------------------------------
    @classmethod
    def from_manager(cls, manager):
        profile = manager.profile
        frames = manager.frames
        n = len(frames)

        if n == 0:
            return cls(profile.name, profile.confidence, profile.source,
                       profile.is_calibrated, None, 0.0, 0.0, {},
                       manager.estimated_peak_ram_bytes(), profile.usable_ram_bytes,
                       ["No frames rendered yet — run the app (and call show()) first."])

        totals_us = [f.total_us for f in frames]
        median_us = _median(totals_us)
        worst_us = max(totals_us)
        est_fps = (1_000_000.0 / median_us) if median_us > 0 else None

        # Average per-category breakdown (ms), and which category dominates.
        cats = ("bitmap_rebuild_us", "refresh_us", "pixel_writes_us", "gc_us",
                "bulk_ops_us")
        breakdown_ms = {}
        for cat in cats:
            avg_us = sum(getattr(f, cat) for f in frames) / n
            breakdown_ms[cat.replace("_us", "")] = avg_us / 1000.0
        dominant = max(breakdown_ms, key=lambda k: breakdown_ms[k])

        peak_ram = manager.estimated_peak_ram_bytes()
        budget = profile.usable_ram_bytes

        warnings = []
        if est_fps is not None and est_fps < 1:
            warnings.append(
                "Frame would take ~%d ms on hardware (~%s FPS) — effectively frozen."
                % (round(median_us / 1000.0), _fps_text(est_fps, profile.is_calibrated)))
        elif est_fps is not None and est_fps < 10:
            warnings.append(
                "Frame would take ~%d ms on hardware (~%s FPS%s). Scrolling will stutter."
                % (round(median_us / 1000.0), _fps_text(est_fps, profile.is_calibrated),
                   "" if profile.is_calibrated else ", ESTIMATE"))
        if dominant == "bitmap_rebuild" and breakdown_ms["bitmap_rebuild"] > 0 \
                and breakdown_ms["bitmap_rebuild"] >= 0.5 * (median_us / 1000.0):
            warnings.append(
                "draw_text rebuilds a glyph bitmap every frame (the dominant cost on "
                "hardware). Cache the Label/content and only change .text when it "
                "actually changes, instead of redrawing every frame.")
        if peak_ram > budget:
            warnings.append(
                "Estimated peak RAM ~%d KB exceeds the modeled device budget of %d KB "
                "— won't fit. Reduce content/effects or disable the web server."
                % (peak_ram // 1024, budget // 1024))
        elif peak_ram > 0.8 * budget:
            warnings.append(
                "Estimated peak RAM ~%d KB is close to the %d KB budget — little "
                "headroom on hardware." % (peak_ram // 1024, budget // 1024))

        return cls(profile.name, profile.confidence, profile.source,
                   profile.is_calibrated, est_fps, median_us / 1000.0,
                   worst_us / 1000.0, breakdown_ms, peak_ram, budget, warnings)

    # ------------------------------------------------------------------
    def as_dict(self):
        return {
            "profile": self.profile_name,
            "confidence": self.confidence,
            "calibrated": self.calibrated,
            "source": self.source,
            "estimated_hardware_fps": self.est_hw_fps,
            "median_frame_ms": round(self.median_frame_ms, 2),
            "worst_frame_ms": round(self.worst_frame_ms, 2),
            "breakdown_ms": {k: round(v, 2) for k, v in self.breakdown_ms.items()},
            "estimated_peak_ram_bytes": self.est_peak_ram_bytes,
            "ram_budget_bytes": self.ram_budget_bytes,
            "warnings": list(self.warnings),
        }

    def as_text(self):
        lines = ["=== Hardware feasibility: %s ===" % self.profile_name]
        if self.calibrated:
            lines.append("  Confidence: MEASURED on device (%s)" % self.source)
        else:
            lines.append("  Confidence: ROUGH ESTIMATE, not measured on device (%s)"
                         % self.source)
        if self.est_hw_fps is None:
            lines.append("  Estimated hardware FPS: n/a (no frames rendered)")
        else:
            lines.append("  Estimated hardware FPS: ~%s   (median frame ~%d ms, worst ~%d ms)"
                         % (_fps_text(self.est_hw_fps, self.calibrated),
                            round(self.median_frame_ms), round(self.worst_frame_ms)))
        if self.breakdown_ms:
            parts = sorted(self.breakdown_ms.items(), key=lambda kv: -kv[1])
            lines.append("  Per-frame cost (avg): "
                         + " | ".join("%s %.1f ms" % (k, v) for k, v in parts))
        lines.append("  Estimated peak RAM: %d KB / %d KB budget"
                     % (self.est_peak_ram_bytes // 1024, self.ram_budget_bytes // 1024))
        if self.warnings:
            lines.append("  Warnings:")
            for w in self.warnings:
                lines.append("    - " + w)
        else:
            lines.append("  No feasibility warnings.")
        return "\n".join(lines)


def _fps_text(fps, calibrated):
    if fps is None:
        return "n/a"
    if calibrated:
        return "%.1f" % fps
    sig = _one_sig_fig(fps)
    return ("%g" % sig)
