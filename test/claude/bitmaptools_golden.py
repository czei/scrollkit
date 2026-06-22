"""Host-side capture of the bitmaptools golden corpus from a real board.

MANUAL / OPTIONAL CALIBRATION — this is NOT part of the test suite. It runs the
same battery the shim conformance test replays, but on a real MatrixPortal S3 via
the raw-REPL driver (``test/claude/cpy_repl.py``, which writes nothing to the
board's filesystem), and emits ``test/unit/display/bitmaptools_golden.json``.

Use it to (re)capture the authoritative golden after a CircuitPython upgrade, then
re-run ``test/unit/display/test_bitmaptools_shim.py``. The committed JSON is the
CI fixture; the simulator shim is fixed to match it, never the reverse.

    python test/claude/bitmaptools_golden.py [--port /dev/tty.usbmodemXXXX]
"""

import argparse
import json
import os
import sys

# The battery runs on the DEVICE with the real bitmaptools; it mirrors the cases
# in test/unit/display/test_bitmaptools_shim.py exactly.
DEVICE_CODE = r'''
import bitmaptools, displayio, json
W, H, VC = 8, 4, 16

def fresh():
    return displayio.Bitmap(W, H, VC)

def buf(b):
    return [[b[x, y] for x in range(W)] for y in range(H)]

def src(rows):
    h = len(rows); w = len(rows[0])
    b = displayio.Bitmap(w, h, VC)
    for y in range(h):
        for x in range(w):
            b[x, y] = rows[y][x]
    return b

out = {}
b = fresh(); bitmaptools.fill_region(b, 1, 1, 4, 3, 5); out["fill_region_basic"] = buf(b)
b = fresh(); bitmaptools.fill_region(b, 6, 0, 20, 2, 7); out["fill_region_clip_right"] = buf(b)
b = fresh(); bitmaptools.fill_region(b, -3, -1, 2, 2, 9); out["fill_region_negative"] = buf(b)
b = fresh(); bitmaptools.fill_region(b, 3, 3, 3, 5, 4); out["fill_region_empty"] = buf(b)
b = fresh(); bitmaptools.fill_region(b, 4, 0, 1, 2, 5); out["fill_region_inverted"] = buf(b)
b = fresh(); bitmaptools.fill_region(b, 0, 0, 8, 4, 2); out["fill_region_full"] = buf(b)
b = fresh(); bitmaptools.blit(b, src([[1, 2], [3, 4]]), 3, 1); out["blit_basic"] = buf(b)
b = fresh(); bitmaptools.blit(b, src([[0, 2], [3, 0]]), 1, 0, skip_index=0); out["blit_skip_index"] = buf(b)
b = fresh(); bitmaptools.blit(b, src([[1, 2], [3, 4]]), -1, -1); out["blit_clip_negative"] = buf(b)
print("GOLDEN:" + json.dumps(out))
'''

GOLDEN_PATH = os.path.join(
    os.path.dirname(__file__), "..", "unit", "display", "bitmaptools_golden.json")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", default=None, help="serial port of the board")
    args = ap.parse_args()

    sys.path.insert(0, os.path.dirname(__file__))
    from cpy_repl import run_on_device  # noqa: E402

    kwargs = {"port": args.port} if args.port else {}
    output = run_on_device(DEVICE_CODE, **kwargs)
    line = next((ln for ln in output.splitlines() if ln.startswith("GOLDEN:")), None)
    if line is None:
        raise SystemExit("device did not emit GOLDEN: line. Raw output:\n" + output)
    captured = json.loads(line[len("GOLDEN:"):])

    doc = {
        "_doc": ("Golden expected outputs for the bitmaptools battery, on a fresh "
                 "8x4 value_count=16 bitmap (rows of x-values, _buffer[y][x]). "
                 "Captured on a real board by test/claude/bitmaptools_golden.py."),
        "_bitmap": {"width": 8, "height": 4, "value_count": 16},
    }
    doc.update(captured)
    with open(os.path.normpath(GOLDEN_PATH), "w") as f:
        json.dump(doc, f, indent=2)
        f.write("\n")
    print("wrote", os.path.normpath(GOLDEN_PATH))


if __name__ == "__main__":
    main()
