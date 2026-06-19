"""Pre-flight validation for a ScrollKit app — structured issues with fixes.

``validate(app)`` runs the app headless once and combines *static* checks on its
content (colors, text width, on-panel positions) with *dynamic* findings from the
run (did it render anything, plus the hardware feasibility warnings — stutter,
RAM). It returns a ``ValidationReport`` of ``Issue``s, each carrying a severity, a
stable code, a human message, and a concrete fix — so an AI agent gets actionable
feedback instead of a stack trace, and can decide whether the app is ready.

Design note: this reports the *real* behavior of the imperative content classes.
A color name string, for example, is flagged as an error (it would crash
``draw_text``) rather than being quietly "fixed" — only ``MinimalLEDApp`` maps
names to colors. Honest root-cause feedback over papering over the problem.

Desktop-only (imported via ``scrollkit.dev``).
"""

PANEL_WIDTH = 64
PANEL_HEIGHT = 32
CHAR_WIDTH_PX = 6  # ScrollingText's own width estimate; good enough for a heuristic


class Issue:
    """One validation finding: severity + stable code + message + concrete fix."""

    __slots__ = ("severity", "code", "message", "fix")

    def __init__(self, severity, code, message, fix):
        self.severity = severity   # "error" | "warning" | "info"
        self.code = code
        self.message = message
        self.fix = fix

    def as_dict(self):
        return {"severity": self.severity, "code": self.code,
                "message": self.message, "fix": self.fix}

    def __repr__(self):
        return "Issue(%s, %s)" % (self.severity, self.code)


class ValidationReport:
    """Aggregate of validation issues, plus the underlying RunResult (if any)."""

    def __init__(self, issues, run=None):
        self.issues = issues
        self.run = run  # the RunResult from the headless render, or None

    @property
    def errors(self):
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self):
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def infos(self):
        return [i for i in self.issues if i.severity == "info"]

    @property
    def ok(self):
        """True when there are no errors (warnings are allowed)."""
        return not self.errors

    def as_dict(self):
        return {
            "ok": self.ok,
            "counts": {"error": len(self.errors), "warning": len(self.warnings),
                       "info": len(self.infos)},
            "issues": [i.as_dict() for i in self.issues],
        }

    def as_text(self):
        lines = ["=== validate: %s ===" % ("OK" if self.ok else "ISSUES FOUND")]
        if not self.issues:
            lines.append("  No issues.")
        for i in self.issues:
            lines.append("  [%s] %s: %s" % (i.severity.upper(), i.code, i.message))
            if i.fix:
                lines.append("        fix: %s" % i.fix)
        return "\n".join(lines)

    def __repr__(self):
        return "ValidationReport(ok=%s, errors=%d, warnings=%d)" % (
            self.ok, len(self.errors), len(self.warnings))


# --- checks -------------------------------------------------------------------

def _check_color(color, label):
    if isinstance(color, bool):  # bool is an int subclass — almost certainly a bug
        return [Issue("error", "color_type",
                      "%s: color is a bool (%r)." % (label, color),
                      "Use an int 0xRRGGBB or an (r, g, b) tuple.")]
    if isinstance(color, int):
        if color < 0 or color > 0xFFFFFF:
            return [Issue("warning", "color_out_of_range",
                          "%s: color 0x%X is outside 0x000000..0xFFFFFF."
                          % (label, color),
                          "Use a 24-bit value, e.g. 0xFF8800.")]
        return []
    if isinstance(color, (tuple, list)):
        ok = (len(color) == 3 and all(
            isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255
            for c in color))
        if not ok:
            return [Issue("warning", "color_out_of_range",
                          "%s: RGB %r must be three ints in 0..255." % (label, color),
                          "e.g. (255, 136, 0).")]
        return []
    if isinstance(color, str):
        return [Issue("error", "color_string",
                      "%s: color is the string %r. The imperative content classes "
                      "need an int or (r, g, b) tuple; a name would crash draw_text "
                      "(only MinimalLEDApp understands color names)." % (label, color),
                      "Use 0xRRGGBB or (r, g, b). To go from a name: "
                      "scrollkit.dev.capabilities()['named_colors'][name].")]
    return [Issue("error", "color_type",
                  "%s: color has unsupported type %s." % (label, type(color).__name__),
                  "Use an int 0xRRGGBB or an (r, g, b) tuple.")]


