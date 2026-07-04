# Copyright (c) 2024-2026 Michael Czeiszperger
"""Image animators — per-frame motion layered onto a static image already on screen.

A host shows a full-panel image (an intro card, a logo, an icon) as a TileGrid and
wants part of it to MOVE while it holds: lights twinkle across a silhouette, a subject
crosses a fixed scene, a feature glows, a flag waves. Each animator here decorates that
EXISTING image layer; none of them own the display loop.

Contract (the standalone-effect start/step/detach convention):

    anim = TwinkleAnimator(count=20)
    if anim.wants_writable_bitmap:                 # some animators rewrite image pixels
        bitmap = copy_to_writable(display.gfx, bitmap, w, h, len(palette))
    anim.start(display, tile, bitmap, palette, base_colors)   # raise = host falls back
    ...                                            # each frame: anim.step(frame)
    anim.detach()                                  # settle + free layers (idempotent)

``base_colors`` is the palette's original colors as RGB888 ints (captured by the host
before any fading/mutation). ``HOLD_FRAMES`` on each class suggests how many frames one
play wants. Any exception out of ``start``/``step`` is the host's cue to fall back to
the still image — animators must stay safe to ``detach()`` after a failure.

Three motion substrates, composable via ``ComboAnimator``:
  * transparent overlay bitmaps ABOVE the image (Twinkle / Emitter / Orbiter / Blink /
    Cover) — sparse per-pixel writes cleared with one C ``fill``;
  * moving the image's own TileGrid (Motion) or a lifted copy of its subject
    (SpriteLift — the scene stays fixed, the hole row-inpaints);
  * rewriting image pixels in place (RegionShift / Vanish / FrameCycle) or palette
    entries (PalettePulse) — these need the host's writable copy.

Not to be confused with: ``effects.overlay.OverlayMask`` (opaque cover for transitions,
C bulk-ops); ``effects.particles.ParticleEngine`` (renders via ``display.set_pixel``,
no overlay layer — EmitterAnimator instead composites through a palette overlay that
can ``follow_tile`` a moving image).
"""
import math
import random


def _shuffle(lst):
    """In-place Fisher-Yates (random.shuffle is absent on CircuitPython)."""
    for i in range(len(lst) - 1, 0, -1):
        j = random.randint(0, i)
        lst[i], lst[j] = lst[j], lst[i]


def copy_to_writable(gfx, src, width, height, ncolors):
    """A writable ``Bitmap`` copy of ``src`` (an OnDiskBitmap's bitmap or a Bitmap).

    Animators that MODIFY the image pixels (vs. only overlaying) need a writable target —
    an ``OnDiskBitmap`` is read-only. Copied once at start (2048 reads for a 64x32), never
    per frame.
    """
    # TODO: bitmaptools.blit fast-path (2048-iteration Python loop on device)
    dst = gfx.Bitmap(width, height, ncolors)
    for y in range(height):
        for x in range(width):
            dst[x, y] = src[x, y]
    return dst


def read_indexed_bmp(gfx, path):
    """Decode an 8-bit indexed BMP straight into a writable ``gfx.Bitmap``.

    CircuitPython's ``OnDiskBitmap`` renders fine but is NOT subscriptable — any
    ``bitmap[x, y]`` read raises TypeError — so animators that scan or rewrite image
    pixels cannot use it directly on-device. For the common case (small indexed BMPs
    authored for the panel) this reads the pixel array off disk into a real Bitmap:
    BITMAPINFOHEADER only, bpp must be 8, rows bottom-up and 4-byte padded. The
    returned Bitmap pairs with the OnDiskBitmap's own ``pixel_shader``.
    """
    with open(path, "rb") as f:
        header = f.read(54)
        if header[0:2] != b"BM":
            raise ValueError("not a BMP")
        offset = (header[10] | (header[11] << 8) | (header[12] << 16)
                  | (header[13] << 24))
        width = header[18] | (header[19] << 8)
        height = header[22] | (header[23] << 8)
        bpp = header[28] | (header[29] << 8)
        if bpp != 8:
            raise ValueError("read_indexed_bmp: %d bpp (need 8)" % bpp)
        ncolors = (header[46] | (header[47] << 8)) or 256
        row_bytes = (width + 3) & ~3
        bmp = gfx.Bitmap(width, height, ncolors)
        f.seek(offset)
        for row in range(height):
            data = f.read(row_bytes)
            y = height - 1 - row                   # BMP rows are bottom-up
            for x in range(width):
                bmp[x, y] = data[x]
    return bmp


def _scale_color(color, f):
    """Scale a 24-bit color by ``f`` (clamped 0..255 per channel; f may exceed 1)."""
    r = int(((color >> 16) & 0xFF) * f)
    g = int(((color >> 8) & 0xFF) * f)
    b = int((color & 0xFF) * f)
    if r > 255:
        r = 255
    if g > 255:
        g = 255
    if b > 255:
        b = 255
    return (r << 16) | (g << 8) | b


