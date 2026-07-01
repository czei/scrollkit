#!/usr/bin/env python3
"""Render per-API visual reference samples for the docs (the isolated-effect gallery).

Where ``render_gifs.py`` records one GIF per *whole demo*, this records one small
sample per *individual visual API call* — every transition, characterful scroller,
palette-animated bitmap effect, splash, particle, gradient-text direction and colour
ramp — each on a canvas **tailored to that effect** and deliberately different from
the themed demos.  The output feeds the guide pages and the Visual Reference gallery
(``docs/guide/visual-reference.md``).

It reuses the SAME recorder as everything else (``SimulatorDisplay.start_recording``
/ ``save_gif`` / ``screenshot`` and ``scrollkit.dev.record_gif``) — no new capture
engine — and enumerates the effect sets from the **live selectors**
(``supported_names`` / ``scrollers_for`` / ``palette_effects_for`` /
``gradient_directions``), so a newly added effect shows up here automatically (a unit
test, ``test_reference_coverage.py``, fails if a name has no sample config).

Run (regenerate everything into docs/assets/reference/):

    make docs-reference
    # or:  PYTHONSAFEPATH=1 PYTHONPATH=src python demos/render_reference.py

Render only some (by slug):     python demos/render_reference.py iris-snap wave-rider
Preview ONE live on-screen:     python demos/render_reference.py --preview iris-snap

``--preview`` opens the real pygame window (no GIF written) so an effect can be
eyeballed in the live simulator — the sanctioned way to check it actually looks
right, rather than judging a generated GIF.

This is a docs/tooling script, not a demo — it drives library APIs directly.
"""

import argparse
import asyncio
import os
import sys

# Put src/ on the path (mirrors what render_gifs / the demos do at import time). The
# offscreen SDL driver is set in main() only for GENERATION — --preview needs a real
# window, so it must NOT be forced to the dummy driver.
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if os.path.join(_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "src"))

from scrollkit.app.base import ScrollKitApp                       # noqa: E402
from scrollkit.dev import record_gif                             # noqa: E402
from scrollkit.display.simulator import SimulatorDisplay         # noqa: E402

OUT_DIR = os.path.join(_ROOT, "docs", "assets", "reference")

# Render the panel at a higher LED pitch so the downscaled sample is crisp (the same
# lever render_gifs / the hero shot use). Visual scale only — the logical 64x32 grid
# is unchanged. Reference samples are smaller/shorter than the 480px demo GIFs since
# many render inline together on one page.
RENDER_PITCH = 4.0
REF_WIDTH = 300       # target GIF/PNG width (px)
REF_COLORS = 48       # shared adaptive-palette size
REF_STEP = 2          # keep every Nth frame (smaller file)

# Text baselines used across the samples (tuned for the terminalio 5x8-ish font on a
# 32-tall panel). Bitmap text uses the glyph-top convention instead.
_LABEL_Y = 20
_BITMAP_Y = 12


# ---------------------------------------------------------------------------
# Tailored per-effect configuration (keyed by the LIVE name/class so the drift
# guard can prove every enumerated effect has a sample). Each effect gets its own
# short text + colours chosen to show it off.
# ---------------------------------------------------------------------------

def _slug(name):
    """Lowercase hyphenated slug for a filename (handles names and CamelCase)."""
    out = []
    prev_lower = False
    for ch in name:
        if ch in " _-":
            out.append("-")
            prev_lower = False
            continue
        if ch.isupper() and prev_lower:
            out.append("-")
        out.append(ch.lower())
        prev_lower = ch.islower() or ch.isdigit()
    s = "".join(out)
    while "--" in s:
        s = s.replace("--", "-")
    return s.strip("-")


# Transitions — user-facing name -> (word A, word B, colour). The sequence shows
# A, the transition A->B, B, then B->A, so a GIF loops seamlessly.
TRANSITIONS = {
    "Drop from Sky":     ("RAIN", "DROP", 0x66CCFF),
    "Pixel Dissolve":    ("PIXEL", "DUST", 0xFF66CC),
    "Column Rain":       ("STORM", "RAIN", 0x66CCFF),
    "Gradual Reveal":    ("REVEAL", "BANDS", 0x88FF88),
    "Scan Fold":         ("SCAN", "FOLD", 0xFFCC33),
    "Horizontal Wipe":   ("WIPE", "SWEEP", 0x66FFCC),
    "Glitch Bars":       ("GLITCH", "SIGNAL", 0xFF3366),
    "Diagonal Wipe":     ("ANGLE", "SLASH", 0xFFAA33),
    "Iris Snap":         ("ALPHA", "OMEGA", 0xFFD24A),
    "Venetian Shutters": ("BLINDS", "OPEN", 0x99CCFF),
    "Mosaic Resolve":    ("MOSAIC", "TILES", 0xCC99FF),
    "CRT Collapse":      ("POWER", "OFF", 0x66FF99),
    "Light Slit":        ("LIGHT", "SLIT", 0xFFFFFF),
}

