"""Class 1 — characterful scrolling: KineticMarquee, WaveRider, SplitFlap.

Behavioral assertions use a lightweight stub display (records every draw_text call);
strict-feasibility + no-per-frame-allocation use the real SimulatorDisplay through
``run_headless`` and the label-pool reuse invariant.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

from scrollkit.effects.scrolling import KineticMarquee, WaveRider, SplitFlap
from scrollkit.display.content import DisplayContent


class _StubDisplay:
    """Records every (text, x, y) draw; uniform 6-px font advance."""

    def __init__(self, width=64, height=32):
        self._width = width
        self._height = height
        self.frame_draws = []        # list of (text, x, y) for the CURRENT frame
        self.all_draws = []          # every (text, x, y) ever drawn

    @property
    def width(self):
        return self._width

    @property
    def height(self):
        return self._height

    def measure_text(self, text, font=None):
        return len(text) * 6

    async def draw_text(self, text, x, y=0, color=0xFFFFFF, font=None):
        self.frame_draws.append((text, x, y))
        self.all_draws.append((text, x, y))

    def new_frame(self):
        self.frame_draws = []


async def _drive(content, display, frames):
    await content.start()
    snapshots = []
    for _ in range(frames):
        display.new_frame()
        await content.render(display)
        snapshots.append(list(display.frame_draws))
    return snapshots


# --- KineticMarquee ---------------------------------------------------------

@pytest.mark.asyncio
async def test_kinetic_marquee_dwells_at_punctuation():
    d = _StubDisplay()
    m = KineticMarquee("GO. NOW", y=12, speed=60, overshoot=False)
    snaps = await _drive(m, d, 90)
    xs = [s[0][1] for s in snaps]            # the single label's x each frame
    # A dwell shows up as a run of consecutive frames where x does not change.
    longest = run = 1
    for a, b in zip(xs, xs[1:]):
        run = run + 1 if a == b else 1
        longest = max(longest, run)
    assert longest >= KineticMarquee.DWELL_FRAMES, (longest, xs)


@pytest.mark.asyncio
async def test_kinetic_marquee_overshoots_and_springs_back():
    d = _StubDisplay()
    m = KineticMarquee("GO. NOW", y=12, speed=60, overshoot=True)
    snaps = await _drive(m, d, 90)
    xs = [s[0][1] for s in snaps]
    # Overshoot+spring makes the label briefly move RIGHT (x increases) — a marquee
    # that only ever scrolls left never does this.
    assert any(b > a for a, b in zip(xs, xs[1:])), xs


@pytest.mark.asyncio
async def test_kinetic_marquee_uses_one_label_text_constant():
    d = _StubDisplay()
    m = KineticMarquee("HELLO WORLD", y=0, speed=45)
    snaps = await _drive(m, d, 40)
    # Exactly one draw per frame, always the full message (glyph built once; only .x moves).
    assert all(len(s) == 1 for s in snaps)
    assert all(s[0][0] == "HELLO WORLD" for s in snaps)


# --- WaveRider --------------------------------------------------------------

@pytest.mark.asyncio
async def test_wave_rider_realizes_only_visible_window():
    d = _StubDisplay(width=64)
    text = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123"     # 30 chars * 6px = 180px wide
    w = WaveRider(text, y=12, speed=30)
    snaps = await _drive(w, d, 20)
    visible_cap = d.width // 6 + 2               # window that can fit on a 64-px panel
    # Every frame draws only the on-screen characters, never the whole 30-char string.
    for s in snaps[1:]:                          # frame 0 may include the entry edge
        assert 0 < len(s) <= visible_cap, len(s)
        assert len(s) < len(text)


@pytest.mark.asyncio
async def test_wave_rider_chars_ride_a_wave_and_advance():
    d = _StubDisplay(width=64)
    w = WaveRider("ABCDEFGH", y=16, speed=30, amplitude=4)
    snaps = await _drive(w, d, 12)
    # Characters sit at varying y (the wave), not a flat baseline.
    ys = {y for s in snaps for (_t, _x, y) in s}
    assert len(ys) > 1, ys
    # And the whole thing advances: the drawn positions differ frame-to-frame.
    assert snaps[1] != snaps[5]


# --- SplitFlap --------------------------------------------------------------

@pytest.mark.asyncio
async def test_split_flap_is_deterministic_given_seed():
    da, db, dc = _StubDisplay(), _StubDisplay(), _StubDisplay()
    a = await _drive(SplitFlap("HELLO", seed=5), da, 30)
    b = await _drive(SplitFlap("HELLO", seed=5), db, 30)
    c = await _drive(SplitFlap("HELLO", seed=6), dc, 30)
    assert a == b                                 # same seed -> identical flips
    assert a != c                                 # different seed -> different flips


@pytest.mark.asyncio
async def test_split_flap_flips_then_lands():
    d = _StubDisplay()
    sf = SplitFlap("HI", y=0, flip_steps=3, seed=2)
    snaps = await _drive(sf, d, 60)
    # During the flip an intermediate glyph differs from the final character...
    first_cell_glyphs = [s[0][0] for s in snaps if s]
    assert any(g != "H" for g in first_cell_glyphs[:6]), first_cell_glyphs[:6]
    # ...and it eventually lands on the real text and completes.
    landed = [s for s in snaps if [g for (g, _x, _y) in s] == ["H", "I"]]
    assert landed, snaps[-1]
    assert sf.is_complete


# --- strict feasibility + no per-frame allocation (real simulator) ----------

pytest.importorskip("pygame")
from scrollkit.app.base import ScrollKitApp           # noqa: E402
from scrollkit.dev import run_headless                # noqa: E402


class _Looping(DisplayContent):
    """Re-instantiates the wrapped effect when it completes so the run keeps
    advancing for the whole feasibility window."""

    FACTORY = None

    def __init__(self):
        super().__init__(duration=None, priority=2)
        self._eff = self.FACTORY()
        self._started = False

    async def render(self, display):
        if not self._started:
            await self._eff.start()
            self._started = True
        await self._eff.render(display)
        if self._eff.is_complete:
            self._eff = self.FACTORY()
            await self._eff.start()

    @property
    def is_complete(self):
        return False


class _MarqueeLoop(_Looping):
    FACTORY = staticmethod(lambda: KineticMarquee("SCROLLKIT. GO!", y=12, speed=45))


class _WaveLoop(_Looping):
    FACTORY = staticmethod(lambda: WaveRider("WAVE RIDER DEMO", y=14, speed=30))


class _FlapLoop(_Looping):
    FACTORY = staticmethod(lambda: SplitFlap("SPLITFLAP", y=12, seed=3))


def _app(content_cls):
    class _App(ScrollKitApp):
        def __init__(self):
            super().__init__(enable_web=False, update_interval=10)
            self._c = None

        async def create_display(self):
            from scrollkit.display.simulator import SimulatorDisplay
            return SimulatorDisplay(width=64, height=32)

        async def prepare_display_content(self):
            return self._c

        async def setup(self):
            self._c = content_cls()
    return _App()


@pytest.mark.parametrize("cls", [_MarqueeLoop, _WaveLoop, _FlapLoop])
def test_class1_effects_pass_strict_at_20fps(cls):
    result = run_headless(_app(cls), frames=120, hardware=True, strict=True)
    assert result.errors == [], result.errors
    assert result.ok is True
    assert result.advanced is True


@pytest.mark.asyncio
async def test_wave_rider_reuses_labels_no_per_frame_alloc():
    from scrollkit.display.simulator import SimulatorDisplay
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    w = WaveRider("ABCDEFGHIJKLMNOPQR", y=14, speed=30)
    await w.start()
    for _ in range(80):
        await d.clear()
        await w.render(d)
        await d.show()
    # The label pool is bounded by the visible window, not the frame count.
    assert len(d._label_pool) <= d.width // 6 + 3
