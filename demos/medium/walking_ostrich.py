#!/usr/bin/env python3
"""ScrollKit demo (MEDIUM): a walking creature (true multi-pose cel animation).

`CelWalkAnimator` plays a real WALK CYCLE: it cycles through distinct AUTHORED leg
poses (not one leg region nudged up and down) while the whole sprite strides across
the panel. The ostrich walks in from the left, legs stepping and head nodding, then
off the right.

    ostrich.bmp  (the still)  +  ostrich_walk.bmp  (4 authored poses, side by side)

The two files sit next to each other in demos/assets/animators/. That pairing is the
whole convention: a cel walk needs a SIBLING spritesheet, `<name>_walk.bmp`, holding
N panel-sized frames in one strip (one shared palette, sky at slot 0). The animator
finds it from the still image's path — which is why `CelWalkAnimator` declares
`wants_image_path = True` and reads `self.image_path` (set below, exactly as the app's
ride-intro screen sets it via `for_image`).

── What makes it a "cel" walk ───────────────────────────────────────────────────
Most animators deform ONE loaded bitmap. A cel walk instead swaps between authored
frames: it loads the strip as a tile-indexed TileGrid, so advancing the gait is a
single `tile[0, 0] = pose` write and a step of travel is a `tile.x` write — no
per-frame allocation, no layer churn. It blanks the still (`wants_writable_bitmap`)
so the stationary ostrich doesn't sit behind the walking one, then walks off; the
caller's fade (in the app) would then show empty sky, like any traverse.

Drop a `<name>_walk.bmp` beside any `<name>.bmp` and this same animator walks it.

── Self-driving loop ────────────────────────────────────────────────────────────
Like image_intro, this demo keeps control in setup(): build a frame,
`await display.show()`, repeat at ~20 fps. An image animator MUST be `step()`-ed once
per displayed frame, which the self-driving style gives you (see image_intro.py and
docs/guide/effects.md#image-animators for the queue-vs-self-driving distinction).

Run on desktop (opens a pygame window):

    PYTHONPATH=src python demos/medium/walking_ostrich.py

The same code runs unchanged on an Adafruit MatrixPortal S3 — both BMPs (the still and
the `_walk` strip) just need to be on the board's filesystem.
"""

import sys
import os

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    import _demo_support as _support
except (AttributeError, ImportError):
    _support = None

import asyncio

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.unified import displayio
from scrollkit.effects.image_animators import CelWalkAnimator, read_indexed_bmp

# The still + its walk strip ship next to this demo (demos/assets/animators/).
_ART_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'animators')
_STILL = "ostrich.bmp"          # its sibling ostrich_walk.bmp holds the 4 walk poses

_CROSSINGS = 3                   # how many times the ostrich strides across
_GAP_FRAMES = 8                 # a short empty beat between crossings so the loop reads


class WalkingOstrichDemo(ScrollKitApp):

    def __init__(self):
        super().__init__(enable_web=False, update_interval=30)

    async def create_display(self):
        if _support is not None:
            return _support.simulator_display(getattr(self, "opts", None))
        try:
            from scrollkit.display.simulator import SimulatorDisplay
            return SimulatorDisplay(width=64, height=32)
        except ImportError:
            return await super().create_display()

    # setup() is self-driving: it runs the whole show and never returns while the
    # window is open (see the module docstring + image_intro.py).
    async def setup(self):
        if hasattr(self.display, "create_window"):
            await self.display.create_window("ScrollKit - Walking Ostrich (medium)")

        while self.running:
            for _ in range(_CROSSINGS):
                if not self.running:
                    return
                if await self._walk_across() is False:
                    return self._request_shutdown()
                if await self._pause(_GAP_FRAMES) is False:
                    return self._request_shutdown()

    async def _walk_across(self):
        """One crossing: load the still as a layer, drive the CelWalkAnimator contract."""
        display = self.display
        path = os.path.join(_ART_DIR, _STILL)
        # Same loader the app + image_intro use: OnDiskBitmap supplies the palette;
        # read_indexed_bmp decodes the pixels into a real (writable) Bitmap so the
        # animator can blank the still. Both calls run on device and simulator.
        odb = displayio.OnDiskBitmap(path)              # kept alive so the palette stays valid
        palette = odb.pixel_shader
        palette.make_transparent(0)                     # slot 0 = sky
        base_colors = _capture_base_colors(palette)
        bitmap = read_indexed_bmp(display.gfx, path)

        tile = displayio.TileGrid(bitmap, pixel_shader=palette)
        display.add_layer(tile)

        # Four authored leg poses keep the gait natural.  The small head-and-neck box
        # is pre-rotated once at start, then tile-swapped in sync with that gait.
        animator = CelWalkAnimator(
            period=6, bob=0,
            head_box=(39, 0, 54, 10), head_pivot=(39, 10),
            head_amp_deg=7,
        )
        # A cel walk needs the image path so it can find the sibling ostrich_walk.bmp.
        # The app injects this the same way (opt-in via wants_image_path); here we set it
        # by hand since we're driving the animator directly.
        animator.image_path = path
        try:
            animator.start(display, tile, bitmap, palette, base_colors)
            for frame in range(animator.HOLD_FRAMES):
                if not self.running:
                    break
                animator.step(frame)
                if await display.show() is False:       # window closed
                    return False
                await asyncio.sleep(0.05)               # ~20 fps
        finally:
            try:
                animator.detach()
            except Exception:
                pass
            display.remove_layer(tile)
        return True

    async def _pause(self, frames):
        """Hold an empty panel for a beat between crossings."""
        display = self.display
        for _ in range(frames):
            if not self.running:
                break
            await display.clear()
            if await display.show() is False:
                return False
            await asyncio.sleep(0.05)
        return True


def _capture_base_colors(palette):
    """The palette's original colours as 0xRRGGBB ints (before any fading).

    CircuitPython's Palette[i] is already RGB888; the simulator stores RGB565 and
    exposes the true colour via get_rgb888().
    """
    get888 = getattr(palette, "get_rgb888", None)
    if get888 is not None:
        return [(int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2])
                for c in (get888(i) for i in range(len(palette)))]
    return [palette[i] for i in range(len(palette))]


if __name__ == "__main__":
    if _support is not None:
        _support.main(WalkingOstrichDemo(), "ScrollKit walking-ostrich demo (medium)")
    else:
        asyncio.run(WalkingOstrichDemo().run())
