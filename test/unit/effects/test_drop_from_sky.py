"""DropFromSky slides new content in from an edge — default top, plus bottom/left/right."""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import asyncio

from scrollkit.effects.transitions import DropFromSky


class _Display:
    width = 64
    height = 32


class _Content:
    def __init__(self):
        self.x = 10
        self.y = 20


def _slide(direction=None):
    """Return (first on-screen position, final position, completed) for a slide."""
    display = _Display()
    content = _Content()
    t = DropFromSky() if direction is None else DropFromSky(direction=direction)

    async def run():
        await t.start(display, lambda: None)
        t.pre_render_hook(content)              # frame 0: content sits at the edge
        first = (content.x, content.y)
        await t.render(display, content)
        for _ in range(DropFromSky.FALL_FRAMES + 2):
            t.pre_render_hook(content)
            await t.render(display, content)
        return first, (content.x, content.y), t.is_complete

    return asyncio.run(run())


def test_default_is_from_the_top():
    first, last, done = _slide()               # no direction -> top
    assert first == (10, 0)                    # x natural, y at the top edge
    assert last == (10, 20) and done           # restored to its natural position


def test_from_bottom_starts_below():
    first, last, done = _slide("bottom")
    assert first == (10, 32)                   # y starts at the bottom edge
    assert last == (10, 20) and done


def test_from_left_and_right_start_off_screen_horizontally():
    fl, last_l, done_l = _slide("left")
    assert fl[0] < 0 and fl[1] == 20           # x off the left edge, y natural
    assert last_l == (10, 20) and done_l

    fr, last_r, done_r = _slide("right")
    assert fr[0] >= 64 and fr[1] == 20         # x off the right edge, y natural
    assert last_r == (10, 20) and done_r


def test_unknown_direction_falls_back_to_top():
    assert DropFromSky(direction="sideways").direction == "top"
