"""Phase-0 spike: render a real ScrollKit frame to a canvas-ready buffer, NO pygame.

Proves the core architectural assumption behind ScrollKit Studio (the browser app):
the real library can rasterize text into the `(H, W, 3)` uint8 RGB pixel buffer using
only pure-Python + numpy — the exact two things Pyodide ships — so it can run in the
browser and hand that buffer straight to an HTML canvas via putImageData.

How the proof is made airtight:
  1. A meta-path finder BLOCKS any `import pygame` and raises. If the headless render
     path touched pygame, this script would crash. It doesn't.
  2. SCROLLKIT_HEADLESS=1 puts LEDMatrix in headless mode (skip the window surface).
  3. We drive the *real* SimulatorDisplay API (clear/draw_text) and the *real*
     displayio refresh, then read the buffer the same way the dev metrics do.

Run:  PYTHONSAFEPATH=1 PYTHONPATH=src SCROLLKIT_HEADLESS=1 python test/claude/spike_pyodide_render.py
"""

import os
import sys

# --- 1) Forbid pygame, to prove the headless render path never needs it ---------
class _BlockPygame:
    def find_spec(self, name, path=None, target=None):
        if name == "pygame" or name.startswith("pygame."):
            raise ImportError(
                "pygame import BLOCKED by the spike: the headless render path must "
                "not need pygame (this is the whole point of the Pyodide proof)."
            )
        return None

sys.meta_path.insert(0, _BlockPygame())
os.environ["SCROLLKIT_HEADLESS"] = "1"

import asyncio
import numpy as np

from scrollkit.display.simulator import SimulatorDisplay
from scrollkit.dev.metrics import buffer_from_display, lit_pixels, coverage, signature

MESSAGE = "HELLO SCROLLKIT"
WIDTH, HEIGHT = 64, 32
COLOR = 0x00AAFF
OUT_DIR = os.path.join(os.path.dirname(__file__), "spike_out")


def ascii_preview(buf):
    """Tiny terminal preview: '#' for lit pixels, '.' for dark."""
    lit = np.any(buf > 0, axis=2)
    return "\n".join("".join("#" if lit[y, x] else "." for x in range(buf.shape[1]))
                     for y in range(buf.shape[0]))


def save_png(buf, path, scale=10):
    """Save the buffer as a PNG via Pillow (NOT pygame), upscaled for viewing."""
    from PIL import Image
    img = Image.fromarray(buf, "RGB").resize(
        (buf.shape[1] * scale, buf.shape[0] * scale), Image.NEAREST)
    img.save(path)


async def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    display = SimulatorDisplay(width=WIDTH, height=HEIGHT)
    await display.initialize()

    # Scroll the message right-to-left; capture the buffer at several offsets.
    frames = []
    offsets = list(range(WIDTH, -90, -8))   # 64 -> off the left edge
    for i, x in enumerate(offsets):
        await display.clear()
        await display.draw_text(MESSAGE, x=x, y=16, color=COLOR)
        # The real displayio rasterize step: group -> pixel buffer (headless matrix).
        display.display.refresh(minimum_frames_per_second=0)
        buf = buffer_from_display(display).copy()
        frames.append(buf)
        if i in (0, len(offsets) // 2, len(offsets) - 1):
            save_png(buf, os.path.join(OUT_DIR, f"frame_{i:02d}_x{x}.png"))

    # --- Assertions: the proof -------------------------------------------------
    mid = frames[len(frames) // 2]
    assert "pygame" not in sys.modules, "FAIL: pygame got imported"
    assert buffer_from_display(display) is not None, "FAIL: no pixel buffer"
    assert mid.shape == (HEIGHT, WIDTH, 3) and mid.dtype == np.uint8, "FAIL: buffer shape/dtype"
    assert lit_pixels(mid) > 0, "FAIL: nothing rendered (blank frame)"
    sigs = {signature(f) for f in frames}
    assert len(sigs) > 1, "FAIL: frames identical (no motion)"

    # --- Report ----------------------------------------------------------------
    print("=" * 64)
    print("PHASE-0 SPIKE: real ScrollKit frame -> canvas-ready buffer, NO pygame")
    print("=" * 64)
    print(f"pygame imported?          {'pygame' in sys.modules}  (blocked at import)")
    print(f"buffer shape / dtype:     {mid.shape} {mid.dtype}  (canvas ImageData-ready)")
    print(f"lit pixels (mid frame):   {lit_pixels(mid)}")
    print(f"coverage (mid frame):     {coverage(mid):.3f}")
    print(f"distinct frame sigs:      {len(sigs)} / {len(frames)}  (motion confirmed)")
    print(f"PNGs written to:          {OUT_DIR}")
    print()
    print("Mid-frame preview (logical 64x32 buffer):")
    print(ascii_preview(mid))
    print()
    print("RESULT: PASS — pure-Python + numpy render path is Pyodide-viable.")


if __name__ == "__main__":
    asyncio.run(main())