class IntroAnimator:
    """Base: animate a static image layer while it holds on screen.

    Lifecycle: ``start()`` once (build overlays / capture pixels), ``step(frame)``
    once per displayed frame, ``detach()`` to settle to a rest pose and free any
    layers. Subclasses set ``HOLD_FRAMES`` (suggested frames for one play) and, if
    they need to REWRITE the base image pixels rather than just overlay a layer on top,
    ``wants_writable_bitmap = True`` so the loader hands them a writable copy.
    """

    HOLD_FRAMES = 96                 # ~5 s at the ~20 fps display loop
    wants_writable_bitmap = False

    def start(self, display, tile, bitmap, palette, base_colors):
        """Store references and build any overlay layers. Raise to abort (falls back)."""
        self.display = display
        self.tile = tile
        self.bitmap = bitmap
        self.palette = palette
        self.base_colors = base_colors

    def step(self, frame):
        """Advance the animation to ``frame`` (0-based). Called once per HOLD frame."""

    def detach(self):
        """Settle to a rest pose and remove/free anything ``start`` created (idempotent)."""

    # -- shared overlay helper (Twinkle / Emitter / Orbiter) ------------------------
    def _make_overlay(self, display, colors):
        """A transparent overlay Bitmap+TileGrid above the image; palette = [sky]+colors."""
        gfx = display.gfx
        bmp = gfx.Bitmap(display.width, display.height, len(colors) + 1)
        pal = gfx.Palette(len(colors) + 1)
        pal[0] = 0x000000
        for i, c in enumerate(colors):
            pal[i + 1] = c
        pal.make_transparent(0)
        tile = gfx.TileGrid(bmp, pixel_shader=pal)
        display.add_layer(tile)
        self._overlay = bmp
        self._overlay_tile = tile
        return bmp

    def _drop_overlay(self):
        tile = getattr(self, "_overlay_tile", None)
        if tile is not None and getattr(self, "display", None) is not None:
            try:
                self.display.remove_layer(tile)
            except Exception:
                pass
        self._overlay_tile = None
        self._overlay = None


class TwinkleAnimator(IntroAnimator):
    """Sparkling lights scattered across a silhouette (city windows, starlight, gems).

    Overlays points sampled from the image's own lit pixels, each flaring on its own sine
    phase so they shimmer independently. Overlay-only — the base image never changes.
    """

    HOLD_FRAMES = 96

    def __init__(self, colors=(0x223355, 0x8899BB, 0xFFFFFF), count=34, box=None):
        self._colors = tuple(colors)
        self._count = count
        self._box = box

    def start(self, display, tile, bitmap, palette, base_colors):
        super().start(display, tile, bitmap, palette, base_colors)
        self._make_overlay(display, self._colors)
        w, h = display.width, display.height
        if self._box:
            x0, y0, x1, y1 = self._box
            x0, y0 = max(0, x0), max(0, y0)
            x1, y1 = min(w, x1 + 1), min(h, y1 + 1)
        else:
            x0, y0, x1, y1 = 0, 0, w, h
        candidates = [(x, y) for y in range(y0, y1) for x in range(x0, x1)
                      if bitmap[x, y] != 0]
        _shuffle(candidates)
        self._points = [(x, y, random.uniform(0.0, 6.28), random.uniform(0.15, 0.35))
                        for x, y in candidates[:min(self._count, len(candidates))]]

    def step(self, frame):
        overlay = self._overlay
        overlay.fill(0)                          # one C fill, never a per-pixel clear loop
        n = len(self._colors)
        for x, y, phase, speed in self._points:
            b = (math.sin(frame * speed + phase) + 1.0) * 0.5
            if b < 0.55:
                continue                         # mostly dark, brief flares -> a twinkle
            shade = n if b > 0.9 else (n - 1 if b > 0.72 and n > 1 else 1)
            overlay[x, y] = shade

    def detach(self):
        self._drop_overlay()
        self._points = None


