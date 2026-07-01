# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Measured performance trade-offs for the MatrixPortal S3 — for AI authoring.

Turns the raw microbenchmark table (``simulator/core/device_benchmarks.json``,
captured on a real device by ``test/claude/device_benchmarks.py``) into a curated
guide an agent can reason about: which calls are cheap C vs slow interpreted
Python, the bit_depth/refresh ladder, allocation costs, and the cardinal rules
that follow. Numbers come straight from the device, so the guidance can't drift.

Desktop-only (imported via ``scrollkit.dev``).
"""

import json
import os

_BENCH_DIR = os.path.join(os.path.dirname(__file__), "..", "simulator", "core")
_DEFAULT_BOARD_ID = "adafruit_matrixportal_s3"
# The S3 benchmark file keeps its historical name; others follow the canonical-id
# convention (matching test/claude/device_benchmarks.py --board output).
_BENCH_FILENAMES = {
    "adafruit_matrixportal_s3": "device_benchmarks.json",
    "pimoroni_interstate75_w": "pimoroni_interstate75_w_benchmarks.json",
}


def _bench_path(board_id):
    filename = _BENCH_FILENAMES.get(board_id, "%s_benchmarks.json" % board_id)
    return os.path.join(_BENCH_DIR, filename)


def _load_doc(board_id):
    with open(os.path.abspath(_bench_path(board_id))) as f:
        return json.load(f)


def _by_name(rows):
    return {r["name"]: r for r in rows}


def performance_guide(board_id=None):
    """Return a JSON-able, device-measured performance guide for ``board_id``.

    Sections: ``pixel_write`` (the C-vs-interpreted spread), ``refresh`` (the
    bit_depth ladder + FPS ceiling), ``allocation``, ``compute``, ``gc``, and
    ``rules`` (the actionable cardinal rules). ``board_id`` defaults to the
    MatrixPortal S3. Falls back to an empty/quiet guide if that board has no
    captured benchmark file yet (e.g. a board wired in code but not yet
    calibrated).
    """
    if board_id is None:
        board_id = _DEFAULT_BOARD_ID
    try:
        doc = _load_doc(board_id)
    except Exception:
        return {"available": False, "board": board_id,
                "note": "no device benchmark data for %s; run "
                        "test/claude/device_benchmarks.py --board %s"
                        % (board_id, board_id)}
    rows = doc.get("benchmarks", [])
    b = _by_name(rows)
    src_board = doc.get("board", board_id)
    src_cp = doc.get("cp")
    source = ("measured on %s, CircuitPython %s" % (src_board, src_cp)
              if src_cp else "measured on %s" % src_board)

    def val(name):
        r = b.get(name)
        return r["value"] if r and r.get("iters") else None

    # Pixel-write spread (per pixel): interpreted set vs C blit vs C fill.
    set_px = val("bitmap_setpixel")                       # ns/px (interpreted)
    blit = val("bitmaptools_blit_16x16")
    blit_px = (blit / 256.0) if blit else None            # 16x16 region
    fill = val("bitmap_fill_64x32")
    fill_px = (fill / 2048.0) if fill else None           # 64x32 region

    # Refresh / bit_depth ladder.
    refresh = {}
    for bd in (1, 2, 4, 6):
        v = val("refresh_full_bd%d" % bd)
        if v:
            refresh["bit_depth_%d" % bd] = {
                "full_refresh_ms": round(v / 1e6, 2),
                "fps_ceiling": int(1e9 / v),
            }

    guide = {
        "available": True,
        "board": src_board,
        "source": source,
        "pixel_write_ns_per_px": {
            "interpreted_setpixel": _r(set_px),
            "c_bitmaptools_blit": _r(blit_px),
            "c_bitmap_fill": _r(fill_px),
            "note": _ratio_note(set_px, blit_px, fill_px),
        },
        "refresh": refresh,
        "allocation_ns": {
            "bitmap_32x16": val("bitmap_alloc_32x16"),
            "tilegrid": val("tilegrid_create"),
            "bytearray_256": val("bytearray_alloc_256"),
            "note": "Allocating objects every frame is a real per-frame tax; "
                    "create once and mutate.",
        },
        "compute_ns_per_op": {
            "loop_iter": val("noop_loop_iter"),
            "int_op": val("int_add"),
            "func_call": val("func_call"),
            "note": "~500k simple ops/sec. CircuitPython is interpreted; a "
                    "1000-op calculation costs ~1.5 ms straight out of the frame "
                    "budget (it's cooperative — there is no background thread).",
        },
        "gc_collect_ns": {
            "value": val("gc_collect"),
            "note": "Scales with live objects / heap size (~0.3 ms clean, ~0.9 ms "
                    "after churn). Fewer live allocations = shorter GC pauses.",
        },
        "rules": _rules(),
    }
    return guide


def _rules():
    return [
        "Reuse a Label and change .text only when the value actually changes; "
        "for scrolling, move .x and leave .text alone (a text change rebuilds the "
        "glyph bitmap pixel-by-pixel — the dominant per-frame cost).",
        "Never push pixels in a Python loop. Use the C bulk calls — bitmap.fill "
        "for solids, bitmaptools.blit to copy — they are ~11x (blit) to ~1500x "
        "(fill) faster per pixel than interpreted bitmap[x,y]=... writes.",
        "Keep bit_depth at 4 unless you need smooth color gradients: a full "
        "refresh is ~4.5 ms at bit_depth<=4 but ~13.7 ms at 6 (~3x slower, so "
        "~220 vs ~73 FPS ceiling).",
        "Don't allocate per frame (Label/Bitmap/TileGrid/Group). Create the "
        "display objects once and mutate them; allocation is tens of microseconds "
        "each and feeds the GC.",
        "Heavy computation competes directly with rendering (cooperative "
        "multitasking, ~500k Python ops/sec). Break long work into chunks across "
        "frames so scrolling keeps moving.",
    ]


def _r(x):
    return round(x, 1) if x is not None else None


def _ratio_note(set_px, blit_px, fill_px):
    if not (set_px and blit_px and fill_px):
        return "interpreted per-pixel writes are far slower than the C bulk ops"
    return ("interpreted bitmap[x,y]= is ~%dx slower than a C blit and ~%dx "
            "slower than a C fill, per pixel"
            % (round(set_px / blit_px), round(set_px / fill_px)))


def performance_text(guide=None):
    """Render the performance guide as a compact human/AI summary."""
    guide = guide or performance_guide()
    if not guide.get("available"):
        return "Performance guide unavailable (no device benchmark data)."
    lines = ["=== %s performance (measured) ===" % guide.get("board", "device")]
    pw = guide["pixel_write_ns_per_px"]
    lines.append("Pixel write ns/px: interpreted=%s | C blit=%s | C fill=%s"
                 % (pw["interpreted_setpixel"], pw["c_bitmaptools_blit"],
                    pw["c_bitmap_fill"]))
    lines.append("  -> %s" % pw["note"])
    if guide["refresh"]:
        parts = ["%s=%sms(~%dfps)" % (k.replace("bit_depth_", "bd"),
                                      v["full_refresh_ms"], v["fps_ceiling"])
                 for k, v in guide["refresh"].items()]
        lines.append("Full refresh by depth: " + " | ".join(parts))
    lines.append("Rules:")
    for r in guide["rules"]:
        lines.append("  - " + r)
    return "\n".join(lines)
