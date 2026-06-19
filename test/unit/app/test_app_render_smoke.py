"""End-to-end render smoke test for the app loop.

The rest of the suite tests units in isolation with mocks — it never actually
runs ``ScrollKitApp.run()`` against the real simulator and checks that something
visible happens over time. That gap let two show-stoppers ship while every unit
test stayed green:

  1. ``create_task`` was declared ``async def`` -> ``run()``'s ``gather`` awaited
     the wrapper coroutines (which spawn detached tasks and return instantly), so
     the display loop died after a single frame.
  2. The simulator's default brightness was 0.3, so rendered content was almost
     invisible.

This test drives the real loop headlessly (SDL dummy video) and asserts the
loop keeps iterating (the scroll position advances) AND that bright pixels are
actually drawn. Either bug above makes it fail.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # headless pygame, before import

import asyncio

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import ScrollingText


class _ScrollApp(ScrollKitApp):
    def __init__(self):
        super().__init__(enable_web=False, update_interval=10)

    async def create_display(self):
        from scrollkit.display.simulator import SimulatorDisplay
        return SimulatorDisplay(width=64, height=32)

    async def setup(self):
        self.content_queue.add(ScrollingText("SCROLL TEST", y=12, color=0xFFFFFF))


def _bright_pixels(surface):
    w, h = surface.get_size()
    n = 0
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = surface.get_at((x, y))[:3]
            if r + g + b > 250:
                n += 1
    return n


@pytest.mark.asyncio
async def test_app_loop_runs_continuously_and_renders_visible_pixels():
    app = _ScrollApp()
    try:
        await asyncio.wait_for(app.run(), timeout=2.0)
    except asyncio.TimeoutError:
        pass
    finally:
        app.stop()

    content = app.content_queue._current_content
    assert content is not None, "no content became current — setup/queue broken"

    # The scroll started at display width (64) and must have advanced left.
    # If the loop died after one frame (the create_task bug) this stays ~63-64.
    assert content._position is not None and content._position < 60, (
        f"scroll position did not advance (position={content._position}); "
        "the display loop is not iterating"
    )

    # Something bright is actually on the matrix. If brightness defaults too low
    # (the 0.3 bug) this is ~0.
    surface = app.display.matrix.get_surface()
    assert _bright_pixels(surface) > 20, "no visible/bright pixels were rendered"
