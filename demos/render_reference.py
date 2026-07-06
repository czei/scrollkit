#!/usr/bin/env python3
"""Render per-API visual reference samples for the docs (the isolated-effect gallery).

Where ``render_gifs.py`` records one GIF per *whole demo*, this records one small
sample per *individual visual API call* — every transition, characterful scroller,
palette-animated bitmap effect, splash, particle, image animator, gradient-text
direction and colour ramp — each on a canvas **tailored to that effect** and
deliberately different from the themed demos.  The output feeds the guide pages and the
Visual Reference gallery (``docs/guide/visual-reference.md``).

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
# Small indexed BMPs that the image-animator samples decorate (one representative
# subject per animator). Committed alongside this generator so it's self-contained.
ANIMATOR_ART_DIR = os.path.join(_HERE, "assets", "animators")

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

# Image animators — class name -> (bmp filename, kind, kwargs, frames, caption). Each
# decorates a static image already on screen; the kwargs are the owner-art-directed
# ThemeParkWaits intro specs the engine was extracted from, one recognisable subject per
# primitive ("combo" kwargs is a tuple of (kind, kwargs) parts). ``frames`` captures one
# full play (~20 fps); loopers get a seamless-ish window, one-shots run to their finish.
IMAGE_ANIMATORS = {
    "TwinkleAnimator":      ("tree.bmp", "twinkle",
                             dict(colors=(0x224422, 0x88AA44, 0xFFEE88), count=10,
                                  box=(14, 1, 50, 19)), 96,
                             "fireflies twinkle over the leaves"),
    "MotionAnimator":       ("airplane.bmp", "motion",
                             dict(path="traverse_lr", bob_amp=1), 104,
                             "the whole tile flies across and off"),
    "EmitterAnimator":      ("tea_cup.bmp", "emitter",
                             dict(box=(24, 8, 42, 11), vx=0, vy=-0.4, rate=4, life=18,
                                  colors=(0xFFFFEE, 0xCCCCCC, 0x777777), max_live=6,
                                  jitter=0.2), 96, "steam drifts up from the cup"),
    "PalettePulseAnimator": ("light_bulb.bmp", "palette_pulse",
                             dict(match=(0xFFEE55, 0xFFDD44, 0xFFFF66, 0xEECC44,
                                         0xCCAA33), tol=24, lo=0.6, hi=1.35, period=44),
                             96, "the filament breathes brighter and dimmer"),
    "RegionShiftAnimator":  ("jellyfish.bmp", "region_shift",
                             dict(box=(21, 16, 43, 29), axis="x", amp=1, period=24,
                                  phase=0, wave="ripple", wavelength=7), 96,
                             "the tentacles ripple (a per-column wave)"),
    "RegionRotateAnimator": ("goat.bmp", "region_rotate",
                             dict(box=(3, 8, 27, 20), pivot=(22, 14), amp_deg=13,
                                  period=44, exclude=(23, 14, 43, 22)), 96,
                             "the goat tilts its head (a true rotation about the neck)"),
    "OrbiterAnimator":      ("honey_pot.bmp", "orbiter",
                             dict(cx=32, cy=19, rx=15, ry=10, period=50, wobble=1,
                                  clockwise=True,
                                  sprite=((0, 0, 0xFFCC00), (1, 0, 0x442200),
                                          (2, 0, 0xFFCC00))), 100,
                             "a bee loops around the honey pot"),
    "BlinkAnimator":        ("panda.bmp", "blink",
                             dict(box=(23, 12, 29, 18), color=0x555555, period=48,
                                  duty=9, delay=28), 100, "the eyes blink shut and open"),
    "SpriteLiftAnimator":   ("canoe.bmp", "lift",
                             dict(boxes=((8, 10, 57, 25),),
                                  exclude_colors=(0x1166BB, 0x3388DD, 0x4499EE,
                                                  0x55AAEE, 0x88DDFF), tol=28,
                                  path="lr", bob_amp=1, slope=0, loop=True), 104,
                             "the canoe crosses; the water stays put"),
    "CoverAnimator":        ("dragon.bmp", "cover",
                             dict(box=(22, 18, 31, 19), dx=0, dy=-3, until=35,
                                  blank=True), 80,
                             "the mouth reads shut until it snaps open"),
    "VanishAnimator":       ("donut.bmp", "vanish",
                             dict(boxes=((40, 5, 46, 9), (38, 10, 46, 14),
                                         (40, 15, 46, 17)), start=35, interval=16), 96,
                             "a bite is taken out, and stays bitten"),
    "FrameCycleAnimator":   ("flag.bmp", "frames",
                             dict(box=(8, 2, 57, 23), nframes=6, amp=2, wavelength=14,
                                  period=3), 96, "the whole flag waves (pre-baked frames)"),
    "ComboAnimator":        ("rocket.bmp", "combo",
                             (("motion", dict(path="rise", delay=40)),
                              ("emitter", dict(box=(29, 27, 37, 29), vx=0, vy=0.5,
                                               rate=2, life=10,
                                               colors=(0xFFEE44, 0xFFAA22, 0xEE4411,
                                                       0x662211), max_live=8,
                                               jitter=0.3))), 84,
                             "rise + exhaust emitter, composed"),
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
        from scrollkit.effects.reveal_splash import pixels_from_text, show_reveal_splash
        from scrollkit.effects.drip_splash import show_drip_splash
        from scrollkit.effects.swarm_reveal import show_swarm_splash
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
# Route: image animators (per-frame motion layered onto a static image). Loads
# the subject BMP as a layer, then drives the animator's start/step/detach contract
# exactly as the host does — mirroring the app's intro pipeline (OnDiskBitmap for the
# palette + read_indexed_bmp for a subscriptable/writable Bitmap -> add_layer). The
# image lives in _layer_group, which clear() does not touch, so each frame is just
# step() + show(); no per-frame content re-render.
# ---------------------------------------------------------------------------

def _build_animator(kind, kwargs):
    """Construct one animator (recursing for a "combo" of parts) from the config."""
    from scrollkit.effects import image_animators as ia
    classes = {
        "twinkle": ia.TwinkleAnimator, "motion": ia.MotionAnimator,
        "emitter": ia.EmitterAnimator, "palette_pulse": ia.PalettePulseAnimator,
        "region_shift": ia.RegionShiftAnimator,
        "region_rotate": ia.RegionRotateAnimator, "orbiter": ia.OrbiterAnimator,
        "blink": ia.BlinkAnimator, "lift": ia.SpriteLiftAnimator,
        "cover": ia.CoverAnimator, "vanish": ia.VanishAnimator,
        "frames": ia.FrameCycleAnimator,
    }
    if kind == "combo":
        return ia.ComboAnimator([_build_animator(k, kw) for k, kw in kwargs])
    return classes[kind](**kwargs)


def _load_intro_image(disp, bmp_name):
    """Load ``bmp_name``; return (odb, bmp, palette, base_colors).

    Device-correct loader (same as demos/medium/image_intro.py): OnDiskBitmap supplies
    the palette, but it is NOT subscriptable on CircuitPython and most animators
    read/rewrite image pixels, so read_indexed_bmp decodes the BMP into a real writable
    Bitmap. Sky sits at palette slot 0; the un-faded colours are captured as RGB888 so a
    palette-writing animator scales correctly on both platforms (the simulator stores
    RGB565 and exposes the true colour via ``get_rgb888``).
    """
    from scrollkit.display.unified import displayio
    from scrollkit.effects.image_animators import read_indexed_bmp
    path = os.path.join(ANIMATOR_ART_DIR, bmp_name)
    odb = displayio.OnDiskBitmap(path)
    pal = odb.pixel_shader
    pal.make_transparent(0)
    get888 = getattr(pal, "get_rgb888", None)
    if get888 is not None:
        base_colors = [(int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2])
                       for c in (get888(i) for i in range(len(pal)))]
    else:
        base_colors = [pal[i] for i in range(len(pal))]
    bmp = read_indexed_bmp(disp.gfx, path)     # subscriptable + writable, both platforms
    return odb, bmp, pal, base_colors


async def _image_animator_sequence(disp, cls_name, *, live=False):
    """Drive one image animator over its subject image (renders + shows each frame)."""
    from scrollkit.display.unified import displayio
    bmp_name, kind, kwargs, frames, _cap = IMAGE_ANIMATORS[cls_name]
    _odb, bmp, pal, base_colors = _load_intro_image(disp, bmp_name)
    animator = _build_animator(kind, kwargs)
    tile = displayio.TileGrid(bmp, pixel_shader=pal)
    disp.add_layer(tile)
    try:
        animator.start(disp, tile, bmp, pal, base_colors)
        for f in range(frames):
            animator.step(f)
            if await disp.show() is False:
                break
    finally:
        try:
            animator.detach()
        except Exception:
            pass
        try:
            disp.remove_layer(tile)
        except Exception:
            pass


async def _gen_image_animator(cls_name, out):
    disp = await _make_display()
    disp.start_recording()
    await _image_animator_sequence(disp, cls_name)
    disp.save_gif(out, target_width=REF_WIDTH, max_colors=REF_COLORS,
                  frame_step=REF_STEP)
    return _saved(out)


async def _preview_image_animator(cls_name):
    disp = await _make_display(title="ScrollKit reference — %s" % cls_name)
    while True:
        await _image_animator_sequence(disp, cls_name, live=True)


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
    from scrollkit.utils.color_utils import NAMED_COLORS
    # Distinct entries, in declaration order, skipping the 'grey' duplicate of 'gray'.
    items = [(k, v) for k, v in NAMED_COLORS.items() if k != "grey"]
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

    # Image animators (enumerated from the live ANIMATOR_CLASSES catalog)
    from scrollkit.effects.image_animators import ANIMATOR_CLASSES
    for cls in ANIMATOR_CLASSES:
        cls_name = cls.__name__
        slug = _slug(cls_name)
        out = _out("animators", slug)
        add("animators", slug,
            (lambda n=cls_name, o=out: asyncio.run(_gen_image_animator(n, o))),
            (lambda n=cls_name: asyncio.run(_preview_image_animator(n))))

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
