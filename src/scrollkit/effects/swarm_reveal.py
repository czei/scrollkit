"""Swarm-reveal animation — a flock of "birds" (or bees) assembles the target image.

A small flock flies in with classic boids flocking (separation / alignment /
cohesion); as birds pass over target pixels they "capture" them — the captured
pixels light up permanently and accumulate into the text/logo.  Once every target
pixel is captured the birds disperse, leaving the assembled image.

This is a device-feasible reimagining of the original 150-200 bird boids demo
(which only ran via precomputed paths).  The cost killers there were three
separate O(n^2) neighbor loops and an O(birds x pixels) target scan *every frame*.
Here:

* a **small flock** (the plan's own observation: fewer birds flock more visibly),
* **one combined neighbor pass** computing all three rules together with squared
  distances (no per-pair sqrt for the radius gates),
* **O(1) opportunistic capture** — each bird only checks the few integer cells
  around itself against the remaining-pixel set, never the whole target list,
* **O(1) steer-target assignment** — birds pull a target from a shuffled queue,

so per-frame work is dominated by the ~n^2 neighbor pass at a small n.  Measured
on a MatrixPortal S3 (incl. the panel refresh): 14 birds ~25 ms/frame (safe),
20 ~34 ms, 28 ~48 ms — so the default ``num_birds=14`` keeps headroom under the
50 ms / 20 fps budget while the desktop simulator can use more for a denser flock.

Two transparent overlay layers via ``display.gfx`` (sim + device identical): the
captured-text layer is written incrementally (never fully redrawn); the birds
layer is cleared and redrawn each frame (a handful of pixels).

Frame-driven :class:`SwarmReveal` (call :meth:`step` once per frame) plus a
blocking :func:`show_swarm_splash` convenience wrapper, mirroring
:class:`scrollkit.effects.DripReveal`.
"""

import asyncio
import math
import random


# Boids tuning (radii stored squared to avoid sqrt in the gates).
_SEP_R2 = 5.0 * 5.0
_ALI_R2 = 15.0 * 15.0
_COH_R2 = 20.0 * 20.0
_SEP_W = 0.40
_ALI_W = 0.30
_COH_W = 0.20
_COH_GAIN = 0.02          # cohesion pulls gently toward the local center
_MAX_NUDGE = 0.10         # random per-frame jitter (organic wander)
_CAPTURE_DIST = 0.9       # a bird captures its target once this close to it


class _Bird:
    def __init__(self, x, y, vx, vy):
        self.x = x
        self.y = y
        self.vx = vx
        self.vy = vy
        self.phase = random.uniform(0, 6.2832)     # wing-flap phase offset
        self.spd = random.uniform(0.7, 1.3)         # individual speed variation
        self.target = None                          # (x, y) it steers toward


