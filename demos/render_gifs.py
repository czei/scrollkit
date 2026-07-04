#!/usr/bin/env python3
"""Render an animated GIF preview of every ScrollKit demo (for the docs).

Drives each demo headlessly through the desktop simulator and records the LED
panel to ``docs/assets/demos/<name>.gif`` — the same round-dot look you see when
you run a demo, captured frame-accurate via the simulator's ``save_gif`` (see
``SimulatorDisplay.start_recording`` / ``save_gif``). Generation is **offline and
deterministic**: the two demos that hit public APIs are seeded with canned data
so the GIF shows a populated display, never a "loading..." frame.

Run (regenerate all 12 GIFs):

    make docs-gifs
    # or:  PYTHONSAFEPATH=1 PYTHONPATH=src python demos/render_gifs.py

Render only some:   python demos/render_gifs.py hello_world showcase
Use live network:   python demos/render_gifs.py --live temperature

This is a docs/tooling script, not a demo itself — it imports each demo module
and instantiates its ``ScrollKitApp`` subclass.
"""

import argparse
import asyncio  # noqa: F401  (kept: demos import asyncio via the shared path setup)
import importlib.util
import os
import sys

# Render offscreen — no window pops up while generating.
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# Put src/ and demos/ on the path (mirrors what each demo does at import time).
_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
for _p in (os.path.join(_ROOT, "src"), _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from scrollkit.app.base import ScrollKitApp  # noqa: E402
from scrollkit.dev import record_gif  # noqa: E402

OUT_DIR = os.path.join(_ROOT, "docs", "assets", "demos")


# --------------------------------------------------------------------------
# Seeding: feed the network demos canned data so generation is offline and the
# GIF shows real-looking values. We stub the demo's HttpClient.get (leaving its
# real fetch/parse/chunk logic intact) rather than replacing update_data().
# --------------------------------------------------------------------------

_CANNED_USD = {
    "bitcoin": 64213, "ethereum": 3380, "solana": 152.7, "cardano": 0.45,
    "dogecoin": 0.16, "polkadot": 6.8, "litecoin": 84, "chainlink": 17.2,
    "stellar": 0.11, "monero": 168,
}


class _FakeResponse:
    """Minimal stand-in for an HttpClient response with .json()."""

    def __init__(self, data):
        self._data = data

    def json(self):
        return self._data


async def _fake_get(url, *args, **kwargs):
    """Return canned JSON shaped like the public APIs the demos call."""
    if "open-meteo" in url:
        return _FakeResponse({"current": {"temperature_2m": 21.4}})
    if "coingecko" in url:
        ids = url.split("ids=")[1].split("&")[0].split(",")
        return _FakeResponse({c: {"usd": _CANNED_USD.get(c, 1.0)} for c in ids})
    return _FakeResponse({})


async def _noop_async(*args, **kwargs):
    return None


def _seed_network(app):
    """Stub the app's HTTP (and any startup OTA check) for offline rendering."""
    if hasattr(app, "http"):
        app.http.get = _fake_get
    if hasattr(app, "_check_for_updates"):
        app._check_for_updates = _noop_async


# --------------------------------------------------------------------------
# Per-demo render config. ``seconds`` is chosen so each GIF shows a full cycle;
# ``step`` (frame_step) and ``width`` trade size for smoothness. Defaults suit
# the short scrollers; the long/dense demos drop a frame to stay small.
# --------------------------------------------------------------------------

# Render the panel at a slightly higher LED pitch so the downscaled GIF is crisp
# and the colored text is legible (the lever the hero shot uses). Visual scale
# only — the logical 64x32 grid is unchanged. Kept modest (vs 6.0) to bound the
# per-frame memory of the recording, since some demos emit many frames.
RENDER_PITCH = 4.0

# ``self_driving`` demos run their whole animation inside an infinite setup()
# loop (they never hand control back to a content queue), so they can't be driven
# by run_headless's "setup then step N frames" model — we run setup() as a
# cancellable task and cap the capture at ``max_frames`` instead of ``seconds``.
DEFAULTS = {"seconds": 5.0, "step": 2, "width": 480, "colors": 64, "seed": None,
            "self_driving": False, "max_frames": 170}

PER_DEMO = {
    "hello_world":          {"seconds": 5.0},
    "colors":               {"seconds": 6.0},
    "clock":                {"seconds": 4.0},
    "drip_splash":          {"self_driving": True, "max_frames": 170},
    "reveal_splash":        {"seconds": 7.0},
    "configurable_message": {"seconds": 5.0},
    "drip_value":           {"self_driving": True, "max_frames": 200},
    "golden_transition":    {"seconds": 6.0},
    "image_intro":          {"self_driving": True, "max_frames": 400, "step": 3},
    "rainbow":              {"seconds": 5.0},
    "temperature":          {"seconds": 5.0, "seed": _seed_network},
    "crypto_dashboard":     {"seconds": 8.0, "seed": _seed_network},
    "showcase":             {"seconds": 9.0, "step": 3},
    "swarm_reveal":         {"self_driving": True, "max_frames": 170},
}


async def _capture_self_driving(app, max_frames):
    """Record a demo whose setup() runs the animation in an infinite loop.

    Runs setup() as a task and stops once ``max_frames`` frames are captured (or
    setup ends on its own), so a never-returning splash loop is bounded.
    """
    await app._initialize_display()
    app.display.start_recording()
    app.running = True
    task = asyncio.create_task(app.setup())
    try:
        while not task.done() and len(app.display._recording or []) < max_frames:
            await asyncio.sleep(0.01)   # let setup() produce frames via show()
    finally:
        app.running = False
        if not task.done():
            task.cancel()
            try:
                await task
            except BaseException:       # noqa: BLE001 — cancellation/teardown
                pass
        try:
            await app.cleanup()
        except Exception:
            pass


def _hi_res_display(opts=None, width=64, height=32):
    """Display factory used for recording: forces the crisp render pitch."""
    from scrollkit.display.simulator import SimulatorDisplay
    return SimulatorDisplay(width=width, height=height, pitch=RENDER_PITCH)


def discover_demos():
    """Map demo name -> file path for every demo under easy/medium/hard."""
    demos = {}
    for tier in ("easy", "medium", "hard"):
        tier_dir = os.path.join(_HERE, tier)
        if not os.path.isdir(tier_dir):
            continue
        for fname in sorted(os.listdir(tier_dir)):
            if fname.endswith(".py") and not fname.startswith("_"):
                demos[fname[:-3]] = os.path.join(tier_dir, fname)
    return demos


def load_app_class(name, path):
    """Import a demo module and return its single ScrollKitApp subclass."""
    spec = importlib.util.spec_from_file_location("demo_%s" % name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    candidates = [
        obj for obj in vars(module).values()
        if isinstance(obj, type) and issubclass(obj, ScrollKitApp)
        and obj is not ScrollKitApp and obj.__module__ == module.__name__
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            "%s: expected exactly one ScrollKitApp subclass, found %d (%s)"
            % (name, len(candidates), [c.__name__ for c in candidates]))
    return candidates[0]


def render_demo(name, path, *, live=False):
    """Render one demo to docs/assets/demos/<name>.gif; return (path, bytes)."""
    cfg = dict(DEFAULTS)
    cfg.update(PER_DEMO.get(name, {}))

    app_cls = load_app_class(name, path)
    app = app_cls()

    # Restore the library-default scroll speed: a stray runtime settings.json in
    # the CWD can set it to "None" (static), which would freeze the scrollers.
    if hasattr(app, "settings"):
        app.settings.settings["scroll_speed"] = "Medium"

    if cfg["seed"] is not None and not live:
        cfg["seed"](app)

    out = os.path.join(OUT_DIR, "%s.gif" % name)
    if cfg["self_driving"]:
        # Capture the self-driving animation directly (record_gif can't drive a
        # demo that never returns from setup()), then encode with save_gif.
        asyncio.run(_capture_self_driving(app, cfg["max_frames"]))
        saved = app.display.save_gif(out, frame_step=cfg["step"],
                                     target_width=cfg["width"],
                                     max_colors=cfg["colors"])
    else:
        saved = record_gif(app, out, seconds=cfg["seconds"], frame_step=cfg["step"],
                           target_width=cfg["width"], max_colors=cfg["colors"])
    size = os.path.getsize(out) if saved and os.path.exists(out) else 0
    return saved, size


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("names", nargs="*",
                        help="demo names to render (default: all)")
    parser.add_argument("--live", action="store_true",
                        help="let network demos fetch real data instead of seeding")
    args = parser.parse_args()

    # Force every demo's display to the crisp recording pitch (the demos build
    # their display through this shared factory).
    import _demo_support
    _demo_support.simulator_display = _hi_res_display

    os.makedirs(OUT_DIR, exist_ok=True)
    demos = discover_demos()
    targets = args.names or list(demos)

    unknown = [n for n in targets if n not in demos]
    if unknown:
        parser.error("unknown demo(s): %s\navailable: %s"
                     % (", ".join(unknown), ", ".join(demos)))

    print("Rendering %d demo GIF(s) -> %s\n" % (len(targets), OUT_DIR))
    total = 0
    failures = []
    for name in targets:
        try:
            saved, size = render_demo(name, demos[name], live=args.live)
        except Exception as e:  # keep going; report at the end
            print("  %-22s FAILED: %r" % (name, e))
            failures.append(name)
            continue
        if not saved:
            print("  %-22s no GIF (display can't record?)" % name)
            failures.append(name)
            continue
        total += size
        print("  %-22s %6.0f KB  %s" % (name, size / 1024, os.path.basename(saved)))

    print("\nTotal: %.1f MB across %d GIF(s)" % (total / 1e6, len(targets) - len(failures)))
    if failures:
        print("Failed: %s" % ", ".join(failures))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
