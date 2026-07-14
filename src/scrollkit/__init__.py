# Copyright (c) 2024-2026 Michael Czeiszperger
"""ScrollKit - LED Matrix Display Framework for CircuitPython and Desktop.

A framework for building scrolling LED matrix applications that run unchanged on
CircuitPython hardware (Adafruit MatrixPortal S3) and a desktop pygame simulator.

This top-level package is intentionally lightweight: it exposes only version
metadata and performs NO eager submodule imports. On CircuitPython every imported
module costs RAM (a globals dict + bytecode), so callers import exactly what they
need from submodules, e.g.::

    from scrollkit.app.base import ScrollKitApp
    from scrollkit.display.unified import UnifiedDisplay
"""

__version__ = "0.9.0"
