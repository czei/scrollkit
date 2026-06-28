"""Measure real MatrixPortal S3 timing/RAM and write the calibration fixture.

Runs a measurement routine on the connected board via the raw REPL (no files are
written to the device), parses the printed JSON, and saves it to
``test/fixtures/memory_baseline.json`` — which ``HardwareProfile.from_measurements``
then turns into a CALIBRATED profile.

Each field is measured the way the simulator's cost model *accounts* it, so the
calibration is apples-to-apples:
  - full_refresh_us        : time for one display.refresh() (populated panel)
  - bitmap_rebuild_us_per_px: per-pixel Python loop building a glyph bitmap
                              (mirrors adafruit_display_text Label._update_text)
  - gc_pause_us            : time for one gc.collect()
  - usable_ram_bytes       : gc.mem_free() after the display is set up
  - base_app_ram_bytes     : RAM consumed bringing the display up
  - bytes_per_label_px     : RAM per pixel of a 2-color bitmap

Run:  PYTHONSAFEPATH=1 python test/claude/calibrate_device.py [--board <id>]
"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cpy_repl import run_on_device  # noqa: E402

# Ship baselines inside the package so the simulator/capabilities use them by
# default (hardware_profile.profile_for() loads these paths). One file per board;
# the S3 keeps its historical filename.
CORE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "src", "scrollkit",
                        "simulator", "core")
BASELINE_FILENAMES = {
    "adafruit_matrixportal_s3": "matrixportal_s3_baseline.json",
    "pimoroni_interstate75_w": "pimoroni_interstate75_w_baseline.json",
}
BOARD_NAMES = {
    "adafruit_matrixportal_s3": "Adafruit MatrixPortal S3 (64x32)",
    "pimoroni_interstate75_w": "Pimoroni Interstate 75 W (64x32)",
}

# Per-board on-device RGBMatrix constructor (injected into DEVICE_CODE as ``_mk``).
# It must define ``def _mk(bd): return rgbmatrix.RGBMatrix(...)`` for a 64x32 panel.
MK_FUNCS = {
    "adafruit_matrixportal_s3": r"""
def _mk(bd):
    return rgbmatrix.RGBMatrix(
        width=64, height=32, bit_depth=bd,
        rgb_pins=[board.MTX_R1, board.MTX_G1, board.MTX_B1,
                  board.MTX_R2, board.MTX_G2, board.MTX_B2],
        addr_pins=[board.MTX_ADDRA, board.MTX_ADDRB, board.MTX_ADDRC, board.MTX_ADDRD],
        clock_pin=board.MTX_CLK, latch_pin=board.MTX_LAT, output_enable_pin=board.MTX_OE)
""",
    "pimoroni_interstate75_w": r"""
def _mk(bd):
    _common = getattr(board, "MTX_COMMON", None)
    _addr = getattr(board, "MTX_ADDRESS", None)
    if _common is not None and _addr is not None:
        return rgbmatrix.RGBMatrix(width=64, height=32, bit_depth=bd,
                                   addr_pins=_addr[:4], **_common)
    return rgbmatrix.RGBMatrix(
        width=64, height=32, bit_depth=bd,
        rgb_pins=[board.R0, board.G0, board.B0, board.R1, board.G1, board.B1],
        addr_pins=[board.ROW_A, board.ROW_B, board.ROW_C, board.ROW_D],
        clock_pin=board.CLK, latch_pin=board.LAT, output_enable_pin=board.OE)
""",
}

# This block runs ON the device (CircuitPython 9.x). ``___MK_DEF___`` is replaced
# with the selected board's ``_mk`` constructor before upload.
DEVICE_CODE = r"""
import gc, time, json, board, displayio, rgbmatrix, framebufferio
___MK_DEF___
displayio.release_displays()
gc.collect()
mem_boot = gc.mem_free()

# Match the library's on-hardware default: 64x32, bit_depth=4 (the speed/quality
# sweet spot; UnifiedDisplay defaults here).
matrix = _mk(4)
display = framebufferio.FramebufferDisplay(matrix, auto_refresh=False)
g = displayio.Group()
display.root_group = g

