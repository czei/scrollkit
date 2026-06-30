"""On-hardware check: gradient text baseline alignment for the device font.

The device's terminalio is a FULL-CELL BuiltinFont (every glyph a 6x12 tile,
height=12, dy=0, no .ascent) whose baseline is buried in the cell — so the
trimmed-BDF simulator can't reproduce its placement. This sends the repo's (pure)
``text_pixels.py`` to a connected MatrixPortal S3, then computes where gradient
ride names would land and asserts NOTHING clips off the top of the panel.

    PYTHONPATH=src python test/claude/verify_font_baseline.py

Needs a board on USB serial (uses the raw-REPL driver ``cpy_repl.py``; writes
nothing to the device). Exits non-zero if any name would clip.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cpy_repl import run_on_device  # noqa: E402

_HERE = os.path.dirname(__file__)
_TEXT_PIXELS = os.path.join(_HERE, "..", "..", "src", "scrollkit", "display",
                            "text_pixels.py")

# Sample park / ride names: ALL-CAPS, mixed-case, and descender-heavy.
_PROBE = r'''

import terminalio
F = terminalio.FONT
NAME_Y = 5            # app top-zone y
BASELINE_DROP = 4     # gradient_text._BASELINE_DROP
NAMES = ("MAGIC KINGDOM", "Space Mountain", "Jungle Cruise",
         "Big Thunder Mountain", "Tower of Terror", "gyp")
worst = 99
for txt in NAMES:
    asc = font_text_ascent(F, txt)
    ys = [p[1] for p in pixels_from_font_text(F, txt, 0, 0)]
    tiley = NAME_Y + BASELINE_DROP - asc
    top = tiley + min(ys)
    worst = min(worst, top)
    print("%-22r ascent %d  tile.y %d  top_screen_row %d" % (txt, asc, tiley, top))
print("RESULT", "OK" if worst >= 0 else "CLIP", "worst_top_row", worst)
'''


def main():
    with open(_TEXT_PIXELS) as fh:
        out = run_on_device(fh.read() + _PROBE)
    print(out)
    if "RESULT OK" not in out:
        print("FAILED: gradient text would clip the top of the panel")
        sys.exit(1)
    print("PASSED: no top clipping on the device font")


if __name__ == "__main__":
    main()