def _static_checks(items, panel_width, panel_height):
    issues = []
    if not items:
        issues.append(Issue(
            "info", "empty_queue",
            "content_queue is empty.",
            "If you render via a prepare_display_content() override this is fine; "
            "otherwise add content in setup(), e.g. "
            "self.content_queue.add(ScrollingText('HELLO'))."))
        return issues

    for idx, item in enumerate(items):
        label = "%s#%d" % (type(item).__name__, idx)

        color = getattr(item, "color", None)
        if color is not None:
            issues.extend(_check_color(color, label))

        text = getattr(item, "text", None)
        scrolling = hasattr(item, "speed")  # ScrollingText has speed; StaticText doesn't
        if isinstance(text, str) and not scrolling:
            width = len(text) * CHAR_WIDTH_PX
            if width > panel_width:
                issues.append(Issue(
                    "warning", "text_clipped",
                    "%s: text ~%dpx wide exceeds the %dpx panel and will be clipped."
                    % (label, width, panel_width),
                    "Use ScrollingText so it scrolls, or shorten the text."))

        y = getattr(item, "y", None)
        if isinstance(y, int) and (y < 0 or y >= panel_height):
            issues.append(Issue(
                "warning", "offscreen_y",
                "%s: y=%d is outside the 0..%d panel." % (label, y, panel_height - 1),
                "Pick a y within the panel (y=12 vertically centers an 8px font)."))

    return issues


def _dynamic_checks(result):
    issues = []
    for e in result.errors:
        issues.append(Issue(
            "error", "runtime_error", e,
            "Fix the exception; scrollkit.dev.run_headless(app) shows full detail."))
    if result.is_blank and not result.errors:
        if result.frames == 0:
            msg = ("Nothing rendered (0 frames shown) — no content reached the "
                   "display.")
        else:
            msg = "Ran %d frames but nothing was lit." % result.frames
        issues.append(Issue(
            "error", "blank_render", msg,
            "Check content was added to the queue (or drawn), colors aren't "
            "black, and positions are on-panel."))
    # Hardware estimates from a crashed or empty run are meaningless, so skip
    # them then. The feasibility warnings already carry their own fix guidance,
    # so no separate fix line is needed.
    if result.hardware and not result.errors and result.frames > 0:
        for w in result.hardware.get("warnings", []):
            issues.append(Issue("warning", "hardware", w, None))
    return issues


def validate(app, panel_width=PANEL_WIDTH, panel_height=PANEL_HEIGHT,
             run=True, frames=60):
    """Validate ``app`` and return a :class:`ValidationReport`.

    Args:
        app: a ``ScrollKitApp`` instance (its ``setup()`` populates content).
        panel_width/panel_height: target panel size (MatrixPortal S3 = 64x32).
        run: render the app headless to add dynamic checks + hardware warnings
            (default True). With ``run=False`` only static checks run.
        frames: frames to render when ``run`` is True.

    The app's ``setup()`` runs as part of this call (via the headless render, or
    directly when ``run=False``), so pass a fresh, un-run app instance.
    """
    issues = []
    result = None

    if run:
        from .harness import run_headless
        result = run_headless(app, frames=frames, hardware=True)
    else:
        import asyncio
        try:
            asyncio.run(app.setup())
        except Exception as e:
            issues.append(Issue(
                "warning", "setup_failed",
                "Could not run setup() for static checks: %r" % (e,),
                "Ensure setup() runs without a live display, or use run=True."))

    try:
        items = list(app.content_queue)
    except Exception:
        items = []
    issues.extend(_static_checks(items, panel_width, panel_height))

    if result is not None:
        issues.extend(_dynamic_checks(result))

    return ValidationReport(issues, result)
