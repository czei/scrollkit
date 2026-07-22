#!/usr/bin/env python3
"""ScrollKit demo (MEDIUM): tilt the box and the picture falls over.

The Adafruit MatrixPortal S3 has an onboard LIS3DH accelerometer, so a sign built
on one knows which way is down. This demo wires that to
``GravityDripAnimator``: the image sits still while the panel hangs normally, and
the moment you turn the box the pixels let go and pour toward whichever edge is
now the floor. Keep turning it mid-fall and the pile changes direction with you.

    still  --(the box is turned)-->  dripping  --(pile settles)-->  settled
      ^                                                               |
      +--------------------(the box is upright again)-----------------+

On the desktop there is nothing to tilt, so the simulator carries a VIRTUAL
accelerometer you steer from the keyboard — the identical ``TiltSensor`` API the
device uses, so this demo is written once and runs unchanged on both:

    left / right arrow  swing gravity 15 degrees
    down arrow          snap back upright
    up arrow            lay the panel flat on its back (no "down" at all)
    esc                 quit

Run on desktop (opens a pygame window):

    PYTHONPATH=src python demos/medium/tilt_drip.py

On a MatrixPortal S3 it just works — ``TiltSensor`` finds the real chip at I2C
address 0x19 (NOT the 0x18 Adafruit's own libraries default to) and reports the
same panel-space angles. On a board with no accelerometer, such as the Pimoroni
Interstate 75 W, the sensor reports ``available == False`` and this demo falls
back to dripping on a timer rather than refusing to run.
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
from scrollkit.effects.image_animators import GravityDripAnimator, read_indexed_bmp
from scrollkit.sensors.tilt import TiltSensor

_ART_DIR = os.path.join(os.path.dirname(__file__), '..', 'assets', 'animators')
_IMAGE = "light_bulb.bmp"        # 339 lit px — inside the animator's 400 budget

_SETTLED_HOLD = 40               # frames the finished pile holds (~2 s at 20 fps)
_AUTO_DRIP_AFTER = 60            # frames before an accelerometer-less board drips


class TiltDripDemo(ScrollKitApp):
    """Self-driving demo: it owns the frame loop so the animator can be stepped.

    An image animator is not queue content — it decorates a layer you add
    yourself and must be ``step()``-ed once per displayed frame, which only the
    self-driving style allows. See ``demos/medium/image_intro.py``.
    """

    def __init__(self):
        super().__init__(enable_web=False, update_interval=30)
        self.tilt = None

    async def create_display(self):
        if _support is not None:
            return _support.simulator_display(getattr(self, "opts", None))
        try:
            from scrollkit.display.simulator import SimulatorDisplay
            return SimulatorDisplay(width=64, height=32)
        except ImportError:
            return await super().create_display()

    async def setup(self):
        if hasattr(self.display, "create_window"):
            await self.display.create_window("ScrollKit - Tilt Drip (medium)")

        # One sensor for the life of the app. Passing the display lets it find the
        # board (so it knows whether there IS an accelerometer, and at what
        # address) and, on desktop, the simulator's virtual gravity vector.
        self.tilt = TiltSensor(self.display)
        print("tilt: available=%s source=%s board=%s"
              % (self.tilt.available, self.tilt.source, self.tilt.board_id))

        while self.running:
            if await self._scene() is False:
                return self._request_shutdown()

    async def _scene(self):
        """One full still -> drip -> settle -> reset cycle."""
        display = self.display
        path = os.path.join(_ART_DIR, _IMAGE)
        # OnDiskBitmap supplies the palette but is not subscriptable on
        # CircuitPython, and the animator reads image pixels — so decode into a
        # real writable Bitmap. Same call on the simulator and the device.
        odb = displayio.OnDiskBitmap(path)
        palette = odb.pixel_shader
        palette.make_transparent(0)
        base_colors = _capture_base_colors(palette)
        bitmap = read_indexed_bmp(display.gfx, path)

        tile = displayio.TileGrid(bitmap, pixel_shader=palette)
        display.add_layer(tile)

        animator = None
        state = "still"
        frame = 0
        held = 0
        try:
            while self.running:
                edge = self._down_edge()

                if state == "still":
                    # Turning the box is the trigger. A board with no
                    # accelerometer never reports a turn, so fall back to a timer
                    # rather than sitting inert forever.
                    triggered = (edge is not None and edge != "bottom") or (
                        not self.tilt.available and frame > _AUTO_DRIP_AFTER)
                    if triggered:
                        animator = GravityDripAnimator(edge=edge or "right")
                        try:
                            animator.start(display, tile, bitmap, palette,
                                           base_colors)
                            state = "dripping"
                            frame = 0
                        except ValueError as e:
                            # The host contract: a refused animator means keep
                            # showing the still image, never a blank panel.
                            print("drip declined:", e)
                            animator = None

                elif state == "dripping":
                    if edge is not None:
                        animator.set_gravity(edge=edge)   # follow the box, live
                    animator.step(frame)
                    if animator.is_complete:
                        state = "settled"
                        held = 0

                elif state == "settled":
                    held += 1
                    # Standing it back up (or, with no sensor, waiting a beat)
                    # rebuilds the scene from scratch.
                    if (edge == "bottom" and held > 5) or (
                            not self.tilt.available and held > _SETTLED_HOLD):
                        return True

                await display.clear()                    # content group only; layers persist
                await self._draw_readout()
                if await display.show() is False:
                    return False
                await asyncio.sleep(0.05)                # ~20 fps, the real loop's rate
                frame += 1
        finally:
            if animator is not None:
                try:
                    animator.detach()
                except Exception:
                    pass
            display.remove_layer(tile)
            await display.clear()
        return True

    def _down_edge(self):
        """Which panel edge is down, or None when there's no usable reading."""
        if not self.tilt.available:
            return None
        self.tilt.read()                                 # throttled internally
        edge = self.tilt.orientation
        return None if edge == "flat" else edge

    async def _draw_readout(self):
        """A one-line corner readout of what the sensor currently believes."""
        if not self.tilt.available:
            return
        label = "%s %d" % (self.tilt.orientation[:1].upper(),
                           int(self.tilt.gravity_angle))
        await self.display.draw_text(label, x=1, y=3, color=0x224466)


def _capture_base_colors(palette):
    """The palette's original colours as 0xRRGGBB ints (before any fading).

    The simulator stores RGB565 and exposes the true colour via ``get_rgb888``;
    the device palette is already RGB888. Same helper as image_intro.py.
    """
    get888 = getattr(palette, "get_rgb888", None)
    if get888 is not None:
        return [(int(c[0]) << 16) | (int(c[1]) << 8) | int(c[2])
                for c in (get888(i) for i in range(len(palette)))]
    return [palette[i] for i in range(len(palette))]


if __name__ == "__main__":
    if _support is not None:
        _support.main(TiltDripDemo(), "ScrollKit tilt-drip demo (medium)")
    else:
        asyncio.run(TiltDripDemo().run())
