"""Headless verification harness — the AI agent's primary tool.

``run_headless(app, frames=N)`` drives a ``ScrollKitApp``'s display loop
deterministically in a dummy (no-window) pygame, captures a screenshot plus
pixel/feasibility metrics, and returns a JSON-able ``RunResult`` — no human and
no real hardware required. The whole point: an AI can write an app, run it here,
see that it actually rendered and advanced, read an honest estimate of whether
it would survive on the real (slow, RAM-tiny) MatrixPortal S3, and iterate.

Determinism: the loop is stepped exactly ``frames`` times with no inter-frame
sleep, so the same app + same frame count always reaches the same visual state
(reproducible compare across edits) and the run finishes fast. ``seconds=S`` is
sugar for ``frames = round(S * 20)`` (the display loop targets 20 FPS).

Desktop-only — imported via ``scrollkit.dev``, which raises on CircuitPython.
"""

import os

from . import metrics as _metrics

# The display loop in app/base.py paces itself at 20 FPS; seconds->frames uses it.
TARGET_FPS = 20
DEFAULT_FRAMES = 120


class RunResult:
    """JSON-able summary of a headless run (what the AI inspects)."""

    def __init__(self, **kw):
        self.frames = kw.get("frames", 0)
        self.estimated_hardware_fps = kw.get("estimated_hardware_fps")
        self.bright_pixels = kw.get("bright_pixels", 0)
        self.lit_pixels = kw.get("lit_pixels", 0)
        self.coverage = kw.get("coverage", 0.0)
        self.is_blank = kw.get("is_blank", True)
        self.advanced = kw.get("advanced", False)
        self.current_content = kw.get("current_content")
        self.memory = kw.get("memory")
        self.hardware = kw.get("hardware")            # FeasibilityReport dict or None
        self.hardware_text = kw.get("hardware_text")  # human-readable report or None
        self.screenshot = kw.get("screenshot")        # saved path or None
        self.errors = kw.get("errors") or []
        self.warnings = kw.get("warnings") or []

    @property
    def ok(self):
        """A quick "did it render anything without errors" boolean."""
        return not self.errors and not self.is_blank

    def as_dict(self):
        return {
            "frames": self.frames,
            "estimated_hardware_fps": self.estimated_hardware_fps,
            "bright_pixels": self.bright_pixels,
            "lit_pixels": self.lit_pixels,
            "coverage": self.coverage,
            "is_blank": self.is_blank,
            "advanced": self.advanced,
            "current_content": self.current_content,
            "memory": self.memory,
            "hardware": self.hardware,
            "screenshot": self.screenshot,
            "errors": list(self.errors),
            "warnings": list(self.warnings),
            "ok": self.ok,
        }

    def as_text(self):
        lines = ["=== run_headless: %d frames ===" % self.frames]
        lines.append("  Rendered: %s (bright=%d, lit=%d, coverage=%.1f%%, advanced=%s)"
                     % ("yes" if not self.is_blank else "BLANK",
                        self.bright_pixels, self.lit_pixels,
                        self.coverage * 100.0, self.advanced))
        if self.current_content is not None:
            lines.append("  Content: %s" % (self.current_content,))
        if self.screenshot:
            lines.append("  Screenshot: %s" % self.screenshot)
        if self.errors:
            lines.append("  ERRORS:")
            for e in self.errors:
                lines.append("    - " + e)
        if self.hardware_text:
            lines.append("")
            lines.append(self.hardware_text)
        elif self.warnings:
            lines.append("  Warnings:")
            for w in self.warnings:
                lines.append("    - " + w)
        return "\n".join(lines)

    def __repr__(self):
        return "RunResult(frames=%d, bright=%d, advanced=%s, errors=%d)" % (
            self.frames, self.bright_pixels, self.advanced, len(self.errors))


def run_headless(app, frames=None, seconds=None, screenshot=None,
                 hardware=True, warmup_data=False):
    """Run ``app`` headlessly for a fixed number of frames; return a ``RunResult``.

    Args:
        app: a ``ScrollKitApp`` instance whose ``setup()`` populates content.
        frames: number of display frames to render (default 120).
        seconds: alternative to ``frames``; converted at 20 FPS.
        screenshot: path to save the final frame as a PNG (optional).
        hardware: model real-hardware timing/RAM and include a feasibility
            report (default True).
        warmup_data: call ``update_data()`` once after ``setup()`` (default
            False — kept off so headless runs never block on the network).

    Synchronous wrapper around :func:`run_headless_async`. Call the async form
    directly from inside an existing event loop.
    """
    import asyncio
    return asyncio.run(run_headless_async(
        app, frames=frames, seconds=seconds, screenshot=screenshot,
        hardware=hardware, warmup_data=warmup_data))


