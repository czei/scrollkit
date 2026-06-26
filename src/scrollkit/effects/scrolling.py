"""Class 1 — characterful scrolling (built on the easing engine + fixed-point scroll).

Three scrolling content types that feel alive instead of a constant 1 px/frame crawl:

- :class:`KineticMarquee` — mass/inertia: accelerates in, coasts, dwells at
  punctuation/keywords, overshoots then springs back. Only a single reused Label's
  ``.x`` (and, briefly, ``.y`` is untouched) changes per frame; the glyph bitmap is
  built once.
- :class:`WaveRider` — characters ride a precomputed integer sine path; only the
  visible window of single-char Labels is realized.
- :class:`SplitFlap` — entering characters flip through a small *deterministic*
  sequence of intermediate glyphs (seeded LCG, no per-frame ``random`` allocation)
  before landing, staggered left-to-right.

All three are async ``DisplayContent``, run unchanged on device and simulator, do no
per-frame heap allocation on the hot path, and pass the strict feasibility gate at
20 fps (single / few small Labels per frame; the gate tolerates the bounded,
isolated glyph rebuilds these produce).
"""

import math

from ..display.content import DisplayContent, LOOP_FPS
from .easing import interp, ease, EASE_OUT_QUAD


def _delta_q(speed):
    """Per-frame motion in 1/16-px units from a px/sec speed (>=1)."""
    d = int(round(speed * 16 / LOOP_FPS))
    return d if d > 0 else 1


class KineticMarquee(DisplayContent):
    """Scrolling text with mass: eased accelerate-in, dwell at ``pause_chars``, an
    overshoot+spring at each dwell, then scroll off. The whole message lives in ONE
    reused Label whose ``.x`` moves per frame (glyph bitmap built once).

    Advertised hardware budget (see ``FEASIBILITY``): one Label, repositioned each
    frame; a single glyph rebuild on first show — strict-feasible at 20 fps.
    """

    FEASIBILITY = {
        "hardware_safe": True,
        "allocates_per_frame": False,
        "max_pixel_writes_per_frame": 0,    # only Label .x changes; no painter writes
        "modeled_frame_ms": 6.0,            # ~refresh + one repositioned label
    }

    ACCEL_FRAMES = 10       # eased ramp-up of the entry velocity
    DWELL_FRAMES = 12       # hold when a pause char is centered (~0.6 s at 20 fps)
    SPRING_PX = 3           # overshoot distance past the dwell target
    SPRING_FRAMES = 3       # frames to spring back from the overshoot

    def __init__(self, text, y=0, color=0xFFFFFF, speed=30,
                 pause_chars=".,!?;:", overshoot=True, priority=2):
        super().__init__(duration=None, priority=priority)
        self.text = text
        self.y = y
        self.color = color
        self.speed = speed
        self.pause_chars = pause_chars
        self.overshoot = overshoot
        self._pos_q = None          # text left-edge x in 1/16 px
        self._width = 0             # measured text width (px)
        self._targets = ()          # pos_q values (descending) centering a pause char
        self._ti = 0                # index of the next dwell target
        self._dwell = 0             # remaining dwell frames
        self._spring = 0            # remaining spring-back frames (moves right)
        self._spring_from = 0       # pos_q at the start of the spring
        self._frame = 0             # frames since first render (drives entry accel)

    async def start(self):
        await super().start()
        self._pos_q = None
        self._ti = 0
        self._dwell = 0
        self._spring = 0
        self._frame = 0

    def _setup(self, display):
        self._width = display.measure_text(self.text)
        center = display.width // 2
        targets = []
        for i, ch in enumerate(self.text):
            if ch in self.pause_chars:
                left = display.measure_text(self.text[:i])
                right = display.measure_text(self.text[:i + 1])
                glyph_center = (left + right) // 2
                targets.append((center - glyph_center) << 4)
        self._targets = tuple(targets)
        self._pos_q = display.width << 4        # start off the right edge

    async def render(self, display):
        if self._pos_q is None:
            self._setup(display)
        await display.draw_text(self.text, self._pos_q >> 4, self.y, self.color)
        self._advance()

    def _advance(self):
        self._frame += 1
        if self._dwell > 0:                     # holding at a pause char
            self._dwell -= 1
            return
        if self._spring > 0:                    # springing back to the target (rightward)
            self._spring -= 1
            done = self.SPRING_FRAMES - self._spring
            self._pos_q = self._spring_from + (self.SPRING_PX << 4) * done // self.SPRING_FRAMES
            if self._spring == 0:
                self._dwell = self.DWELL_FRAMES
            return

        d = _delta_q(self.speed)
        if self._frame <= self.ACCEL_FRAMES:    # eased accelerate-in
            prog = self._frame * 255 // self.ACCEL_FRAMES
            d = interp(EASE_OUT_QUAD, 1, d, prog)
        self._pos_q -= d

        if self._ti < len(self._targets) and self._pos_q <= self._targets[self._ti]:
            tgt = self._targets[self._ti]
            self._ti += 1
            if self.overshoot:                  # slide past, then spring back to tgt
                self._pos_q = tgt - (self.SPRING_PX << 4)
                self._spring_from = self._pos_q
                self._spring = self.SPRING_FRAMES
            else:
                self._pos_q = tgt
                self._dwell = self.DWELL_FRAMES

        if (self._pos_q >> 4) < -self._width:
            self._is_complete = True

    @property
    def is_complete(self):
        return self._is_complete

    def describe(self):
        info = super().describe()
        info.update({
            "text": self.text, "y": self.y, "speed": self.speed,
            "position": None if self._pos_q is None else (self._pos_q >> 4),
            "dwelling": self._dwell > 0 or self._spring > 0,
        })
        return info