class MotionAnimator(IntroAnimator):
    """Move the whole image tile: traverse across, blast off, bob, or jiggle.

    ``traverse_lr``/``traverse_rl`` cross the panel starting and ending fully off-screen;
    ``rise`` launches upward off the top after ``delay`` frames (with a tiny pre-launch
    shudder); ``bob``/``jiggle`` oscillate in place and recenter at detach. Traverse/rise
    deliberately do NOT recenter — the subject has left, and the fade shows empty sky.
    """

    def __init__(self, path="bob", amp=2, bob_amp=0, delay=0):
        self._path = path
        self._amp = amp
        self._bob_amp = bob_amp
        self._delay = delay
        if path in ("traverse_lr", "traverse_rl"):
            self.HOLD_FRAMES = 104
        elif path == "rise":
            self.HOLD_FRAMES = 84

    def step(self, frame):
        tile = self.tile
        p = self._path
        if p == "traverse_lr" or p == "traverse_rl":
            span = self.HOLD_FRAMES - 1
            t = frame / span if span else 1.0
            if t > 1.0:
                t = 1.0
            x0, x1 = (-66, 66) if p == "traverse_lr" else (66, -66)
            tile.x = int(round(x0 + (x1 - x0) * t))
            if self._bob_amp:
                tile.y = int(round(self._bob_amp * math.sin(frame * 0.3)))
        elif p == "rise":
            if frame < self._delay:
                tile.x = 1 if (frame // 3) & 1 else 0      # pre-launch shudder
            else:
                tile.x = 0
                t = (frame - self._delay) / float(max(1, self.HOLD_FRAMES - self._delay))
                tile.y = -int(round(40 * t * t))           # ease-in launch, exits the top
        elif p == "bob":
            tile.y = int(round(self._amp * math.sin(frame * 0.25)))
        elif p == "jiggle":
            tile.x = int(round(self._amp * math.sin(frame * 0.9)))
            tile.y = int(round((self._amp * 0.5) * math.sin(frame * 1.3)))

    def detach(self):
        if self._path in ("bob", "jiggle"):      # in-place motions settle back to center
            try:
                self.tile.x = 0
                self.tile.y = 0
            except Exception:
                pass


class EmitterAnimator(IntroAnimator):
    """Short-lived drifting particles from a spawn box (smoke, exhaust, bubbles, fire).

    Particles are single overlay pixels colored by age along ``colors`` (young -> old).
    Capped at ``max_live`` so the per-frame cost stays a few dozen writes + one C fill.
    """

    HOLD_FRAMES = 96

    def __init__(self, box, vx=0.0, vy=-0.5, rate=4, life=16,
                 colors=(0xFFFFFF, 0xBBBBBB, 0x777777), max_live=6, jitter=0.0,
                 delay=0, follow_tile=False):
        self._boxk = box
        self._vx = vx
        self._vy = vy
        self._rate = max(1, rate)
        self._life = life
        self._colors = tuple(colors)
        self._max = min(8, max_live)
        self._jitter = jitter
        self._delay = delay
        # follow_tile: spawn relative to the (moving) image tile, so a traversing
        # locomotive puffs smoke from its own stack and the puffs trail behind it.
        self._follow = follow_tile

    def start(self, display, tile, bitmap, palette, base_colors):
        super().start(display, tile, bitmap, palette, base_colors)
        self._make_overlay(display, self._colors)
        self._parts = []                          # [x, y, vx, vy, age] per particle

    def step(self, frame):
        overlay = self._overlay
        overlay.fill(0)
        if frame < self._delay:
            return
        if frame % self._rate == 0 and len(self._parts) < self._max:
            x0, y0, x1, y1 = self._boxk
            ox = oy = 0
            if self._follow:
                ox, oy = self.tile.x, self.tile.y
            j = self._jitter
            self._parts.append([random.uniform(x0, x1) + ox, random.uniform(y0, y1) + oy,
                                self._vx + (random.uniform(-j, j) if j else 0.0),
                                self._vy + (random.uniform(-j, j) if j else 0.0), 0])
        w, h = overlay.width, overlay.height
        ncol = len(self._colors)
        alive = []
        for part in self._parts:
            part[0] += part[2]
            part[1] += part[3]
            part[4] += 1
            if part[4] >= self._life:
                continue
            xi, yi = int(part[0]), int(part[1])
            if 0 <= xi < w and 0 <= yi < h:
                ci = 1 + min(ncol - 1, (part[4] * ncol) // self._life)
                overlay[xi, yi] = ci
                alive.append(part)
        self._parts = alive

    def detach(self):
        self._drop_overlay()
        self._parts = None


class PalettePulseAnimator(IntroAnimator):
    """Breathe the brightness of the palette entries matching given colors (a glow).

    Nearly free per frame (a handful of palette writes). The registry spec must only
    match colors exclusive to the glowing feature — validated at design time.
    """

    HOLD_FRAMES = 96

    def __init__(self, match, tol=24, lo=0.6, hi=1.25, period=48):
        self._match = tuple(match)
        self._tol = tol
        self._lo = lo
        self._hi = hi
        self._period = max(8, period)

    def start(self, display, tile, bitmap, palette, base_colors):
        super().start(display, tile, bitmap, palette, base_colors)
        t = self._tol
        idx = []
        for i in range(1, len(base_colors)):
            c = base_colors[i]
            r, g, b = (c >> 16) & 0xFF, (c >> 8) & 0xFF, c & 0xFF
            for m in self._match:
                mr, mg, mb = (m >> 16) & 0xFF, (m >> 8) & 0xFF, m & 0xFF
                if abs(r - mr) <= t and abs(g - mg) <= t and abs(b - mb) <= t:
                    idx.append(i)
                    break
        self._idx = idx                           # empty -> harmless no-op

    def step(self, frame):
        f = self._lo + (self._hi - self._lo) * (math.sin(6.2832 * frame / self._period) + 1.0) * 0.5
        pal, base = self.palette, self.base_colors
        for i in self._idx:
            pal[i] = _scale_color(base[i], f)

    def detach(self):
        pal, base = getattr(self, "palette", None), getattr(self, "base_colors", None)
        if pal is None or base is None:
            return
        try:
            for i in self._idx:
                pal[i] = base[i]                  # restore, so the fade starts clean
        except Exception:
            pass


class RegionShiftAnimator(IntroAnimator):
    """Move the lit pixels inside a box (wing flap, tail wag, jaw, door slide, flag wave).

    The captured pixels re-stamp at an offset each frame; only the PREVIOUSLY stamped
    pixels are erased (tracked, not a whole-box clear), and frames where the offset didn't
    change cost nothing. The design-time rule: the box expanded by the travel along
    ``axis`` contains only this feature plus sky.

    Waveforms (``wave``): "sine" oscillates; "ramp" moves once from 0 to ``amp`` over
    ``period`` frames and holds (a door sliding open, a head popping up); "ripple" gives
    each COLUMN its own sine phase (a flag waving — y-axis only, small regions); "hinge"
    rotates the region about one fixed edge (``hinge``="left"/"right"): amplitude grows
    linearly from 0 at the shoulder to ``amp`` at the tip — a WHOLE wing beating.
    ``half`` clamps a sine to one side ("pos"/"neg": a jaw only opens downward).
    ``delay`` holds rest (or, with ``hide_before``, keeps the region ERASED — invisible)
    until that frame: a dragon's flame that appears mid-hold, a jack popping out.
    """

    HOLD_FRAMES = 96
    wants_writable_bitmap = True

    def __init__(self, box, axis="y", amp=2, period=24, phase=0.0,
                 wave="sine", half=None, delay=0, hide_before=False, wavelength=12,
                 hinge="left"):
        self._boxk = box
        self._axis = axis
        self._amp = amp
        self._period = max(4, period)
        self._phase = phase
        self._wave = wave
        self._half = half
        self._delay = delay
        self._hide = hide_before
        self._wl = max(4, wavelength)
        self._hinge = hinge

    def start(self, display, tile, bitmap, palette, base_colors):
        super().start(display, tile, bitmap, palette, base_colors)
        x0, y0, x1, y1 = self._boxk
        pix = []
        for y in range(max(0, y0), min(bitmap.height, y1 + 1)):
            for x in range(max(0, x0), min(bitmap.width, x1 + 1)):
                ci = bitmap[x, y]
                if ci != 0:
                    pix.append((x, y, ci))
        cap = 240 if self._wave in ("ripple", "hinge") else 320   # these restamp every frame
        if not pix or len(pix) > cap:             # too big = over budget -> fall back
            raise ValueError("region_shift: %d lit px" % len(pix))
        self._pix = pix
        self._x0 = x0
        self._x1 = max(x0 + 1, x1)
        self._stamped = [(x, y) for x, y, _ in pix]   # currently drawn positions
        self._last_off = 0
        self._hidden = False
        if self._hide:
            self._erase()                          # invisible until delay

    def _erase(self):
        bmp = self.bitmap
        for x, y in self._stamped:
            bmp[x, y] = 0
        self._stamped = []
        self._hidden = True

    def _stamp(self, off):
        bmp = self.bitmap
        w, h = bmp.width, bmp.height
        for x, y in self._stamped:                # erase only what we last drew
            bmp[x, y] = 0
        dx, dy = (off, 0) if self._axis == "x" else (0, off)
        stamped = []
        for x, y, ci in self._pix:
            xx, yy = x + dx, y + dy
            if 0 <= xx < w and 0 <= yy < h:
                bmp[xx, yy] = ci
                stamped.append((xx, yy))
        self._stamped = stamped
        self._last_off = off
        self._hidden = False

    def _stamp_ripple(self, frame):
        bmp = self.bitmap
        w, h = bmp.width, bmp.height
        for x, y in self._stamped:
            bmp[x, y] = 0
        k = 6.2832 / self._wl
        t = 6.2832 * frame / self._period
        stamped = []
        for x, y, ci in self._pix:
            yy = y + int(round(self._amp * math.sin(k * (x - self._x0) - t)))
            if 0 <= yy < h and 0 <= x < w:
                bmp[x, yy] = ci
                stamped.append((x, yy))
        self._stamped = stamped
        self._hidden = False

    def _stamp_hinge(self, frame):
        bmp = self.bitmap
        h = bmp.height                            # hinge rotates about x; only y is clamped
        for x, y in self._stamped:
            bmp[x, y] = 0
        s = math.sin(6.2832 * frame / self._period + self._phase)
        x0, x1 = self._x0, self._x1
        span = float(x1 - x0)
        stamped = []
        for x, y, ci in self._pix:
            wgt = (x1 - x) / span if self._hinge == "right" else (x - x0) / span
            yy = y + int(round(self._amp * s * wgt))
            if 0 <= yy < h:
                bmp[x, yy] = ci
                stamped.append((x, yy))
        self._stamped = stamped
        self._hidden = False

    def step(self, frame):
        if frame < self._delay:
            return                                # resting (or hidden) until the cue
        f = frame - self._delay
        if self._wave == "ripple":
            self._stamp_ripple(f)
            return
        if self._wave == "hinge":
            self._stamp_hinge(f)
            return
        if self._wave == "ramp":
            t = f / float(self._period)
            off = int(round(self._amp * (t if t < 1.0 else 1.0)))
        else:
            off = int(round(self._amp * math.sin(6.2832 * f / self._period + self._phase)))
            if self._half == "pos":
                off = abs(off)
            elif self._half == "neg":
                off = -abs(off)
        if off != self._last_off or self._hidden:  # unchanged offset -> zero cost
            self._stamp(off)

    def detach(self):
        try:
            if getattr(self, "_pix", None):
                self._stamp(0)                    # settle at rest (and un-hide) for the fade
        except Exception:
            pass


class OrbiterAnimator(IntroAnimator):
    """A tiny sprite loops an ellipse over the image (a bee circling the honey pot)."""

    HOLD_FRAMES = 96

    def __init__(self, cx, cy, rx, ry, period=64, sprite=((0, 0, 0xFFCC00),),
                 clockwise=True, delay=0, wobble=0):
        self._cx, self._cy = cx, cy
        self._rx, self._ry = rx, ry
        self._period = max(16, period)
        self._sprite = tuple(sprite)
        self._dir = 1.0 if clockwise else -1.0
        self._delay = delay                       # hidden until this frame (rx=ry=0 +
        self._wobble = wobble                     # delay = eyes appearing in a doorway)

    def start(self, display, tile, bitmap, palette, base_colors):
        super().start(display, tile, bitmap, palette, base_colors)
        colors = []
        self._cmap = {}
        for _, _, c in self._sprite:
            if c not in self._cmap:
                colors.append(c)
                self._cmap[c] = len(colors)       # overlay palette index (1-based)
        self._make_overlay(display, colors)

    def step(self, frame):
        overlay = self._overlay
        overlay.fill(0)
        if frame < self._delay:
            return
        th = 6.2832 * frame / self._period * self._dir
        px = self._cx + self._rx * math.cos(th)
        py = self._cy + self._ry * math.sin(th)
        if self._wobble:                          # erratic buzz on top of the orbit (a bee)
            px += self._wobble * math.sin(frame * 1.7)
            py += self._wobble * math.sin(frame * 2.3)
        w, h = overlay.width, overlay.height
        for dx, dy, c in self._sprite:
            xi, yi = int(px) + dx, int(py) + dy
            if 0 <= xi < w and 0 <= yi < h:
                overlay[xi, yi] = self._cmap[c]

    def detach(self):
        self._drop_overlay()


class BlinkAnimator(IntroAnimator):
    """Periodically cover a feature's lit pixels with a color (a wink, a rotor flicker).

    Overlay-only: during the "covered" window the captured pixels are painted ``color`` on
    the overlay (e.g. the fur color closes an eye — a wink; black over spinning rotor
    blades flickers them against the night sky). ``duty`` frames covered every ``period``.
    """

    HOLD_FRAMES = 96

    def __init__(self, box, color, period=70, duty=10, delay=28):
        self._boxk = box
        self._color = color
        self._period = max(8, period)
        self._duty = max(1, duty)
        self._delay = delay

    def start(self, display, tile, bitmap, palette, base_colors):
        super().start(display, tile, bitmap, palette, base_colors)
        self._make_overlay(display, (self._color,))
        x0, y0, x1, y1 = self._boxk
        self._cover = [(x, y)
                       for y in range(max(0, y0), min(display.height, y1 + 1))
                       for x in range(max(0, x0), min(display.width, x1 + 1))
                       if bitmap[x, y] != 0]

    def step(self, frame):
        overlay = self._overlay
        covered = frame >= self._delay and ((frame - self._delay) % self._period) < self._duty
        overlay.fill(0)
        if covered:
            for x, y in self._cover:
                overlay[x, y] = 1

    def detach(self):
        self._drop_overlay()
        self._cover = None


class SpriteLiftAnimator(IntroAnimator):
    """Lift a SUBJECT off the scene onto its own layer and move it; the scene stays fixed.

    Scene division: a boat crosses the water, the water does not move. At start,
    the subject's pixels (lit pixels inside ``boxes``, minus any near
    ``exclude_colors`` — e.g. the water blues) are copied onto an overlay tile, and the
    hole they leave in the base image is ROW-INPAINTED (each erased pixel takes the color
    of the nearest surviving pixel in its row — water bands and rails continue behind the
    subject automatically). The overlay then traverses: off-screen -> across -> off-screen,
    with optional bob and a ``slope`` (dy per dx) so a coaster car rides its drawn rail.
    Per-frame cost is two attribute writes — the cheapest mover in the engine.
    """

    HOLD_FRAMES = 104
    wants_writable_bitmap = True

    def __init__(self, boxes, exclude_colors=(), tol=28, path="lr", bob_amp=0,
                 slope=0.0, loop=False):
        self._boxes = boxes
        self._excl = tuple(exclude_colors)
        self._tol = tol
        self._path = path
        self._bob_amp = bob_amp
        self._slope = slope
        self._loop = loop

    def _is_excluded(self, rgb):
        t = self._tol
        r, g, b = (rgb >> 16) & 0xFF, (rgb >> 8) & 0xFF, rgb & 0xFF
        for e in self._excl:
            if (abs(r - ((e >> 16) & 0xFF)) <= t and abs(g - ((e >> 8) & 0xFF)) <= t
                    and abs(b - (e & 0xFF)) <= t):
                return True
        return False

    def start(self, display, tile, bitmap, palette, base_colors):
        super().start(display, tile, bitmap, palette, base_colors)
        w, h = bitmap.width, bitmap.height
        lifted = {}
        for bx in self._boxes:
            x0, y0, x1, y1 = bx
            for y in range(max(0, y0), min(h, y1 + 1)):
                for x in range(max(0, x0), min(w, x1 + 1)):
                    ci = bitmap[x, y]
                    if ci != 0 and (x, y) not in lifted \
                            and not self._is_excluded(base_colors[ci]):
                        lifted[(x, y)] = ci
        if not lifted:
            raise ValueError("lift: nothing captured")
        # Subject copy on its own layer (cloned palette, sky transparent).
        gfx = display.gfx
        opal = gfx.Palette(len(base_colors))
        for i, c in enumerate(base_colors):
            opal[i] = c
        opal.make_transparent(0)
        obmp = gfx.Bitmap(w, h, len(base_colors))
        for (x, y), ci in lifted.items():
            obmp[x, y] = ci
        otile = gfx.TileGrid(obmp, pixel_shader=opal)
        display.add_layer(otile)
        self._overlay = obmp
        self._overlay_tile = otile
        # Erase the subject from the scene, inpainting each hole pixel with the nearest
        # surviving pixel's color in its ROW (water bands / rails continue behind it).
        # Two sweeps per touched row — O(width) — instead of a per-pixel outward scan:
        # the naive scan cost ~1.6 s at start() for a large subject on a slow device.
        rows = {}
        for (x, y) in lifted:
            rows.setdefault(y, []).append(x)
        for y, xs in rows.items():
            left = [None] * w                     # (color, distance) from the left...
            last = None
            dist = 0
            for x in range(w):
                if (x, y) in lifted:
                    dist += 1
                else:
                    last = bitmap[x, y]
                    dist = 0
                left[x] = (last, dist)
            last = None
            dist = 0
            for x in range(w - 1, -1, -1):        # ...and from the right; nearer wins
                if (x, y) in lifted:
                    dist += 1
                else:
                    last = bitmap[x, y]
                    dist = 0
                lc, ld = left[x]
                if (x, y) in lifted:
                    if lc is None:
                        fillv = last if last is not None else 0
                    elif last is None or ld <= dist:
                        fillv = lc
                    else:
                        fillv = last
                    bitmap[x, y] = fillv if fillv is not None else 0

        xs = [x for x, _ in lifted]
        self._span_lo = -(max(xs) + 2)            # tile.x that fully hides the subject left
        self._span_hi = (w + 2) - min(xs)         # ... and off the right edge

    def step(self, frame):
        span = self.HOLD_FRAMES - 1
        t = (frame % span) / float(span) if self._loop else min(1.0, frame / float(span))
        lo, hi = self._span_lo, self._span_hi
        if self._path == "rl":
            lo, hi = hi, lo
        x = lo + (hi - lo) * t
        self._overlay_tile.x = int(round(x))
        y = self._slope * x
        if self._bob_amp:
            y += self._bob_amp * math.sin(frame * 0.3)
        self._overlay_tile.y = int(round(y))

    def detach(self):
        self._drop_overlay()


class CoverAnimator(IntroAnimator):
    """A multi-color patch that hides/repositions part of the art until a cue frame.

    Copies the lit pixels in ``box``, draws them on an overlay at (dx, dy) — and blanks
    their home position — so a dragon's painted-open mouth reads CLOSED (jaw drawn shifted
    up, the opening masked) until ``until``, when the overlay clears in one shot and the
    painted art (and whatever effect starts then) takes over. Zero per-frame cost.
    """

    HOLD_FRAMES = 96

    def __init__(self, box, dx=0, dy=-2, until=35, blank=True):
        self._boxk = box
        self._dx, self._dy = dx, dy
        self._until = until
        self._blank = blank

    def start(self, display, tile, bitmap, palette, base_colors):
        super().start(display, tile, bitmap, palette, base_colors)
        x0, y0, x1, y1 = self._boxk
        pix = [(x, y, bitmap[x, y])
               for y in range(max(0, y0), min(display.height, y1 + 1))
               for x in range(max(0, x0), min(display.width, x1 + 1))
               if bitmap[x, y] != 0]
        colors = [0x000000]                       # overlay palette: [sky, black, ...]
        idx = {}
        for _x, _y, ci in pix:
            c = base_colors[ci]
            if c not in idx:
                colors.append(c)
                idx[c] = len(colors)              # 1-based overlay index (0 transparent)
        overlay = self._make_overlay(display, colors)
        w, h = display.width, display.height
        if self._blank:
            for x, y, _ci in pix:                 # mask the painted (open) position
                overlay[x, y] = 1                 # black
        for x, y, ci in pix:                      # draw the shifted (closed) copy
            xx, yy = x + self._dx, y + self._dy
            if 0 <= xx < w and 0 <= yy < h:
                overlay[xx, yy] = idx[base_colors[ci]]
        self._cleared = False

    def step(self, frame):
        if not self._cleared and frame >= self._until:
            self._overlay.fill(0)                 # one-shot reveal of the painted art
            self._cleared = True

    def detach(self):
        self._drop_overlay()


class VanishAnimator(IntroAnimator):
    """Lit pixels in successive boxes disappear at staged times (a bite out of a donut).

    Each box's pixels erase in order starting at ``start``, ``interval`` frames apart.
    The bites persist through the fade — the donut stays bitten. Cost is a one-shot erase
    per bite frame; nothing per-frame otherwise.
    """

    HOLD_FRAMES = 96
    wants_writable_bitmap = True

    def __init__(self, boxes, start=40, interval=16):
        self._boxes = boxes
        self._start = start
        self._interval = max(1, interval)

    def start(self, display, tile, bitmap, palette, base_colors):
        super().start(display, tile, bitmap, palette, base_colors)
        self._done = [False] * len(self._boxes)

    def step(self, frame):
        for k, bx in enumerate(self._boxes):
            if self._done[k] or frame < self._start + k * self._interval:
                continue
            x0, y0, x1, y1 = bx
            bmp = self.bitmap
            for y in range(max(0, y0), min(bmp.height, y1 + 1)):
                for x in range(max(0, x0), min(bmp.width, x1 + 1)):
                    bmp[x, y] = 0
            self._done[k] = True

    def detach(self):
        pass                                       # bites persist; the copy is discarded


class FrameCycleAnimator(IntroAnimator):
    """Pre-baked displacement frames cycled by layer swap (a WHOLE flag waving).

    Large-region ripples cost too much restamped per frame in Python, so the frames
    are pre-baked at start: the region's pixels render into
    ``nframes`` bitmaps, each displaced by a different ripple phase, and step() just swaps
    which one is on the display — O(1) per frame. RAM: nframes small bitmaps while the
    image is on screen (freed at detach).
    """

    HOLD_FRAMES = 96
    wants_writable_bitmap = True

    def __init__(self, box, nframes=5, amp=2, wavelength=14, period=3,
                 exclude_colors=(), tol=28):
        self._boxk = box
        self._n = max(2, nframes)
        self._amp = amp
        self._wl = max(4, wavelength)
        self._period = max(1, period)
        self._excl = tuple(exclude_colors)
        self._tol = tol

    def start(self, display, tile, bitmap, palette, base_colors):
        super().start(display, tile, bitmap, palette, base_colors)
        x0, y0, x1, y1 = self._boxk
        w, h = bitmap.width, bitmap.height
        pix = [(x, y, bitmap[x, y])
               for y in range(max(0, y0), min(h, y1 + 1))
               for x in range(max(0, x0), min(w, x1 + 1))
               if bitmap[x, y] != 0]
        if not pix:
            raise ValueError("frames: nothing captured")
        self._pix = pix
        gfx = display.gfx
        opal = gfx.Palette(len(base_colors))
        for i, c in enumerate(base_colors):
            opal[i] = c
        opal.make_transparent(0)
        k = 6.2832 / self._wl
        self._frames = []
        for p in range(self._n):
            fb = gfx.Bitmap(w, h, len(base_colors))
            ph = 6.2832 * p / self._n
            for x, y, ci in pix:
                yy = y + int(round(self._amp * math.sin(k * (x - x0) - ph)))
                if 0 <= yy < h:
                    fb[x, yy] = ci
            self._frames.append(gfx.TileGrid(fb, pixel_shader=opal))
        for x, y, _ci in pix:                      # the cloth lives on the overlays now
            bitmap[x, y] = 0
        self._cur = 0
        display.add_layer(self._frames[0])

    def step(self, frame):
        idx = (frame // self._period) % self._n
        if idx != self._cur:
            try:
                self.display.remove_layer(self._frames[self._cur])
            except Exception:
                pass
            self.display.add_layer(self._frames[idx])
            self._cur = idx

    def detach(self):
        try:
            self.display.remove_layer(self._frames[self._cur])
        except Exception:
            pass
        try:                                       # restore the cloth for the fade
            for x, y, ci in self._pix:
                self.bitmap[x, y] = ci
        except Exception:
            pass
        self._frames = None
        self._pix = None


class ComboAnimator(IntroAnimator):
    """Compose two primitives (e.g. rocket = rise + exhaust emitter)."""

    def __init__(self, parts):
        self._parts = parts
        self.HOLD_FRAMES = max(p.HOLD_FRAMES for p in parts)
        self.wants_writable_bitmap = any(p.wants_writable_bitmap for p in parts)

    def start(self, display, tile, bitmap, palette, base_colors):
        # If a later part fails to start, detach the parts that already started —
        # otherwise their overlay layers leak on the display when the caller falls
        # back to the still image.
        started = []
        try:
            for p in self._parts:
                p.start(display, tile, bitmap, palette, base_colors)
                started.append(p)
        except Exception:
            for p in started:
                try:
                    p.detach()
                except Exception:
                    pass
            raise

    def step(self, frame):
        for p in self._parts:
            p.step(frame)

    def detach(self):
        for p in self._parts:
            try:
                p.detach()
            except Exception:
                pass


# ------------------------------------------------------------------------------------
# FEASIBILITY — attached to the CLASSES only (CircuitPython cannot set attributes on
# function objects; doing so would crash `import scrollkit.effects` on-device).
# "allocates_per_frame" is honest: Emitter builds a small list per spawn (every `rate`
# frames). FrameCycle allocates its nframes bitmaps at START only (~1 KB each at 64x32
# — budget RAM accordingly), then swaps layers O(1) per frame. Animators with
# wants_writable_bitmap also imply the host's one-time ~2 KB writable copy.
# ------------------------------------------------------------------------------------
TwinkleAnimator.FEASIBILITY = {
    "hardware_safe": True, "allocates_per_frame": False,
    "max_pixel_writes_per_frame": 40, "modeled_frame_ms": 1.0,
}
MotionAnimator.FEASIBILITY = {
    "hardware_safe": True, "allocates_per_frame": False,
    "max_pixel_writes_per_frame": 0, "modeled_frame_ms": 0.1,
}
EmitterAnimator.FEASIBILITY = {
    "hardware_safe": True, "allocates_per_frame": True,
    "max_pixel_writes_per_frame": 8, "modeled_frame_ms": 1.0,
}
PalettePulseAnimator.FEASIBILITY = {
    "hardware_safe": True, "allocates_per_frame": False,
    "max_pixel_writes_per_frame": 0, "modeled_frame_ms": 0.5,
}
RegionShiftAnimator.FEASIBILITY = {
    "hardware_safe": True, "allocates_per_frame": False,
    "max_pixel_writes_per_frame": 640, "modeled_frame_ms": 7.0,
}
OrbiterAnimator.FEASIBILITY = {
    "hardware_safe": True, "allocates_per_frame": False,
    "max_pixel_writes_per_frame": 8, "modeled_frame_ms": 0.5,
}
BlinkAnimator.FEASIBILITY = {
    "hardware_safe": True, "allocates_per_frame": False,
    "max_pixel_writes_per_frame": 320, "modeled_frame_ms": 2.0,
}
SpriteLiftAnimator.FEASIBILITY = {
    "hardware_safe": True, "allocates_per_frame": False,
    "max_pixel_writes_per_frame": 0, "modeled_frame_ms": 0.1,
}
CoverAnimator.FEASIBILITY = {
    "hardware_safe": True, "allocates_per_frame": False,
    "max_pixel_writes_per_frame": 0, "modeled_frame_ms": 0.1,
}
VanishAnimator.FEASIBILITY = {
    "hardware_safe": True, "allocates_per_frame": False,
    "max_pixel_writes_per_frame": 320, "modeled_frame_ms": 2.0,
}
FrameCycleAnimator.FEASIBILITY = {
    "hardware_safe": True, "allocates_per_frame": False,
    "max_pixel_writes_per_frame": 0, "modeled_frame_ms": 0.2,
}
ComboAnimator.FEASIBILITY = {
    "hardware_safe": True, "allocates_per_frame": True,
    "max_pixel_writes_per_frame": 648, "modeled_frame_ms": 8.0,
}

# The public animator primitives, in catalog order — the FEASIBILITY-carrying classes a
# host can instantiate and drive. Enumerated explicitly (not via __subclasses__, which is
# unreliable on CircuitPython) so callers, the docs reference generator, and its drift
# guard share one ordered source of truth; the base ``IntroAnimator`` and the bitmap
# helpers are deliberately excluded (they are scaffolding, not animations).
ANIMATOR_CLASSES = (
    TwinkleAnimator,
    MotionAnimator,
    EmitterAnimator,
    PalettePulseAnimator,
    RegionShiftAnimator,
    OrbiterAnimator,
    BlinkAnimator,
    SpriteLiftAnimator,
    CoverAnimator,
    VanishAnimator,
    FrameCycleAnimator,
    ComboAnimator,
)
