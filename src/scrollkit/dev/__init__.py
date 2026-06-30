# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Desktop-only developer / AI-agent affordances for ScrollKit.

Everything here exists to help a human or an AI agent build and *verify* a
ScrollKit app on the desktop simulator before flashing it to real hardware:
a headless run harness, pixel metrics, and (via the simulator package) an honest
estimate of how the app would perform on the slow, RAM-constrained MatrixPortal
S3.

This subpackage is **never** meant to run on the device. It pulls in numpy,
pygame, and other desktop-only machinery that would waste scarce RAM (or simply
not import) on CircuitPython. Importing it there raises ImportError immediately,
on purpose, so device code can't accidentally depend on it. Nothing in
``scrollkit`` core (``app/``, ``display/``, the top-level ``__init__``) imports
this module.
"""

import sys

# Hard stop on CircuitPython — these tools are desktop-only by design.
if getattr(sys, "implementation", None) is not None \
        and getattr(sys.implementation, "name", None) == "circuitpython":
    raise ImportError(
        "scrollkit.dev is a desktop-only development/verification toolkit and "
        "cannot run on CircuitPython. Use it from the desktop simulator to "
        "build and check apps before deploying to the device."
    )

from .harness import (  # noqa: E402
    RunResult, run_headless, run_headless_async, record_gif, record_video)
from .capabilities import capabilities, as_text  # noqa: E402
from .validation import validate, ValidationReport, Issue  # noqa: E402
from .performance import performance_guide  # noqa: E402
from . import metrics  # noqa: E402,F401

__all__ = [
    "RunResult", "run_headless", "run_headless_async", "record_gif",
    "record_video", "metrics",
    "capabilities", "as_text", "validate", "ValidationReport", "Issue",
    "performance_guide",
]
