# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
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
        self.gif = kw.get("gif")                      # saved animated-GIF path or None
        self.video = kw.get("video")                  # saved MP4 path or None
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
            "gif": self.gif,
            "video": self.video,
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
        if self.gif:
            lines.append("  GIF: %s" % self.gif)
        if self.video:
            lines.append("  Video: %s" % self.video)
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
                 hardware=True, warmup_data=False, strict=False, gif=None,
                 gif_opts=None, video=None, video_opts=None):
    """Run ``app`` headlessly for a fixed number of frames; return a ``RunResult``.

    Args:
        app: a ``ScrollKitApp`` instance whose ``setup()`` populates content.
        frames: number of display frames to render (default 120).
        seconds: alternative to ``frames``; converted at 20 FPS.
        screenshot: path to save the final frame as a PNG (optional).
        gif: path to save the whole run as an animated GIF (optional). Records
            every rendered frame from the simulator's LED panel and encodes it
            via ``display.save_gif``; the saved path lands on ``result.gif``.
            Ignored if the display can't record (e.g. real hardware).
        gif_opts: optional dict of keyword args forwarded to ``display.save_gif``
            (e.g. ``{"target_width": 320, "frame_step": 2, "max_colors": 48}``)
            to tune the encoded GIF's size/quality. Ignored unless ``gif`` is set.
        video: path to save the whole run as an MP4 (optional), via
            ``display.save_video``; the saved path lands on ``result.video``.
            Mutually exclusive with ``gif`` in one run (the recording is consumed
            by the first save). Ignored if the display can't record.
        video_opts: optional dict forwarded to ``display.save_video`` (e.g.
            ``{"crf": 20, "border": 22}``). Ignored unless ``video`` is set.
        hardware: model real-hardware timing/RAM and include a feasibility
            report (default True).
        warmup_data: call ``update_data()`` once after ``setup()`` (default
            False — kept off so headless runs never block on the network).
        strict: enforce the feasibility gate. A sustained over-budget run (or a
            catastrophic single frame, or a RAM breach) raises FeasibilityError,
            which is caught, recorded in ``result.errors`` (tagged ``feasibility:``)
            and stops the run, so ``result.ok`` is False. Implies hardware
            modeling. Off by default.

    Synchronous wrapper around :func:`run_headless_async`. Call the async form
    directly from inside an existing event loop.
    """
    import asyncio
    return asyncio.run(run_headless_async(
        app, frames=frames, seconds=seconds, screenshot=screenshot,
        hardware=hardware, warmup_data=warmup_data, strict=strict, gif=gif,
        gif_opts=gif_opts, video=video, video_opts=video_opts))


def record_gif(app, path, *, seconds=4.0, hardware=False, **gif_opts):
    """Render ``app`` headlessly and save an animated GIF of the run to ``path``.

    A thin convenience over :func:`run_headless` with ``gif=path`` — the natural
    way to make a shareable preview of an app (docs, README, a bug report).
    Extra keyword args (``target_width``, ``max_colors``, ``frame_step``, ``fps``)
    are forwarded to ``display.save_gif`` to tune size/quality. Returns the saved
    GIF path, or None if the display can't record (e.g. real hardware / no pygame).
    """
    return run_headless(app, seconds=seconds, gif=path, hardware=hardware,
                        gif_opts=gif_opts or None).gif


def record_video(app, path, *, seconds=4.0, hardware=False, **video_opts):
    """Render ``app`` headlessly and save an MP4 of the run to ``path``.

    The MP4 sibling of :func:`record_gif` (via ``display.save_video``) — far
    smaller and smoother than a GIF, the right format for a site hero. Extra
    keyword args (``crf``, ``target_width``, ``border``, ``fps``, ``preset``) are
    forwarded to ``display.save_video``. Returns the saved path, or None if the
    display can't record (e.g. real hardware / no ffmpeg).
    """
    return run_headless(app, seconds=seconds, video=path, hardware=hardware,
                        video_opts=video_opts or None).video


