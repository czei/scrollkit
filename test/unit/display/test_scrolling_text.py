"""ScrollingText: speed actually drives motion (fixed-point), width is MEASURED
(not len*6), and measurement happens once (off the hot path).

Uses a stub display with a controlled fake font of UNEQUAL glyph advances so the
measured width cannot coincide with a uniform-6px ``len(text)*6`` estimate.
"""

import pytest

from scrollkit.display.content import ScrollingText, LOOP_FPS


class _StubDisplay:
    """Minimal display: records draw_text x and measures with unequal advances."""
    ADV = {"A": 3, "W": 7, "B": 5, " ": 4}

    def __init__(self, width=64):
        self._width = width
        self.draws = []          # x positions drawn
        self.measure_calls = 0

    @property
    def width(self):
        return self._width

    def measure_text(self, text, font=None):
        self.measure_calls += 1
        return sum(self.ADV.get(ch, 6) for ch in text)

    async def draw_text(self, text, x, y=0, color=0xFFFFFF, font=None):
        self.draws.append(x)


async def _run(content, display, frames):
    await content.start()
    for _ in range(frames):
        await content.render(display)


@pytest.mark.asyncio
async def test_speed_scales_motion_roughly_linearly():
    slow = ScrollingText("AWB", x=0, speed=30)
    fast = ScrollingText("AWB", x=0, speed=60)
    ds, df = _StubDisplay(), _StubDisplay()
    await _run(slow, ds, 10)
    await _run(fast, df, 10)
    # Distance travelled from the start over the same frame count.
    moved_slow = ds.draws[0] - ds.draws[-1]
    moved_fast = df.draws[0] - df.draws[-1]
    assert moved_slow > 0 and moved_fast > 0
    # ~2x speed -> ~2x distance (allow rounding slack).
    assert abs(moved_fast - 2 * moved_slow) <= 2


@pytest.mark.asyncio
async def test_per_frame_delta_matches_speed_over_loop_fps():
    content = ScrollingText("AWB", x=0, speed=40)
    d = _StubDisplay()
    await _run(content, d, 5)
    expected_step = round(40 * 16 / LOOP_FPS) / 16.0   # px per frame
    steps = [d.draws[i] - d.draws[i + 1] for i in range(len(d.draws) - 1)]
    # Integer render positions, but the average step tracks the sub-pixel speed.
    avg = sum(steps) / len(steps)
    assert abs(avg - expected_step) <= 1.0


@pytest.mark.asyncio
async def test_width_is_measured_not_len_times_six():
    content = ScrollingText("AWB", x=0, speed=30)
    d = _StubDisplay()
    await _run(content, d, 1)
    # 3 + 7 + 5 = 15, NOT len("AWB")*6 == 18.
    assert content._measured_width == 15
    assert content.describe()["text_width"] == 15


@pytest.mark.asyncio
async def test_width_measured_exactly_once():
    content = ScrollingText("AWB", x=0, speed=30)
    d = _StubDisplay()
    await _run(content, d, 25)
    assert d.measure_calls == 1            # measured on first render only


@pytest.mark.asyncio
async def test_completes_after_scrolling_off_measured_width():
    # Start at x=0, width 15; with speed it must finish once it passes -15.
    content = ScrollingText("AWB", x=0, speed=240)   # ~12 px/frame
    d = _StubDisplay()
    await content.start()
    completed_at = None
    for i in range(20):
        await content.render(d)
        if content.is_complete:
            completed_at = i
            break
    assert completed_at is not None
    assert (content._pos_q >> 4) < -content._measured_width