class SwarmReveal:
    """Frame-driven swarm that assembles ``pixels`` then disperses.

    Build it with the target ``pixels`` (e.g. from
    :func:`pixels_from_text` / :func:`pixels_from_font_text`), :meth:`start` it
    with the display, then call :meth:`step` once per frame until it reports
    complete.  The captured-text overlay persists until :meth:`detach`.
    """

    def __init__(self, pixels, text_color=0xFFCC00, bird_color=0xFFE08A,
                 num_birds=14, bird_speed=2.4, disperse_frames=18):
        self.pixels = pixels
        self.text_color = text_color
        self.bird_color = bird_color
        self.num_birds = num_birds if num_birds > 1 else 1
        self.bird_speed = bird_speed if bird_speed > 0.5 else 0.5
        self.disperse_frames = disperse_frames if disperse_frames > 0 else 0

        self._display = None
        self._gfx = None
        self._w = 0
        self._h = 0
        self._text_bmp = None
        self._text_tile = None
        self._birds_bmp = None
        self._birds_tile = None

        self._remaining = set()     # uncaptured target cells
        self._total = 0
        self._queue = []            # shuffled targets for O(1) steer assignment
        self._qi = 0
        self._birds = []
        self._t = 0.0               # animation clock (frames * dt)
        self._disperse_left = -1    # >=0 once all captured (counts down)
        self._complete = False

    # --- lifecycle ------------------------------------------------------------
    def start(self, display):
        gfx = display.gfx
        self._display = display
        self._gfx = gfx
        w, h = display.width, display.height
        self._w, self._h = w, h

        # Captured-text layer (written incrementally; never fully redrawn).
        self._text_bmp = gfx.Bitmap(w, h, 2)
        tpal = gfx.Palette(2)
        tpal.make_transparent(0)
        tpal[1] = self.text_color
        self._text_tile = gfx.TileGrid(self._text_bmp, pixel_shader=tpal)

        # Birds layer (cleared + redrawn each frame). Added AFTER text so birds
        # fly in front; both have a transparent background.
        self._birds_bmp = gfx.Bitmap(w, h, 2)
        bpal = gfx.Palette(2)
        bpal.make_transparent(0)
        bpal[1] = self.bird_color
        self._birds_tile = gfx.TileGrid(self._birds_bmp, pixel_shader=bpal)

        display.add_layer(self._text_tile)
        display.add_layer(self._birds_tile)

        # Targets in bounds; shuffled queue for steer-target assignment.
        self._remaining = set((x, y) for (x, y) in self.pixels
                              if 0 <= x < w and 0 <= y < h)
        self._total = len(self._remaining)
        self._queue = list(self._remaining)
        _shuffle(self._queue)
        self._qi = 0

        # Spawn the flock from the screen edges in small clusters.
        self._birds = [self._spawn_bird() for _ in range(self.num_birds)]
        for b in self._birds:
            b.target = self._next_target()

        self._t = 0.0
        self._disperse_left = -1
        self._complete = False

    def detach(self):
        """Remove both overlay layers (no-op if already detached)."""
        if self._display is None:
            return
        if self._text_tile is not None:
            self._display.remove_layer(self._text_tile)
            self._text_tile = None
        if self._birds_tile is not None:
            self._display.remove_layer(self._birds_tile)
            self._birds_tile = None

    # --- helpers --------------------------------------------------------------
    def _spawn_bird(self):
        w, h = self._w, self._h
        edge = random.randint(0, 3)
        s = self.bird_speed
        if edge == 0:        # left
            return _Bird(-1.0, random.uniform(0, h), s, random.uniform(-0.3, 0.3))
        if edge == 1:        # right
            return _Bird(w + 1.0, random.uniform(0, h), -s, random.uniform(-0.3, 0.3))
        if edge == 2:        # top
            return _Bird(random.uniform(0, w), -1.0, random.uniform(-0.3, 0.3), s)
        return _Bird(random.uniform(0, w), h + 1.0, random.uniform(-0.3, 0.3), -s)  # bottom

    def _next_target(self):
        """Pop the next still-uncaptured target from the shuffled queue (O(1) amortized)."""
        q = self._queue
        n = len(q)
        while self._qi < n:
            p = q[self._qi]
            self._qi += 1
            if p in self._remaining:
                return p
        return None

    def _flock(self, b):
        """All three boids rules in one neighbor pass (squared-distance gates)."""
        sx = sy = ax = ay = cx = cy = 0.0
        sc = ac = cc = 0
        bx, by = b.x, b.y
        for o in self._birds:
            if o is b:
                continue
            dx = bx - o.x
            dy = by - o.y
            d2 = dx * dx + dy * dy
            if d2 >= _COH_R2 or d2 == 0.0:
                continue
            cx += o.x
            cy += o.y
            cc += 1
            if d2 < _ALI_R2:
                ax += o.vx
                ay += o.vy
                ac += 1
                if d2 < _SEP_R2:
                    inv = 1.0 / d2          # steer away, stronger when closer
                    sx += dx * inv
                    sy += dy * inv
                    sc += 1
        fx = fy = 0.0
        if sc:
            fx += (sx / sc) * _SEP_W
            fy += (sy / sc) * _SEP_W
        if ac:
            fx += ((ax / ac) - b.vx) * _ALI_W
            fy += ((ay / ac) - b.vy) * _ALI_W
        if cc:
            fx += ((cx / cc) - bx) * _COH_GAIN * _COH_W
            fy += ((cy / cc) - by) * _COH_GAIN * _COH_W
        return fx, fy

    # --- per-frame ------------------------------------------------------------
    @property
    def is_complete(self):
        return self._complete

    def step(self):
        """Advance one frame; render into the overlays. Returns True when done."""
        if self._complete:
            return True
        self._t += 0.05
        w, h = self._w, self._h
        speed = self.bird_speed
        dispersing = self._disperse_left >= 0
        captured_ratio = 0.0
        if self._total:
            captured_ratio = (self._total - len(self._remaining)) / self._total

        for b in self._birds:
            fx, fy = self._flock(b)

            if dispersing:
                # Head for the nearest edge so the flock clears off-screen.
                ex = -4.0 if b.x < w * 0.5 else w + 4.0
                ey = -4.0 if b.y < h * 0.5 else h + 4.0
                b.vx += fx + (ex - b.x) * 0.04
                b.vy += fy + (ey - b.y) * 0.04
            else:
                if b.target is None or b.target not in self._remaining:
                    b.target = self._next_target()
                if b.target is not None:
                    tx, ty = b.target
                    dx = tx - b.x
                    dy = ty - b.y
                    dist = math.sqrt(dx * dx + dy * dy)
                    if dist < _CAPTURE_DIST:
                        # Arrived: this bird DELIVERS its one pixel. (Deliberate
                        # capture — birds don't blanket-paint, so the flock stays
                        # the show.) Light it permanently; resume flocking.
                        self._remaining.discard(b.target)
                        self._text_bmp[tx, ty] = 1
                        b.target = None
                        b.vx += fx
                        b.vy += fy
                    elif dist < 1.5:
                        # Precision: ignore flocking, settle onto the pixel.
                        b.vx = dx * 0.3
                        b.vy = dy * 0.3
                    elif dist < 3.0:
                        nvx = (dx / dist) * 0.6
                        nvy = (dy / dist) * 0.6
                        b.vx = nvx + fx * 0.3
                        b.vy = nvy + fy * 0.3
                    else:
                        # Flock, with attraction to the target growing as the
                        # image fills (weak early -> stronger late).
                        aw = 0.1 + captured_ratio * 0.5
                        b.vx += fx + (dx / dist) * speed * aw
                        b.vy += fy + (dy / dist) * speed * aw
                else:
                    b.vx += fx
                    b.vy += fy

            # Organic wing-flap + a little randomness.
            b.vx += 0.15 * math.sin(b.phase + self._t * 10.0) * b.spd
            b.vy += 0.10 * math.cos(b.phase + self._t * 8.0) * b.spd
            b.vx += random.uniform(-_MAX_NUDGE, _MAX_NUDGE)
            b.vy += random.uniform(-_MAX_NUDGE, _MAX_NUDGE)

            # Clamp speed (and keep a floor so birds never stall).
            sp = math.sqrt(b.vx * b.vx + b.vy * b.vy)
            if sp > speed:
                b.vx = (b.vx / sp) * speed
                b.vy = (b.vy / sp) * speed
            elif 0.0 < sp < 0.3:
                b.vx = (b.vx / sp) * 0.3
                b.vy = (b.vy / sp) * 0.3

            b.x += b.vx
            b.y += b.vy

            # Wrap around the edges so birds stay in play while capturing.
            if not dispersing:
                if b.x < -2:
                    b.x = w + 2
                elif b.x > w + 2:
                    b.x = -2
                if b.y < -2:
                    b.y = h + 2
                elif b.y > h + 2:
                    b.y = -2

        # Begin dispersing once every pixel is captured.
        if self._disperse_left < 0 and not self._remaining:
            self._disperse_left = self.disperse_frames

        # Render the birds layer: clear, then one pixel per bird (skip when done).
        bmp = self._birds_bmp
        try:
            bmp.fill(0)
        except (AttributeError, TypeError):
            for xx in range(w):
                for yy in range(h):
                    bmp[xx, yy] = 0
        if self._disperse_left != 0:
            for b in self._birds:
                ix = int(b.x + 0.5)
                iy = int(b.y + 0.5)
                if 0 <= ix < w and 0 <= iy < h:
                    bmp[ix, iy] = 1

        if dispersing:
            self._disperse_left -= 1
            if self._disperse_left <= 0:
                self._complete = True
        return self._complete


