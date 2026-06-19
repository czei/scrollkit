"""CircuitPython microbenchmark suite for the MatrixPortal S3.

Measures many distinct operations *separately* so the cost of each library call
is visible on its own — the key being that interpreted-Python work (per-pixel
loops, arithmetic) is ~10-100x slower than the C-backed bulk calls
(``bitmap.fill``, ``bitmaptools.blit``, ``display.refresh``). A single fudge
factor can't capture that; a per-operation table can.

Runs on the device over the raw REPL (no files written to it). Each benchmark
warms up, times an explicit loop with ``time.monotonic_ns()``, and subtracts the
empty-loop overhead so the number is the marginal cost of the op. Results are
printed as one JSON line and saved to test/fixtures/device_benchmarks.json.

Run:  PYTHONSAFEPATH=1 python test/claude/device_benchmarks.py
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from cpy_repl import run_on_device  # noqa: E402

# Ship the measured table inside the package so dev.performance_guide() can load
# it (single source of truth, alongside the calibration baseline).
OUT = os.path.join(os.path.dirname(__file__), "..", "..", "src", "scrollkit",
                   "simulator", "core", "device_benchmarks.json")

DEVICE_CODE = r'''
import time, gc, json, displayio, board, rgbmatrix, framebufferio
try:
    import bitmaptools
except ImportError:
    bitmaptools = None

res = []
def rec(name, cat, per_ns, iters, unit="ns/op", note=""):
    res.append({"name": name, "category": cat, "unit": unit,
                "value": round(per_ns, 2), "iters": iters, "note": note})

gc.collect()

# ---- compute baseline: empty for-loop iteration cost ----
N = 20000
t0 = time.monotonic_ns()
for _ in range(N):
    pass
t1 = time.monotonic_ns()
base = (t1 - t0) / N
rec("noop_loop_iter", "compute", base, N, note="for-loop overhead (subtracted below)")

def net(name, cat, dt_ns, iters, unit="ns/op", note=""):
    rec(name, cat, dt_ns / iters - base, iters, unit, note)

# ---- interpreted compute ----
N = 20000; x = 1
t0 = time.monotonic_ns()
for _ in range(N):
    x = x + 1
t1 = time.monotonic_ns(); net("int_add", "compute", t1 - t0, N)

N = 20000; v = 0
t0 = time.monotonic_ns()
for i in range(N):
    v = i * 3                # loop index, stays a small int (no bignum growth)
t1 = time.monotonic_ns(); net("int_mul", "compute", t1 - t0, N)

N = 20000; f = 1.0
t0 = time.monotonic_ns()
for _ in range(N):
    f = f + 1.5
t1 = time.monotonic_ns(); net("float_add", "compute", t1 - t0, N)

N = 20000; f = 1.0
t0 = time.monotonic_ns()
for _ in range(N):
    f = f * 1.001
t1 = time.monotonic_ns(); net("float_mul", "compute", t1 - t0, N)

a = list(range(64)); N = 20000; v = 0
t0 = time.monotonic_ns()
for i in range(N):
    v = a[i & 63]
t1 = time.monotonic_ns(); net("list_index", "compute", t1 - t0, N)

d = {"a": 1, "b": 2, "c": 3}; N = 20000; v = 0
t0 = time.monotonic_ns()
for _ in range(N):
    v = d["b"]
t1 = time.monotonic_ns(); net("dict_get", "compute", t1 - t0, N)

def f0():
    return 1
N = 20000; v = 0
t0 = time.monotonic_ns()
for _ in range(N):
    v = f0()
t1 = time.monotonic_ns(); net("func_call", "compute", t1 - t0, N)

class _C:
    def __init__(self):
        self.v = 1
_o = _C(); N = 20000; v = 0
t0 = time.monotonic_ns()
for _ in range(N):
    v = _o.v
t1 = time.monotonic_ns(); net("attr_access", "compute", t1 - t0, N)

# ---- interpreted pixel access (the slow path) ----
bmp = displayio.Bitmap(64, 32, 2)
N = 10000
t0 = time.monotonic_ns()
for i in range(N):
    bmp[i & 63, (i >> 6) & 31] = 1
t1 = time.monotonic_ns(); net("bitmap_setpixel", "pixel_interpreted", t1 - t0, N,
                              note="bmp[x,y]=1")

N = 10000; v = 0
t0 = time.monotonic_ns()
for i in range(N):
    v = bmp[i & 63, (i >> 6) & 31]
t1 = time.monotonic_ns(); net("bitmap_getpixel", "pixel_interpreted", t1 - t0, N)

# ---- C bulk bitmap ops (the fast path) ----
N = 4000
t0 = time.monotonic_ns()
for _ in range(N):
    bmp.fill(1)
t1 = time.monotonic_ns()
rec("bitmap_fill_64x32", "bulk_c", (t1 - t0) / N, N, "ns/call", "C fill 2048 px")

if bitmaptools:
    src = displayio.Bitmap(16, 16, 2)
    for i in range(16 * 16):
        src[i & 15, i >> 4] = i & 1
    dst = displayio.Bitmap(64, 32, 2)
    N = 4000
    t0 = time.monotonic_ns()
    for _ in range(N):
        bitmaptools.blit(dst, src, 8, 8)
    t1 = time.monotonic_ns()
    rec("bitmaptools_blit_16x16", "bulk_c", (t1 - t0) / N, N, "ns/call", "C blit 256 px")
    try:
        N = 4000
        t0 = time.monotonic_ns()
        for _ in range(N):
            bitmaptools.fill_region(dst, 0, 0, 32, 16, 1)
        t1 = time.monotonic_ns()
        rec("bitmaptools_fill_region", "bulk_c", (t1 - t0) / N, N, "ns/call", "512 px")
    except (AttributeError, TypeError):
        rec("bitmaptools_fill_region", "bulk_c", 0, 0, note="unavailable")
    try:
        N = 4000
        t0 = time.monotonic_ns()
        for _ in range(N):
            bitmaptools.draw_line(dst, 0, 0, 63, 31, 1)
        t1 = time.monotonic_ns()
        rec("bitmaptools_draw_line", "bulk_c", (t1 - t0) / N, N, "ns/call")
    except (AttributeError, TypeError):
        rec("bitmaptools_draw_line", "bulk_c", 0, 0, note="unavailable")
else:
    rec("bitmaptools", "bulk_c", 0, 0, note="module unavailable")

# ---- display object ops ----
pal = displayio.Palette(4)
N = 10000
t0 = time.monotonic_ns()
for i in range(N):
    pal[i & 3] = 0xFF00FF
t1 = time.monotonic_ns(); net("palette_set", "display_obj", t1 - t0, N)

N = 500
t0 = time.monotonic_ns()
for _ in range(N):
    _tg = displayio.TileGrid(bmp, pixel_shader=pal)
t1 = time.monotonic_ns()
rec("tilegrid_create", "display_obj", (t1 - t0) / N, N, "ns/call", "alloc+init")

tgm = displayio.TileGrid(bmp, pixel_shader=pal)
N = 10000
t0 = time.monotonic_ns()
for i in range(N):
    tgm.x = i & 63
t1 = time.monotonic_ns(); net("tilegrid_move_x", "display_obj", t1 - t0, N)

g2 = displayio.Group()
N = 3000
t0 = time.monotonic_ns()
for _ in range(N):
    g2.append(tgm); g2.pop()
t1 = time.monotonic_ns()
rec("group_append_pop_pair", "display_obj", (t1 - t0) / N, N, "ns/pair")

# ---- memory ----
N = 1000
t0 = time.monotonic_ns()
for _ in range(N):
    _b = displayio.Bitmap(32, 16, 2)
t1 = time.monotonic_ns()
rec("bitmap_alloc_32x16", "memory", (t1 - t0) / N, N, "ns/alloc")

N = 2000
t0 = time.monotonic_ns()
for _ in range(N):
    _ba = bytearray(256)
t1 = time.monotonic_ns()
rec("bytearray_alloc_256", "memory", (t1 - t0) / N, N, "ns/alloc")

gc.collect()
N = 30
t0 = time.monotonic_ns()
for _ in range(N):
    gc.collect()
t1 = time.monotonic_ns()
rec("gc_collect", "memory", (t1 - t0) / N, N, "ns/call", "clean heap")

# ---- call overhead ----
N = 10000
t0 = time.monotonic_ns()
for _ in range(N):
    _t = time.monotonic_ns()
t1 = time.monotonic_ns(); net("monotonic_ns_call", "io", t1 - t0, N)

# ---- display.refresh() at each bit depth ----
for bd in (1, 2, 4, 6):
    displayio.release_displays()
    mm = rgbmatrix.RGBMatrix(
        width=64, height=32, bit_depth=bd,
        rgb_pins=[board.MTX_R1, board.MTX_G1, board.MTX_B1,
                  board.MTX_R2, board.MTX_G2, board.MTX_B2],
        addr_pins=[board.MTX_ADDRA, board.MTX_ADDRB, board.MTX_ADDRC, board.MTX_ADDRD],
        clock_pin=board.MTX_CLK, latch_pin=board.MTX_LAT, output_enable_pin=board.MTX_OE)
    dd = framebufferio.FramebufferDisplay(mm, auto_refresh=False)
    gg = displayio.Group(); dd.root_group = gg
    # empty refresh
    dd.refresh(minimum_frames_per_second=0)
    N = 30
    t0 = time.monotonic_ns()
    for _ in range(N):
        dd.refresh(minimum_frames_per_second=0)
    t1 = time.monotonic_ns()
    rec("refresh_empty_bd%d" % bd, "refresh", (t1 - t0) / N, N, "ns/call",
        "bit_depth=%d, empty group" % bd)
    # full-screen recomposite refresh
    bb = displayio.Bitmap(64, 32, 4)
    bp = displayio.Palette(4)
    bp[0] = 0x000000; bp[1] = 0xFF0000; bp[2] = 0x00FF00; bp[3] = 0x0000FF
    gg.append(displayio.TileGrid(bb, pixel_shader=bp))
    dd.refresh(minimum_frames_per_second=0)
    N = 30
    t0 = time.monotonic_ns()
    for k in range(N):
        bb[0, 0] = k & 3
        dd.refresh(minimum_frames_per_second=0)
    t1 = time.monotonic_ns()
    rec("refresh_full_bd%d" % bd, "refresh", (t1 - t0) / N, N, "ns/call",
        "bit_depth=%d, 64x32 recomposite" % bd)
displayio.release_displays()

print("BENCH_JSON " + json.dumps(res))
'''


def main():
    out = run_on_device(DEVICE_CODE, exec_timeout=180.0)
    line = next((ln for ln in out.splitlines() if ln.startswith("BENCH_JSON ")), None)
    if line is None:
        raise SystemExit("no BENCH_JSON in device output:\n" + out)
    rows = json.loads(line[len("BENCH_JSON "):])

    os.makedirs(os.path.dirname(os.path.abspath(OUT)), exist_ok=True)
    with open(os.path.abspath(OUT), "w") as f:
        json.dump({"board": "adafruit_matrixportal_s3", "cp": "9.1.0",
                   "benchmarks": rows}, f, indent=2)
        f.write("\n")

    # Pretty table grouped by category.
    cats = {}
    for r in rows:
        cats.setdefault(r["category"], []).append(r)
    order = ["compute", "pixel_interpreted", "bulk_c", "display_obj",
             "memory", "io", "refresh"]
    print("%-28s %-12s %12s  %s" % ("operation", "category", "value", "unit"))
    print("-" * 72)
    for cat in order + [c for c in cats if c not in order]:
        for r in sorted(cats.get(cat, []), key=lambda r: r["value"]):
            val = "%.2f" % r["value"] if r["iters"] else "n/a"
            note = ("  # " + r["note"]) if r["note"] else ""
            print("%-28s %-12s %12s  %-7s%s"
                  % (r["name"], r["category"], val, r["unit"], note))
    print("\nSaved %s" % os.path.abspath(OUT))


if __name__ == "__main__":
    main()