class WaveRider(DisplayContent):
    """Characters ride a precomputed integer sine path as the message scrolls. Only
    the visible window of single-char Labels is realized each frame:
    ``y = baseline + wave_table[(x // step + phase) & 255]``.

    Advertised hardware budget (see ``FEASIBILITY``): one small Label per visible
    column (~11 on a 64-px panel), repositioned each frame; rebuilds only as
    characters cross the viewport edge — strict-feasible at 20 fps.
    """

    FEASIBILITY = {
        "hardware_safe": True,
        "allocates_per_frame": False,
        "max_pixel_writes_per_frame": 0,    # Label moves only; no painter writes
        "modeled_frame_ms": 16.0,           # ~refresh + a bounded visible-window
    }

    PHASE_STEP = 8          # wave phase advance per frame (cycles every 32 frames)

    def __init__(self, text, y=0, color=0xFFFFFF, speed=30,
                 amplitude=4, wavelength=16, priority=2):
        super().__init__(duration=None, priority=priority)
        self.text = text
        self.y = y
        self.color = color
        self.speed = speed
        self.amplitude = amplitude
        self.wavelength = max(2, wavelength)
        # Precompute the 256-entry integer wave table ONCE (float sin at construction
        # only; the hot path is a pure table lookup). Values in [-amplitude, +amplitude].
        self._wave = tuple(
            int(round(amplitude * math.sin(2.0 * math.pi * i / 256.0)))
            for i in range(256)
        )
        # 256 / wavelength_px, fixed-point so a few px of x map across the table.
        self._x_scale = 256 // self.wavelength
        self._pos_q = None      # left-edge x of the message, 1/16 px
        self._advances = ()     # per-char advance widths (px)
        self._offsets = ()      # cumulative left offset of each char (px)
        self._width = 0
        self._phase = 0

    async def start(self):
        await super().start()
        self._pos_q = None
        self._phase = 0

    def _setup(self, display):
        advances = []
        offsets = []
        cum = 0
        for ch in self.text:
            offsets.append(cum)
            adv = display.measure_text(ch) or 6
            advances.append(adv)
            cum += adv
        self._advances = tuple(advances)
        self._offsets = tuple(offsets)
        self._width = cum
        self._pos_q = display.width << 4

    async def render(self, display):
        if self._pos_q is None:
            self._setup(display)
        base_x = self._pos_q >> 4
        w = display.width
        baseline = self.y
        wave = self._wave
        scale = self._x_scale
        phase = self._phase
        # Realize only the visible-window characters (others are not drawn at all).
        for i in range(len(self.text)):
            x = base_x + self._offsets[i]
            adv = self._advances[i]
            if x + adv <= 0 or x >= w:
                continue                    # off-screen: not realized
            yy = baseline + wave[(x // scale + phase) & 255]
            await display.draw_text(self.text[i], x, yy, self.color)
        self._phase = (self._phase + self.PHASE_STEP) & 255
        self._pos_q -= _delta_q(self.speed)
        if (self._pos_q >> 4) < -self._width:
            self._is_complete = True

    @property
    def is_complete(self):
        return self._is_complete

    def describe(self):
        info = super().describe()
        info.update({
            "text": self.text, "y": self.y, "speed": self.speed,
            "amplitude": self.amplitude, "wavelength": self.wavelength,
            "position": None if self._pos_q is None else (self._pos_q >> 4),
        })
        return info


class SplitFlap(DisplayContent):
    """A split-flap board: each cell flips through ``flip_steps`` deterministic
    intermediate glyphs (seeded LCG — no per-frame ``random`` allocation) before
    landing on its real character, staggered left-to-right.

    Advertised hardware budget (see ``FEASIBILITY``): one small Label per cell;
    glyph rebuilds happen only on the few cells actively flipping in a given frame
    (bounded), then stop once landed — strict-feasible at 20 fps.
    """

    FEASIBILITY = {
        "hardware_safe": True,
        "allocates_per_frame": False,
        "max_pixel_writes_per_frame": 0,    # Labels only; flips are bounded rebuilds
        "modeled_frame_ms": 18.0,           # ~refresh + a few cells rebuilding
    }

    STAGGER = 2             # frames between successive cells starting to flip
    HOLD_FRAMES = 20        # how long to hold the fully-landed board before completing
    _ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    def __init__(self, text, y=0, color=0xFFFFFF, speed=30,
                 flip_steps=3, seed=1, priority=2):
        super().__init__(duration=None, priority=priority)
        self.text = text
        self.y = y
        self.color = color
        self.speed = speed
        self.flip_steps = max(2, min(4, flip_steps))
        self.seed = seed
        self._flips = ()        # per-cell tuple of intermediate glyph strings
        self._x = ()            # per-cell x position (px)
        self._frame = 0
        self._built = False

    async def start(self):
        await super().start()
        self._frame = 0
        self._built = False

    def _setup(self, display):
        # Deterministic intermediate glyphs from a seeded LCG (integer state only).
        state = (self.seed * 2654435761 + 1) & 0x7FFFFFFF
        flips = []
        xs = []
        cum = 0
        alpha = self._ALPHABET
        for ch in self.text:
            seq = []
            for _ in range(self.flip_steps):
                state = (state * 1103515245 + 12345) & 0x7FFFFFFF
                seq.append(alpha[state % len(alpha)])
            flips.append(tuple(seq))
            xs.append(cum)
            cum += display.measure_text(ch) or 6
        self._flips = tuple(flips)
        self._x = tuple(xs)
        self._built = True

    async def render(self, display):
        if not self._built:
            self._setup(display)
        landed_all = True
        for i, ch in enumerate(self.text):
            local = self._frame - i * self.STAGGER
            if local < 0:
                landed_all = False
                continue                    # this cell has not started flipping yet
            if local < self.flip_steps:
                glyph = self._flips[i][local]
                landed_all = False
            else:
                glyph = ch                  # landed on the real character
            await display.draw_text(glyph, self._x[i], self.y, self.color)
        self._frame += 1
        last_land = (len(self.text) - 1) * self.STAGGER + self.flip_steps
        if landed_all and self._frame > last_land + self.HOLD_FRAMES:
            self._is_complete = True

    @property
    def is_complete(self):
        return self._is_complete

    def describe(self):
        info = super().describe()
        info.update({
            "text": self.text, "y": self.y, "flip_steps": self.flip_steps,
            "seed": self.seed, "frame": self._frame,
        })
        return info


# --- content pairing ---------------------------------------------------------
# Which content presentation each scroller looks best as, surfaced in
# capabilities()/docs so app authors and AI agents pick the right effect for the
# content. Vocabulary: "static" (a held frame), "scrolling" (moving text),
# "fullscreen" (a screen-wide transition). Class-level (CircuitPython can't tag
# functions). Marquee and WaveRider ARE scrolling presentations; SplitFlap flips
# characters in place, so it reads as held/static text.
KineticMarquee.PAIRS_WITH = ("scrolling",)
WaveRider.PAIRS_WITH = ("scrolling",)
SplitFlap.PAIRS_WITH = ("static",)

_SCROLLERS = (KineticMarquee, WaveRider, SplitFlap)


def scrollers_for(presentation):
    """The Class-1 scroller CLASSES suited to `presentation` ('static' | 'scrolling').

    Each returned class is a ``DisplayContent`` you add to the content queue. For
    scrolling text use ``scrollers_for("scrolling")``. Reads the live PAIRS_WITH
    tags, so it stays current as scrollers are added or retagged.

        cls = random.choice(scrollers_for("scrolling"))
        app.content_queue.add(cls("Space Mountain  45 min", y=12))
    """
    return tuple(cls for cls in _SCROLLERS
                 if presentation in getattr(cls, "PAIRS_WITH", ()))
