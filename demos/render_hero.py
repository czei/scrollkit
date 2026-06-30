#!/usr/bin/env python3
"""Render the scrollkit.dev landing-page HERO to docs/assets/video/ (MP4 + poster).

Self-contained and reproducible — regenerate any time with::

    make hero
    # or:  PYTHONSAFEPATH=1 PYTHONPATH=src python demos/render_hero.py

It drives the desktop simulator at 2x resolution (crisp on retina) and records via
``SimulatorDisplay.save_video``. The show, all rendered by ScrollKit on a 64x32
panel:

  1. a swarm flies in and assembles the ScrollKit logo (single-colour silhouette)
  2. two sheen passes sweep over it (a diagonal specular glint, then a vertical
     light-bar) — palette-style animation, device-feasible
  3. a colorize cross-fade to an electric-blue -> magenta -> gold finale (bit_depth
     6 for smooth hues — still device-feasible since the logo is static)
  4. a fade to black for a clean loop

Honesty note: the swarm uses a CINEMATIC bird count (web-hero only); a
device-feasible flock (<= ~28 birds) assembles this many cells far more slowly.
Everything after assembly is device-feasible.
"""
import os
import sys
import math
import random
import asyncio

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if os.path.join(_ROOT, "src") not in sys.path:
    sys.path.insert(0, os.path.join(_ROOT, "src"))

from scrollkit.display.simulator import SimulatorDisplay  # noqa: E402
from scrollkit.display.bitmap_text import FONT_5x7  # noqa: E402
from scrollkit.effects.swarm_reveal import SwarmReveal  # noqa: E402

W, H = 64, 32
DMAX = (W - 1) + (H - 1)
GW = 5  # built-in glyph cell width
OUT_DIR = os.path.join(_ROOT, "docs", "assets", "video")

# Palette (locked).
CYAN_TOP = (0, 232, 238)
TEAL_BOT = (0, 150, 165)
BIRD = (150, 235, 240)
EBLUE = (40, 90, 255)
MAGENTA = (255, 0, 200)
GOLD = (255, 185, 40)


# --- the locked logo: SCROLL spread full width, KIT grouped + centred -------
def _cells(ch, bold=False):
    rows = FONT_5x7.get(ch.upper())
    if not rows:
        return []
    out = []
    for ry, row in enumerate(rows):
        for rx, c in enumerate(row):
            if c != " ":
                out.append((rx, ry))
                if bold:
                    out.append((rx + 1, ry))  # faux-bold: thicken rightward
    return out


def _layout_line(word, x_scale, y_scale, top_y, span=None, base_x=None, bold=False):
    n = len(word)
    gw = (GW + (1 if bold else 0)) * x_scale
    if span is not None:
        gap = (span - n * gw) / (n - 1) if n > 1 else 0
    else:
        gap = 1 * x_scale
        span = n * gw + gap * (n - 1)
    if base_x is None:
        base_x = (W - span) / 2.0
    px = []
    x = base_x
    for ch in word:
        for (cx, cy) in _cells(ch, bold):
            for sx in range(x_scale):
                for sy in range(y_scale):
                    px.append((int(round(x)) + cx * x_scale + sx, top_y + cy * y_scale + sy))
        x += gw + gap
    return px


def logo_pixels():
    px = (_layout_line("SCROLL", 1, 2, top_y=1, span=58, base_x=3, bold=True)
          + _layout_line("KIT", 1, 2, top_y=17, span=22, bold=True))
    return [(x, y) for (x, y) in px if 0 <= x < W and 0 <= y < H]


# --- colour helpers ---------------------------------------------------------
def rgb_int(c):
    return (int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2])


def lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def scale(c, f):
    return (c[0] * f, c[1] * f, c[2] * f)


def clampc(c):
    return tuple(max(0, min(255, int(round(v)))) for v in c)


def grad_base(y):
    return lerp(CYAN_TOP, TEAL_BOT, y / (H - 1))


def multihue(x):
    p = x / (W - 1)
    return lerp(EBLUE, MAGENTA, p / 0.5) if p < 0.5 else lerp(MAGENTA, GOLD, (p - 0.5) / 0.5)


def sheen(coord, phase, sigma, lo, hi):
    dist = abs(coord - phase)
    dist = min(dist, 1.0 - dist)
    return lo + hi * math.exp(-(dist / sigma) ** 2)


def ease(t):
    return t * t * (3 - 2 * t)