# Characterful scrollers — class name -> (kwargs, seconds).
SCROLLERS = {
    "KineticMarquee": (dict(text="SPACE MOUNTAIN  45 MIN.", y=13, color=0x33CCFF,
                            speed=42), 6.0),
    "WaveRider":      (dict(text="RIDE THE WAVE", y=16, color=0x66FF99, speed=34,
                            amplitude=5, wavelength=18), 5.0),
    "SplitFlap":      (dict(text="DEPARTURES", y=13, color=0xFFCC33, flip_steps=3),
                       5.0),
}

# Bitmap palette effects — class name -> (text, effect kwargs, seconds). Slow scroll
# keeps the letters on screen so the palette animation, not the motion, is the star.
PALETTE = {
    "RainbowChase":  ("RAINBOW", dict(), 4.5),
    "MonoChase":     ("PULSE", dict(color=0x33CCFF), 4.5),
    "NeonTubeCrawl": ("NEON", dict(color=0x66FFCC), 4.5),
    "ChromeSheen":   ("CHROME", dict(highlight=0xFFFFFF, color=0x3366AA), 4.5),
    "HazardStripes": ("CAUTION", dict(color=0xFFCC00), 4.5),
}
_PALETTE_SCROLL = 12   # px/sec — slow drift

# Splash reveals — slug -> (text, builder(display) -> coroutine, max_frames).
SPLASHES = {
    "reveal": ("REVEAL", 150),
    "drip":   ("DRIP", 200),
    "swarm":  ("SWARM", 260),
}

# Particle systems — slug -> (max_particles, frames).
PARTICLES = {
    "sparkle": (26, 110),
    "snow":    (30, 130),
    "ember":   (16, 120),
}

# Colour-ramp swatch strips — slug -> callable returning a colour list.
COLOR_RAMPS = {
    "spectrum":       lambda: _colors().spectrum(16),
    "gradient":       lambda: _colors().gradient(0x102840, 0x00CCFF, 16),
    "multi-gradient": lambda: _colors().multi_gradient(
        (0x330000, 0xCC1100, 0xFF4400, 0xFF8800, 0xFFCC22, 0xFFF0A0), 16),
    "depth-palette":  lambda: _colors().depth_palette(0x66CCFF, 0.55, 12),
}


def _colors():
    from scrollkit.display import colors
    return colors


# ---------------------------------------------------------------------------
# Shared display helpers
# ---------------------------------------------------------------------------

async def _make_display(title=None):
    """Build + initialise a recording-pitch SimulatorDisplay (window if titled)."""
    disp = SimulatorDisplay(width=64, height=32, pitch=RENDER_PITCH)
    await disp.initialize()
    if title and hasattr(disp, "create_window"):
        await disp.create_window(title)
    return disp


