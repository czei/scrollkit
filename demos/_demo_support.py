"""Shared demo plumbing: run any demo directly, with --throttle / --strict flags.

Importing this module puts the repo's ``src/`` on ``sys.path`` so the demos run
with a plain ``python demos/.../foo.py`` (no PYTHONPATH needed). It also exposes
the common command-line options and a simulator-display factory that honors them,
so the hardware-sim controls are real CLI flags rather than environment variables.
"""

import argparse
import asyncio
import os
import sys

# --- make `import scrollkit` work no matter where the demo is launched from ---
_SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
if os.path.isdir(_SRC) and _SRC not in sys.path:
    sys.path.insert(0, _SRC)


def demo_args(description=""):
    """Parse the common demo CLI flags (--throttle / --strict)."""
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--throttle", action="store_true",
                   help="crawl the window at the modeled MatrixPortal S3 speed")
    p.add_argument("--strict", action="store_true",
                   help="enforce the hardware feasibility gate (raise if an "
                        "effect busts the ~20 fps device budget)")
    return p.parse_args()


def simulator_display(opts=None, width=64, height=32):
    """Build a SimulatorDisplay honoring the parsed --throttle / --strict flags."""
    from scrollkit.display.simulator import SimulatorDisplay
    throttle = bool(getattr(opts, "throttle", False))
    strict = bool(getattr(opts, "strict", False))
    return SimulatorDisplay(width=width, height=height,
                            throttle=throttle, strict=strict)


def run(app, opts=None):
    """Attach the parsed options to ``app`` and run its event loop."""
    if opts is not None:
        app.opts = opts
    asyncio.run(app.run())


def main(app, description=""):
    """Desktop entry point: parse the CLI flags, attach them, run the app."""
    run(app, demo_args(description))