def _mp4_to_gif(mp4_path, gif_path, *, width=600, fps=15):
    """Convert the rendered MP4 to an optimized, looping GIF for the GitHub README
    (where <video> tags are stripped). Two-pass palette for good quality at a small
    size. Returns the path, or None if ffmpeg is unavailable / the MP4 is missing."""
    import shutil
    import subprocess
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None or not (mp4_path and os.path.exists(mp4_path)):
        return None
    palette = gif_path + ".palette.png"
    vf = "fps=%d,scale=%d:-1:flags=lanczos" % (fps, width)
    try:
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", mp4_path,
                        "-vf", vf + ",palettegen=stats_mode=diff", palette], check=True)
        subprocess.run([ffmpeg, "-y", "-loglevel", "error", "-i", mp4_path,
                        "-i", palette, "-lavfi",
                        vf + " [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=4",
                        gif_path], check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    finally:
        if os.path.exists(palette):
            os.remove(palette)
    return gif_path


def _save_poster(disp, path):
    """Pad a finale screenshot with the same bezel save_video adds, so the poster
    (the autoplay fallback) matches the video frame exactly."""
    tmp = path + ".panel.png"
    if disp.screenshot(tmp) is None:
        return
    try:
        from PIL import Image
        panel = Image.open(tmp).convert("RGB")
        b = 44
        framed = Image.new("RGB", (panel.width + 2 * b, panel.height + 2 * b), (10, 10, 13))
        framed.paste(panel, (b, b))
        framed.save(path)
    except ImportError:
        os.replace(tmp, path)
        return
    os.remove(tmp)


async def render():
    # Seed so the random swarm flight is deterministic -> `make hero` always renders
    # the same animation (the encoded bytes may differ slightly via x264 threading).
    random.seed(0x5C0117)
    os.makedirs(OUT_DIR, exist_ok=True)
    pix = logo_pixels()

    disp = SimulatorDisplay(W, H, pitch=6.0)  # 2x resolution -> crisp on retina
    await disp.initialize()
    disp.start_recording()

    # PHASE 1 — swarm assembles the silhouette (flat cyan).
    swarm = SwarmReveal(pix, text_color=rgb_int(CYAN_TOP), bird_color=rgb_int(BIRD),
                        num_birds=70, bird_speed=3.5, disperse_frames=10)
    swarm.start(disp)
    steps = 0
    while not swarm.is_complete and steps < 150:
        swarm.step()
        await disp.show()
        steps += 1
    await disp.show()
    swarm.detach()

    # PHASE 2a — gradient eases in + a diagonal specular glint sweeps.
    for i in range(26):
        t_ease = min(1.0, i / 7.0)
        phase = (i / 26) % 1.0
        await disp.clear()
        for (x, y) in pix:
            base = lerp(CYAN_TOP, grad_base(y), t_ease)
            f = sheen((x + y) / DMAX, phase, 0.12, 0.55, 0.9)
            await disp.set_pixel(x, y, clampc(scale(base, f)))
        await disp.show()

    # PHASE 2b — a vertical light-bar wipes top->bottom (a different 'kind' of sheen).
    for i in range(20):
        phase = (i / 20) % 1.0
        await disp.clear()
        for (x, y) in pix:
            f = sheen(y / (H - 1), phase, 0.16, 0.55, 0.95)
            await disp.set_pixel(x, y, clampc(scale(grad_base(y), f)))
        await disp.show()

    # PHASE 3 — colorize: cross-fade to electric-blue -> magenta -> gold (bit_depth 6).
    disp.matrix.bit_depth = 6
    for i in range(32):
        t = ease(i / 31)
        phase = (i / 32) % 1.0
        await disp.clear()
        for (x, y) in pix:
            base = lerp(grad_base(y), multihue(x), t)
            f = sheen((x + y) / DMAX, phase, 0.14, 0.62, 0.7)
            await disp.set_pixel(x, y, clampc(scale(base, f)))
        await disp.show()

    # PHASE 4 — hold the multi-colour finale with a slow shimmer (grab the poster here).
    for i in range(20):
        phase = (i / 20) % 1.0
        await disp.clear()
        for (x, y) in pix:
            f = sheen((x + y) / DMAX, phase, 0.20, 0.72, 0.45)
            await disp.set_pixel(x, y, clampc(scale(multihue(x), f)))
        await disp.show()
        if i == 3:
            _save_poster(disp, os.path.join(OUT_DIR, "scrollkit-hero-poster.png"))

    # PHASE 5 — fade to black for a clean loop back to the swarm.
    for i in range(14):
        k = 1.0 - (i + 1) / 14
        await disp.clear()
        for (x, y) in pix:
            await disp.set_pixel(x, y, clampc(scale(multihue(x), k * 0.9)))
        await disp.show()

    out = disp.save_video(os.path.join(OUT_DIR, "scrollkit-hero.mp4"),
                          fps=24, crf=20, border=44)
    size = os.path.getsize(out) / 1e6 if out and os.path.exists(out) else 0
    print("hero mp4 -> %s  (%.1f MB)" % (out, size))

    # README GIF (GitHub can't autoplay an <video>): convert the MP4 once.
    gif = _mp4_to_gif(out, os.path.join(OUT_DIR, "scrollkit-hero.gif"))
    if gif:
        print("hero gif -> %s  (%.1f MB)" % (gif, os.path.getsize(gif) / 1e6))
    return out


if __name__ == "__main__":
    asyncio.run(render())