# Full-screen TileGrid so refresh() actually composites a frame.
bg = displayio.Bitmap(64, 32, 4)
for i in range(64 * 32):
    bg[i % 64, i // 64] = i % 4
pal = displayio.Palette(4)
pal[0] = 0x000000; pal[1] = 0xFF0000; pal[2] = 0x00FF00; pal[3] = 0x0000FF
g.append(displayio.TileGrid(bg, pixel_shader=pal))

gc.collect()
mem_after_display = gc.mem_free()

# --- full_refresh_us ---
display.refresh(minimum_frames_per_second=0)   # warm up
N = 30
t0 = time.monotonic_ns()
for _ in range(N):
    bg[0, 0] = (bg[0, 0] + 1) % 4              # force a recomposite
    display.refresh(minimum_frames_per_second=0)
t1 = time.monotonic_ns()
full_refresh_us = (t1 - t0) / 1000.0 / N

# --- gc_pause_us ---
junk = [bytearray(128) for _ in range(40)]
del junk
M = 20
t0 = time.monotonic_ns()
for _ in range(M):
    gc.collect()
t1 = time.monotonic_ns()
gc_pause_us = (t1 - t0) / 1000.0 / M

# --- bitmap_rebuild_us_per_px ---
# Mirror adafruit_display_text Label._update_text's inner loop: for each glyph,
# read the source glyph bitmap, test the pixel, bounds-check, write the dest.
# Normalized per destination-bitmap pixel (W*H) because the model accounts cost
# as bitmap_width * bitmap_height * us_per_px.
W, H = 60, 16
dst = displayio.Bitmap(W, H, 2)
src = displayio.Bitmap(8, 12, 2)            # one glyph-sized source
for i in range(8 * 12):
    src[i % 8, i // 8] = 1 if (i % 3 == 0) else 0   # ~1/3 lit, like a glyph
K = 12
t0 = time.monotonic_ns()
for _ in range(K):
    x_off = 0
    for _glyph in range(W // 6):            # ~10 glyphs across the line
        for gy in range(12):
            for gx in range(8):
                if src[gx, gy] > 0:
                    bx = x_off + gx
                    by = gy
                    if 0 <= bx < W and 0 <= by < H:
                        dst[bx, by] = 1
        x_off += 6
t1 = time.monotonic_ns()
bitmap_rebuild_us_per_px = (t1 - t0) / 1000.0 / (K * W * H)

# --- bytes_per_label_px ---
gc.collect(); m0 = gc.mem_free()
keep = displayio.Bitmap(64, 32, 2)
gc.collect(); m1 = gc.mem_free()
bytes_per_label_px = (m0 - m1) / float(64 * 32)
del keep; gc.collect()

print("CALIB_JSON " + json.dumps({
    "usable_ram_bytes": mem_after_display,
    "base_app_ram_bytes": max(0, mem_boot - mem_after_display),
    "bytes_per_label_px": round(bytes_per_label_px, 4),
    "full_refresh_us": round(full_refresh_us, 2),
    "bitmap_rebuild_us_per_px": round(bitmap_rebuild_us_per_px, 3),
    "gc_pause_us": round(gc_pause_us, 2),
    "_mem_boot": mem_boot,
    "_mem_after_display": mem_after_display,
}))

displayio.release_displays()
"""


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--board", default="adafruit_matrixportal_s3",
                    choices=sorted(BASELINE_FILENAMES),
                    help="which board is connected (default: %(default)s)")
    ap.add_argument("--cp", default="unknown",
                    help="CircuitPython version string for the source label")
    args = ap.parse_args()

    device_code = DEVICE_CODE.replace("___MK_DEF___", MK_FUNCS[args.board])
    out = run_on_device(device_code)
    line = next((ln for ln in out.splitlines() if ln.startswith("CALIB_JSON ")), None)
    if line is None:
        raise SystemExit("no CALIB_JSON in device output:\n" + out)
    data = json.loads(line[len("CALIB_JSON "):])

    data["name"] = BOARD_NAMES[args.board]
    data["source"] = "measured on %s, CircuitPython %s" % (args.board, args.cp)

    fixture = os.path.join(CORE_DIR, BASELINE_FILENAMES[args.board])
    os.makedirs(os.path.dirname(os.path.abspath(fixture)), exist_ok=True)
    with open(os.path.abspath(fixture), "w") as f:
        json.dump(data, f, indent=2, sort_keys=True)
        f.write("\n")

    print("Measured (%s):" % args.board)
    for k in sorted(data):
        print("  %-26s %s" % (k, data[k]))
    print("\nWrote %s" % os.path.abspath(fixture))


if __name__ == "__main__":
    main()
