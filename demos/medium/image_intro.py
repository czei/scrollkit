#!/usr/bin/env python3
"""ScrollKit demo (MEDIUM): Image-animator intros.

Shows the `scrollkit.effects.image_animators` in the context they were built for:
a full-panel picture appears, ONE part of it moves for a beat (an "attract" intro),
then the screen hands off to the actual data. The demo loops through three
image -> data scenes:

    tree      + TwinkleAnimator   -> "FIREFLIES"  (fireflies blink in the leaves)
    airplane  + MotionAnimator    -> "FLIGHT 42"  (the plane flies across)
    rocket    + ComboAnimator     -> "LIFTOFF!"   (rise + an exhaust emitter)

The data lines are kept short so they fit the 64px panel as a centred StaticText; a
real app with longer values would scroll them (ScrollingText / the characterful
scrollers) instead.

── How the display "sequence" works (the part that trips people up) ─────────────
ScrollKit has TWO ways to put things on screen:

  1. THE QUEUE (the usual one). You `self.content_queue.add(item)` in setup() and
     then RETURN. The framework's display loop pulls the current item each frame,
     renders it, and slides transitions in between — you never call show() yourself.
     Most demos (hello_world, temperature, ...) work this way.

  2. SELF-DRIVING (this demo). setup() keeps control and runs the whole animation
     itself: build a frame, `await self.display.show()`, repeat. The loop runs at
     ~20 fps; show() returns False when the simulator window closes. The splash
     demos (drip_splash, swarm_reveal) do this, and image animators need it too —
     an animator has to be `step()`-ed once per displayed frame, which only the
     self-driving style gives you.

An image animator is NOT queue content. It decorates an image LAYER you add
yourself (`display.add_layer`), following a start -> step-every-frame -> detach
contract. This demo drives that contract directly, exactly as the app's ride-intro
screen does. See docs/guide/effects.md#image-animators and docs/guide/app.md.

Run on desktop (opens a pygame window):

    PYTHONPATH=src python demos/medium/image_intro.py

The same code runs unchanged on an Adafruit MatrixPortal S3 (the BMPs just need to
be on the board's filesystem).
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
from scrollkit.display.content import StaticText
# displayio is the platform graphics module — the simulator's on desktop, the real
# one on CircuitPython. UnifiedDisplay resolves it for us; we use it to load a BMP.
from scrollkit.display.unified import displayio
from scrollkit.effects.image_animators import (
    ComboAnimator,
    EmitterAnimator,
    MotionAnimator,
    TwinkleAnimator,
    read_indexed_bmp,
)

# The subject BMPs ship next to this demo (demos/assets/animators/). Each is a
# 64x32 indexed bitmap with the transparent "sky" colour at palette slot 0.
_ART_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'animators')


def _make_rocket():
    """A ComboAnimator: the rocket rises off the top while its exhaust emits."""
    return ComboAnimator([
        MotionAnimator(path='rise', delay=30),
        EmitterAnimator(box=(29, 27, 37, 29), vx=0, vy=0.5, rate=2, life=10,
                        colors=(0xFFEE44, 0xFFAA22, 0xEE4411, 0x662211),
                        max_live=8, jitter=0.3),
    ])


# Each scene: (bmp filename, a 0-arg factory that returns a FRESH animator,
# the "data" headline shown after the intro, headline colour). A factory (not a
# shared instance) because an animator holds per-play state — you build a new one
# for each play, just like app code calls for_image() per intro.
SCENES = [
    ("tree.bmp",
     lambda: TwinkleAnimator(colors=(0x224422, 0x88AA44, 0xFFEE88), count=10,
                             box=(14, 1, 50, 19)),
     "FIREFLIES", 0x88FF88),
    ("airplane.bmp",
     lambda: MotionAnimator(path='traverse_lr', bob_amp=1),
     "FLIGHT 42", 0x66CCFF),
    ("rocket.bmp", _make_rocket, "LIFTOFF!", 0xFFCC33),
]

_HEADLINE_FRAMES = 34   # how long the data screen holds (~1.7 s at 20 fps)


class ImageIntroDemo(ScrollKitApp):

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

    # ── setup() is self-driving: it runs the whole show and never returns while
    #    the window is open (see the module docstring). ────────────────────────
    async def setup(self):
        if hasattr(self.display, "create_window"):
            await self.display.create_window("ScrollKit - Image Intro (medium)")

        while self.running:
            for bmp_name, make_animator, headline, color in SCENES:
                if not self.running:
                    return
                # 1) the animated image intro, then 2) the "data" screen.
                if await self._play_intro(bmp_name, make_animator()) is False:
                    return self._request_shutdown()
                if await self._show_headline(headline, color) is False:
                    return self._request_shutdown()

    # ------------------------------------------------------------------------
    # Phase 1 — the image intro. Mirrors the app's intro loader + step loop:
    # load the BMP as a layer, run the animator's start/step/detach contract.
    # ------------------------------------------------------------------------
    async def _play_intro(self, bmp_name, animator):
        display = self.display
        path = os.path.join(_ART_DIR, bmp_name)
        # OnDiskBitmap gives us the palette (its pixel_shader). It renders fine, but on
        # CircuitPython it is NOT subscriptable — and most animators read/rewrite image
        # pixels — so we decode the BMP into a real (writable) Bitmap with the library's
        # read_indexed_bmp(). Same call works on the simulator and the device.
        odb = displayio.OnDiskBitmap(path)              # kept alive so the palette stays valid
        palette = odb.pixel_shader
        palette.make_transparent(0)                     # slot 0 = sky -> see-through
        base_colors = _capture_base_colors(palette)     # un-faded RGB888, for the animator
        bitmap = read_indexed_bmp(display.gfx, path)    # subscriptable + writable, both platforms

        # Put the image on its OWN layer, above the (empty) content group.
        tile = displayio.TileGrid(bitmap, pixel_shader=palette)
        display.add_layer(tile)
        try:
            # start() once (build overlays / capture pixels); a raise here means the
            # animator bailed — we'd just show the still image. step() once per frame.
            animator.start(display, tile, bitmap, palette, base_colors)
            for frame in range(animator.HOLD_FRAMES):
                if not self.running:
                    break
                animator.step(frame)                    # advance the motion one frame
                if await display.show() is False:       # composite + present the layers
                    return False                        # window closed
                await asyncio.sleep(0.05)               # ~20 fps, same as the real loop
        finally:
            # detach() settles to a rest pose and frees any overlay layers the animator
            # made; then we remove the image layer so the data screen starts clean.
            try:
                animator.detach()
            except Exception:
                pass
            display.remove_layer(tile)
        return True

    # ------------------------------------------------------------------------
    # Phase 2 — the "data" screen. A plain centred label, held for a beat. In a
    # real app this is where live values go (wait times, prices, weather); scroll
    # them with ScrollingText or the characterful scrollers instead of a StaticText.
    # ------------------------------------------------------------------------
    async def _show_headline(self, text, color):
        display = self.display
        x = max(0, (display.width - display.measure_text(text)) // 2)
        item = StaticText(text, x=x, y=12, color=color)
        await item.start()
        try:
            for _ in range(_HEADLINE_FRAMES):
                if not self.running:
                    break
                await display.clear()                   # empties the content group
                await item.render(display)
                if await display.show() is False:
                    return False
                await asyncio.sleep(0.05)
        finally:
            await display.clear()
        return True


def _capture_base_colors(palette):
    """The palette's original colours as 0xRRGGBB ints (before any fading).

    CircuitPython's Palette[i] is already RGB888; the simulator stores RGB565 and
    exposes the true colour via get_rgb888(), so an animator that scales brightness
    (e.g. PalettePulse) stays correct on both.
    """
    get888 = getattr(palette, "get_rgb888", None)
    if get888 is not None:
        return [(int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2])
                for c in (get888(i) for i in range(len(palette)))]
    return [palette[i] for i in range(len(palette))]


if __name__ == "__main__":
    if _support is not None:
        _support.main(ImageIntroDemo(), "ScrollKit image-intro demo (medium)")
    else:
        asyncio.run(ImageIntroDemo().run())