async def run_headless_async(app, frames=None, seconds=None, screenshot=None,
                             hardware=True, warmup_data=False):
    """Async core of :func:`run_headless` (use inside a running event loop)."""
    if frames is None and seconds is not None:
        frames = max(1, int(round(seconds * TARGET_FPS)))
    if frames is None:
        frames = DEFAULT_FRAMES

    # Headless pygame + opt the simulator into hardware timing via its env hook,
    # so this works regardless of how the app builds its display. Both are
    # restored afterwards so we don't perturb the caller's environment.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    prev_hw = os.environ.get("SCROLLKIT_HW_SIM")
    if hardware:
        os.environ["SCROLLKIT_HW_SIM"] = "1"

    errors = []
    warnings = []
    first_sig = None
    last_sig = None

    try:
        await app._initialize_display()

        # Headless runs must stay fast, deterministic, and quiet: never crawl in
        # real time and never print ambient nags, even if the app built its
        # display with throttle=True or SCROLLKIT_HW_THROTTLE is set.
        try:
            from scrollkit.simulator.core.performance_manager import get_active
            _pm = get_active()
            if _pm is not None:
                _pm.throttle = False
                _pm.ambient_warnings = False
        except Exception:
            pass

        import time
        app.running = True
        app._run_start = time.monotonic() if hasattr(time, "monotonic") else None

        try:
            await app.setup()
        except Exception as e:  # surface, don't crash the harness
            errors.append("setup() failed: %r" % (e,))

        if warmup_data:
            try:
                await app.update_data()
            except Exception as e:
                warnings.append("update_data() failed: %r" % (e,))

        # Step the display loop deterministically (mirrors _display_process,
        # minus the 20 FPS sleep and periodic memory report).
        for i in range(frames):
            try:
                content = await app.prepare_display_content()
                app._current_content = content
                if content and app.display:
                    await app.display.clear()
                    await content.render(app.display)
                    closed = await app.display.show() is False
                    app._frame_count += 1
                    if closed:
                        warnings.append("display closed at frame %d" % (i + 1))
                        break
                    buf = _metrics.buffer_from_display(app.display)
                    sig = _metrics.signature(buf) if buf is not None else None
                    if first_sig is None:
                        first_sig = sig
                    last_sig = sig
            except Exception as e:
                errors.append("frame %d failed: %r" % (i + 1, e))
                break

        shot = None
        if screenshot and app.display and hasattr(app.display, "screenshot"):
            try:
                shot = app.display.screenshot(screenshot)
                if shot is None:
                    warnings.append("screenshot unavailable (no pygame surface)")
            except Exception as e:
                warnings.append("screenshot failed: %r" % (e,))

        buf = _metrics.buffer_from_display(app.display)
        snap = _metrics.snapshot(buf)
        if not snap["available"]:
            warnings.append("no pixel buffer — pixel metrics unavailable "
                            "(display is not the pygame simulator)")

        hw_dict = None
        hw_text = None
        if hardware:
            try:
                from scrollkit.simulator.core.performance_manager import get_active
                pm = get_active()
                if pm is not None:
                    report = pm.report()
                    hw_dict = report.as_dict()
                    hw_text = report.as_text()
                    for w in report.warnings:
                        if w not in warnings:
                            warnings.append(w)
                else:
                    warnings.append("hardware timing requested but no model is "
                                    "active (display is not the simulator?)")
            except Exception as e:
                warnings.append("feasibility report unavailable: %r" % (e,))

        advanced = (first_sig is not None and last_sig is not None
                    and first_sig != last_sig)

        try:
            content_desc = app.describe().get("current_content")
        except Exception:
            content_desc = None
        try:
            memory = app.memory_estimate()
        except Exception:
            memory = None

        return RunResult(
            frames=app._frame_count,
            estimated_hardware_fps=(hw_dict or {}).get("estimated_hardware_fps"),
            bright_pixels=snap["bright_pixels"],
            lit_pixels=snap["lit_pixels"],
            coverage=snap["coverage"],
            is_blank=snap["is_blank"],
            advanced=advanced,
            current_content=content_desc,
            memory=memory,
            hardware=hw_dict,
            hardware_text=hw_text,
            screenshot=shot,
            errors=errors,
            warnings=warnings,
        )
    finally:
        app.running = False
        try:
            await app.cleanup()
        except Exception:
            pass
        # Don't leak the module-global active perf manager across runs/tests.
        try:
            from scrollkit.simulator.core.performance_manager import set_active
            set_active(None)
        except Exception:
            pass
        if prev_hw is None:
            os.environ.pop("SCROLLKIT_HW_SIM", None)
        else:
            os.environ["SCROLLKIT_HW_SIM"] = prev_hw