async def run_headless_async(app, frames=None, seconds=None, screenshot=None,
                             hardware=True, warmup_data=False, strict=False,
                             gif=None, gif_opts=None, video=None, video_opts=None):
    """Async core of :func:`run_headless` (use inside a running event loop)."""
    if frames is None and seconds is not None:
        frames = max(1, int(round(seconds * TARGET_FPS)))
    if frames is None:
        frames = DEFAULT_FRAMES

    # strict enforcement needs the timing model active, so it implies hardware.
    if strict:
        hardware = True

    # Headless pygame + opt the simulator into hardware timing via its env hook,
    # so this works regardless of how the app builds its display. All are
    # restored afterwards so we don't perturb the caller's environment.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    prev_hw = os.environ.get("SCROLLKIT_HW_SIM")
    prev_strict = os.environ.get("SCROLLKIT_HW_STRICT")
    if hardware:
        os.environ["SCROLLKIT_HW_SIM"] = "1"
    if strict:
        os.environ["SCROLLKIT_HW_STRICT"] = "1"

    errors = []
    warnings = []
    first_sig = None
    last_sig = None

    try:
        await app._initialize_display()

        # If a GIF was requested, start capturing frames from the simulator's
        # LED panel now (no-op on displays that can't record, e.g. hardware).
        if (gif or video) and app.display is not None \
                and hasattr(app.display, "start_recording"):
            app.display.start_recording()

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

        # Step the display loop deterministically through the app's OWN frame
        # implementation (SLDKApp.step_frame — settings application, transition
        # firing/rendering, content render, show), minus the 20 FPS sleep and
        # periodic memory report. Never a copy of the loop: the strict gate
        # must exercise exactly the code path that ships, transitions included.
        app._reset_frame_state()
        for i in range(frames):
            try:
                closed = await app.step_frame() is False
                if closed:
                    warnings.append("display closed at frame %d" % (i + 1))
                    break
                if app._current_content is not None and app.display:
                    buf = _metrics.buffer_from_display(app.display)
                    sig = _metrics.signature(buf) if buf is not None else None
                    if first_sig is None:
                        first_sig = sig
                    last_sig = sig
            except Exception as e:
                # The strict feasibility gate raises FeasibilityError mid-render
                # (deep inside display.show()); surface it with a clear tag so
                # callers can tell a budget bust from an ordinary crash.
                from scrollkit.exceptions import FeasibilityError
                if isinstance(e, FeasibilityError):
                    errors.append("feasibility: frame %d busts the device budget: %s"
                                  % (i + 1, e))
                else:
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

        gif_path = None
        if gif and app.display and hasattr(app.display, "save_gif"):
            try:
                gif_path = app.display.save_gif(gif, **(gif_opts or {}))
                if gif_path is None:
                    warnings.append("gif unavailable (no recorded frames / no pygame)")
            except Exception as e:
                warnings.append("gif save failed: %r" % (e,))

        video_path = None
        if video and app.display and hasattr(app.display, "save_video"):
            try:
                video_path = app.display.save_video(video, **(video_opts or {}))
                if video_path is None:
                    warnings.append("video unavailable (no recorded frames / no ffmpeg)")
            except Exception as e:
                warnings.append("video save failed: %r" % (e,))

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
            gif=gif_path,
            video=video_path,
            errors=errors,
            warnings=warnings,
        )
    finally:
        app.running = False
        # Release any still-open recording (save_gif already clears it on the
        # happy path; this covers an early error before the save).
        try:
            if app.display is not None and hasattr(app.display, "stop_recording"):
                app.display.stop_recording()
        except Exception:
            pass
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
        if prev_strict is None:
            os.environ.pop("SCROLLKIT_HW_STRICT", None)
        else:
            os.environ["SCROLLKIT_HW_STRICT"] = prev_strict