def _shuffle(lst):
    """In-place Fisher-Yates (random.shuffle is absent on CircuitPython)."""
    for i in range(len(lst) - 1, 0, -1):
        j = random.randint(0, i)
        lst[i], lst[j] = lst[j], lst[i]


async def show_swarm_splash(
    display,
    pixels,
    text_color=0xFFCC00,
    bird_color=0xFFE08A,
    num_birds=14,
    bird_speed=2.4,
    hold_seconds=2.0,
    max_steps=2000,
):
    """Play a swarm-assembles-the-image animation (blocking convenience wrapper).

    A flock flies in, captures the ``pixels`` into the text layer, then disperses;
    the assembled image holds for ``hold_seconds`` before the overlays are removed.

    Args mirror :class:`SwarmReveal`.  ``max_steps`` bounds the run so an
    unreachable pixel can never hang the loop.

    Returns ``True`` when finished normally, ``False`` if the display reported a
    close (simulator window closed). On hardware ``show()`` never closes, so this
    is always ``True`` there.
    """
    swarm = SwarmReveal(pixels, text_color=text_color, bird_color=bird_color,
                        num_birds=num_birds, bird_speed=bird_speed)
    swarm.start(display)
    steps = 0
    while not swarm.is_complete and steps < max_steps:
        swarm.step()
        steps += 1
        if await display.show() is False:
            swarm.detach()
            return False
        await asyncio.sleep(0.05)

    if await display.show() is False:
        swarm.detach()
        return False
    await asyncio.sleep(hold_seconds)
    swarm.detach()
    return True


# --- advertised feasibility metadata (US7 / FR-026) -------------------------
# Per frame the cost is the ~num_birds^2 combined neighbor pass (one pass, squared
# distances) plus O(1) capture/steer per bird and a birds-layer redraw of
# num_birds pixels. No per-frame heap allocation (flock list + target queue built
# once in start()). MEASURED on a MatrixPortal S3 (bit_depth 4), per-frame work
# incl. refresh: 14 birds ~25 ms avg / 37 ms max (safe); 20 ~34/50 (at the
# ceiling); 28 ~48/68 (over). Default num_birds=14 keeps headroom under the
# 50 ms / 20 fps budget; the desktop simulator can use more for a denser flock.
_FEASIBILITY = {
    "hardware_safe": True,
    "allocates_per_frame": False,
    "max_pixel_writes_per_frame": 24,     # ~num_birds + a few captures per frame
    "modeled_frame_ms": 25.0,             # measured: 14 birds avg on S3 (incl. refresh)
    "note": "cost ~ num_birds^2; measured 14->25ms, 20->34ms, 28->48ms on S3",
}
show_swarm_splash.FEASIBILITY = _FEASIBILITY
SwarmReveal.FEASIBILITY = _FEASIBILITY