def _center_x(disp, text):
    return max(0, (disp.width - disp.measure_text(text)) // 2)


def _rgb_int(rgb):
    r, g, b = rgb
    return (r << 16) | (g << 8) | b


def _out(category, slug, ext="gif"):
    d = os.path.join(OUT_DIR, category)
    os.makedirs(d, exist_ok=True)
    return os.path.join(d, "%s.%s" % (slug, ext))


def _saved(path):
    size = os.path.getsize(path) if path and os.path.exists(path) else 0
    return path, size


def _screenshot(disp, out):
    """Save the current frame, downscaled to REF_WIDTH so stills match the GIFs.

    ``screenshot()`` writes the full native panel surface (crisp but large); the
    reference stills want the same on-page width as the animated samples.
    """
    saved = disp.screenshot(out)
    if not saved:
        return out
    try:
        from PIL import Image
        img = Image.open(saved).convert("RGB")
        if img.width != REF_WIDTH:
            h = max(1, round(img.height * REF_WIDTH / img.width))
            img.resize((REF_WIDTH, h), Image.LANCZOS).save(saved)
    except Exception:
        pass                                     # keep the full-res PNG if PIL is absent
    return saved


# ---------------------------------------------------------------------------
# Route: transitions (direct drive — the headless harness does NOT fire
# transitions, only the real _display_process does, so we mirror its
# cover -> swap-while-hidden -> reveal handling here).
# ---------------------------------------------------------------------------

async def _run_transition(disp, name, a, b, *, live=False):
    """Drive one transition A->B against ``disp`` (renders + shows each frame)."""
    from scrollkit.effects.transitions import transition_factory, Transition
    t = transition_factory(name)
    is_mask = isinstance(t, Transition)          # DropFromSky is a duck-typed sibling
    current = {"c": a if is_mask else b}         # DropFromSky slides the NEW content in

    def swap():
        current["c"] = b

    await t.start(disp, swap)
    guard = 0
    while not t.is_complete and guard < 500:
        guard += 1
        await disp.clear()
        c = current["c"]
        if hasattr(t, "pre_render_hook"):
            t.pre_render_hook(c)
        await c.render(disp)
        await t.render(disp, content=c)
        if await disp.show() is False:
            break
    if hasattr(t, "detach"):
        t.detach()


async def _hold(disp, item, frames, *, live=False):
    for _ in range(frames):
        await disp.clear()
        await item.render(disp)
        if await disp.show() is False:
            return False
    return True


async def _transition_sequence(disp, name, spec, *, live=False):
    from scrollkit.display.content import StaticText
    a_txt, b_txt, color = spec
    a = StaticText(a_txt, x=_center_x(disp, a_txt), y=_LABEL_Y, color=color)
    b = StaticText(b_txt, x=_center_x(disp, b_txt), y=_LABEL_Y, color=color)
    await a.start()
    await b.start()
    if not await _hold(disp, a, 8, live=live):
        return
    await _run_transition(disp, name, a, b, live=live)
    if not await _hold(disp, b, 8, live=live):
        return
    await _run_transition(disp, name, b, a, live=live)


async def _gen_transition(name, spec, out):
    disp = await _make_display()
    disp.start_recording()
    await _transition_sequence(disp, name, spec)
    disp.save_gif(out, target_width=REF_WIDTH, max_colors=REF_COLORS,
                  frame_step=REF_STEP)
    return _saved(out)


async def _preview_transition(name, spec):
    disp = await _make_display(title="ScrollKit reference — %s" % name)
    for _ in range(6):
        await _transition_sequence(disp, name, spec, live=True)


# ---------------------------------------------------------------------------
# Route: content apps (scrollers / palette effects / ScrollingText modes) —
# a one-item queue driven by record_gif (frame-based, so the headless harness
# animates them fine). For --preview we run the real loop for a live window.
# ---------------------------------------------------------------------------

class _RefApp(ScrollKitApp):
    """Minimal app that queues content built by ``builder`` (a 0-arg callable)."""

    def __init__(self, builder, title=None):
        super().__init__(enable_web=False, update_interval=3600)
        self._builder = builder
        self._title = title

    async def create_display(self):
        return SimulatorDisplay(width=64, height=32, pitch=RENDER_PITCH)

    async def setup(self):
        if self._title and hasattr(self.display, "create_window"):
            await self.display.create_window(self._title)
        for item in self._builder():
            self.content_queue.add(item)


def _gen_content_app(builder, out, seconds):
    app = _RefApp(builder)
    saved = record_gif(app, out, seconds=seconds, frame_step=REF_STEP,
                       target_width=REF_WIDTH, max_colors=REF_COLORS)
    return _saved(out if saved else "")


def _preview_content_app(builder, title):
    app = _RefApp(builder, title=title)
    asyncio.run(app.run())


def _scroller_builder(cls_name):
    kwargs, _ = SCROLLERS[cls_name]

    def build():
        from scrollkit.effects import scrolling
        return [getattr(scrolling, cls_name)(**kwargs)]
    return build


def _palette_builder(cls_name):
    text, eff_kwargs, _ = PALETTE[cls_name]

    def build():
        from scrollkit.display import bitmap_text
        eff = getattr(bitmap_text, cls_name)(**eff_kwargs)
        return [bitmap_text.BitmapText(text, y=_BITMAP_Y, palette_effect=eff,
                                       scroll_speed=_PALETTE_SCROLL)]
    return build


def _scrollingtext_builder(mode):
    def build():
        from scrollkit.display.content import ScrollingText
        if mode == "scroll":
            return [ScrollingText("SCROLLING TEXT", y=13, color=0x33CCFF, speed=40)]
        return [ScrollingText("STATIC TEXT", y=13, color=0xFFCC66, speed=0,
                              static_duration=6.0)]
    return build


# ---------------------------------------------------------------------------
# Route: splashes (self-driving — setup runs the blocking show_*_splash coro;
# capture caps the frame count like render_gifs._capture_self_driving does).
# ---------------------------------------------------------------------------

class _SelfDrivingApp(ScrollKitApp):
    def __init__(self, body, title=None):
        super().__init__(enable_web=False, update_interval=3600)
        self._body = body
        self._title = title

    async def create_display(self):
        return SimulatorDisplay(width=64, height=32, pitch=RENDER_PITCH)

    async def setup(self):
        if self._title and hasattr(self.display, "create_window"):
            await self.display.create_window(self._title)
        await self._body(self.display)


def _splash_body(slug):
    text, _ = SPLASHES[slug]

    async def body(display):
        from scrollkit.effects import (
            pixels_from_text, show_reveal_splash, show_drip_splash,
            show_swarm_splash,
        )
        px = pixels_from_text(text, x=_center_x_pixels(text), y=12)
        if slug == "reveal":
            await show_reveal_splash(display, px, color=0xFFEE33,
                                     off_per_frame=16, hold_seconds=1.2)
        elif slug == "drip":
            await show_drip_splash(display, px, color=0x00CCFF, fall_speed=1,
                                   stagger=2, hold_seconds=1.2)
        else:
            await show_swarm_splash(display, px, text_color=0xFFCC00,
                                    bird_color=0xFFE08A, num_birds=22,
                                    bird_speed=2.6, hold_seconds=1.2)
    return body


def _center_x_pixels(text):
    """Centre 5x7-font pixel text (6 px advance/char) on the 64-wide panel."""
    return max(0, (64 - len(text) * 6) // 2)


async def _capture_self_driving(app, max_frames):
    """Record an app whose setup() runs the animation to completion (bounded)."""
    await app._initialize_display()
    app.display.start_recording()
    app.running = True
    task = asyncio.create_task(app.setup())
    try:
        while not task.done() and len(app.display._recording or []) < max_frames:
            await asyncio.sleep(0.01)
    finally:
        app.running = False
        if not task.done():
            task.cancel()
            try:
                await task
            except BaseException:                # noqa: BLE001 — cancellation/teardown
                pass
        try:
            await app.cleanup()
        except Exception:
            pass


def _gen_splash(slug, out):
    _, max_frames = SPLASHES[slug]
    app = _SelfDrivingApp(_splash_body(slug))
    asyncio.run(_capture_self_driving(app, max_frames))
    saved = app.display.save_gif(out, target_width=REF_WIDTH, max_colors=REF_COLORS,
                                 frame_step=REF_STEP)
    return _saved(out if saved else "")


def _preview_splash(slug):
    app = _SelfDrivingApp(_splash_body(slug),
                          title="ScrollKit reference — %s splash" % slug)
    asyncio.run(app.run())


# ---------------------------------------------------------------------------
# Route: particles (direct drive with a small real sleep so the time-based
# physics actually advance between captured frames).
# ---------------------------------------------------------------------------

async def _particle_sequence(disp, slug, frames, *, live=False):
    import random
    from scrollkit.effects.particles import ParticleEngine, Sparkle, Snow, Ember
    from scrollkit.display.colors import spectrum
    random.seed(7)
    hues = spectrum(24)
    max_p, _ = PARTICLES[slug]
    eng = ParticleEngine(max_particles=max_p)
    for f in range(frames):
        await disp.clear()
        if slug == "sparkle":
            if f % 2 == 0:
                eng.add_particle(Sparkle(random.randint(2, 61), random.randint(2, 29),
                                         color=hues[f % len(hues)], lifetime=1.0))
        elif slug == "snow":
            if f % 2 == 0:
                eng.add_particle(Snow(random.randint(0, 63), 0, speed=7.0,
                                      sway=1.4, lifetime=6.0))
        else:  # ember
            if f % 2 == 0:
                eng.add_particle(Ember(random.randint(22, 41), 31, speed=9.0,
                                       drift=3.0, lifetime=2.2))
        await eng.update(disp)
        if await disp.show() is False:
            return
        await asyncio.sleep(0.04)                # let time-based physics advance


async def _gen_particles(slug, out):
    _, frames = PARTICLES[slug]
    disp = await _make_display()
    disp.start_recording()
    await _particle_sequence(disp, slug, frames)
    disp.save_gif(out, target_width=REF_WIDTH, max_colors=REF_COLORS,
                  frame_step=REF_STEP)
    return _saved(out)


async def _preview_particles(slug):
    disp = await _make_display(title="ScrollKit reference — %s" % slug)
    _, frames = PARTICLES[slug]
    while True:
        await _particle_sequence(disp, slug, frames, live=True)


# ---------------------------------------------------------------------------
# Route: static PNGs (gradient-text directions, colour ramps, named colours) —
# render exactly one frame then screenshot.
# ---------------------------------------------------------------------------

async def _gen_gradient(direction, out):
    from scrollkit.display.content import StaticText
    disp = await _make_display()
    palette = (0x0033FF, 0x00FFCC, 0xFFEE33)      # vivid 3-stop so the axis reads
    txt = "GRADIENT"
    item = StaticText(txt, x=_center_x(disp, txt), y=_BITMAP_Y, palette=palette,
                      direction=direction, palette_steps=8)
    await item.start()
    await disp.clear()
    await item.render(disp)
    await disp.show()
    return _saved(_screenshot(disp, out))


async def _gen_color_ramp(slug, out):
    colors = COLOR_RAMPS[slug]()
    disp = await _make_display()
    await disp.clear()
    n = len(colors)
    w, top, band_h = disp.width, 9, 14
    for i, c in enumerate(colors):
        x0 = i * w // n
        x1 = (i + 1) * w // n
        await disp.fill_rect(x0, top, x1 - x0, band_h, c)
    await disp.show()
    return _saved(_screenshot(disp, out))


async def _gen_named_colors(out):
    from scrollkit.app.minimal import MinimalLEDApp
    # Distinct entries, in declaration order, skipping the 'grey' duplicate of 'gray'.
    items = [(k, v) for k, v in MinimalLEDApp.COLORS.items() if k != "grey"]
    disp = await _make_display()
    await disp.clear()
    cols, rows = 4, 4
    cw, ch = disp.width // cols, disp.height // rows
    for idx, (_, rgb) in enumerate(items[:cols * rows]):
        r, c = idx // cols, idx % cols
        await disp.fill_rect(c * cw, r * ch, cw - 1, ch - 1, _rgb_int(rgb))
    await disp.show()
    return _saved(_screenshot(disp, out))


# ---------------------------------------------------------------------------
# Job registry — built from the LIVE selectors so new effects appear here
# automatically. Each job: (category, slug, generate() -> (path, size), preview()).
# ---------------------------------------------------------------------------

def _live_scroller_names():
    from scrollkit.effects.scrolling import scrollers_for
    names = []
    for pres in ("scrolling", "static"):
        for cls in scrollers_for(pres):
            if cls.__name__ not in names:
                names.append(cls.__name__)
    return names


def _live_palette_names():
    from scrollkit.display.bitmap_text import palette_effects_for
    names = []
    for pres in ("static", "scrolling"):
        for cls in palette_effects_for(pres):
            if cls.__name__ not in names:
                names.append(cls.__name__)
    return names


def build_jobs():
    """Return an ordered list of Job dicts for every reference sample."""
    from scrollkit.effects.transitions import supported_names
    from scrollkit.display.text_fill import gradient_directions

    jobs = []

    def add(category, slug, gen, prev):
        jobs.append({"category": category, "slug": slug, "gen": gen, "prev": prev})

    # Transitions
    for name in supported_names():
        spec = TRANSITIONS[name]
        slug = _slug(name)
        out = _out("transitions", slug)
        add("transitions", slug,
            (lambda n=name, s=spec, o=out: asyncio.run(_gen_transition(n, s, o))),
            (lambda n=name, s=spec: asyncio.run(_preview_transition(n, s))))

    # Characterful scrollers
    for cls_name in _live_scroller_names():
        _, seconds = SCROLLERS[cls_name]
        slug = _slug(cls_name)
        out = _out("scrollers", slug)
        add("scrollers", slug,
            (lambda b=_scroller_builder(cls_name), o=out, s=seconds:
                _gen_content_app(b, o, s)),
            (lambda b=_scroller_builder(cls_name), t=cls_name:
                _preview_content_app(b, "ScrollKit reference — %s" % t)))

    # Bitmap palette effects
    for cls_name in _live_palette_names():
        _, _, seconds = PALETTE[cls_name]
        slug = _slug(cls_name)
        out = _out("palette", slug)
        add("palette", slug,
            (lambda b=_palette_builder(cls_name), o=out, s=seconds:
                _gen_content_app(b, o, s)),
            (lambda b=_palette_builder(cls_name), t=cls_name:
                _preview_content_app(b, "ScrollKit reference — %s" % t)))

    # ScrollingText modes
    for mode in ("scroll", "static"):
        slug = "scrollingtext-%s" % mode
        out = _out("content", slug)
        add("content", slug,
            (lambda b=_scrollingtext_builder(mode), o=out: _gen_content_app(b, o, 4.0)),
            (lambda b=_scrollingtext_builder(mode), m=mode:
                _preview_content_app(b, "ScrollKit reference — ScrollingText %s" % m)))

    # Splashes
    for slug in SPLASHES:
        out = _out("splashes", slug)
        add("splashes", slug,
            (lambda sl=slug, o=out: _gen_splash(sl, o)),
            (lambda sl=slug: _preview_splash(sl)))

    # Particles
    for slug in PARTICLES:
        out = _out("particles", slug)
        add("particles", slug,
            (lambda sl=slug, o=out: asyncio.run(_gen_particles(sl, o))),
            (lambda sl=slug: asyncio.run(_preview_particles(sl))))

    # Gradient-text directions (static PNG)
    for direction in gradient_directions():
        out = _out("gradient", direction, ext="png")
        add("gradient", direction,
            (lambda d=direction, o=out: asyncio.run(_gen_gradient(d, o))),
            None)

    # Colour ramps (static PNG)
    for slug in COLOR_RAMPS:
        out = _out("colors", slug, ext="png")
        add("colors", slug,
            (lambda sl=slug, o=out: asyncio.run(_gen_color_ramp(sl, o))),
            None)

    # Named colours grid (static PNG)
    add("colors", "named-colors",
        (lambda o=_out("colors", "named-colors", ext="png"): asyncio.run(_gen_named_colors(o))),
        None)

    return jobs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("slugs", nargs="*",
                        help="sample slugs to render (default: all)")
    parser.add_argument("--preview", metavar="SLUG",
                        help="open ONE sample live in a window instead of rendering")
    args = parser.parse_args()

    jobs = build_jobs()
    by_slug = {j["slug"]: j for j in jobs}

    if args.preview:
        job = by_slug.get(args.preview)
        if job is None:
            parser.error("unknown slug %r\navailable: %s"
                         % (args.preview, ", ".join(sorted(by_slug))))
        if job["prev"] is None:
            parser.error("%r is a still image (no live preview)" % args.preview)
        print("Previewing %s (close the window to exit)..." % args.preview)
        job["prev"]()
        return 0

    # Generation is offscreen — no window pops up.
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    targets = args.slugs or [j["slug"] for j in jobs]
    unknown = [s for s in targets if s not in by_slug]
    if unknown:
        parser.error("unknown slug(s): %s\navailable: %s"
                     % (", ".join(unknown), ", ".join(sorted(by_slug))))

    print("Rendering %d reference sample(s) -> %s\n" % (len(targets), OUT_DIR))
    total = 0
    failures = []
    for slug in targets:
        job = by_slug[slug]
        try:
            path, size = job["gen"]()
        except Exception as e:                    # keep going; report at the end
            print("  %-22s FAILED: %r" % (slug, e))
            failures.append(slug)
            continue
        if not path or not os.path.exists(path):
            print("  %-22s no output (display can't record?)" % slug)
            failures.append(slug)
            continue
        total += size
        print("  %-22s %6.1f KB  %s/%s"
              % (slug, size / 1024, job["category"], os.path.basename(path)))

    print("\nTotal: %.1f MB across %d sample(s)"
          % (total / 1e6, len(targets) - len(failures)))
    if failures:
        print("Failed: %s" % ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
