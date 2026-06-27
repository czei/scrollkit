# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""CircuitPython terminalio compatibility module for SLDK simulator.

Provides the default FONT for text rendering.
"""

import os
from ..adafruit_bitmap_font import bitmap_font

# Load the default font (viii.bdf - 8 pixels tall)
_font_path = os.path.join(os.path.dirname(__file__), '..', 'fonts', 'viii.bdf')
try:
    FONT = bitmap_font.load_font(_font_path)
except Exception as e:
    print(f"Warning: Could not load default font from {_font_path}: {e}")
    # Create a minimal fallback
    FONT = None

# For compatibility with existing code that imports the module
__all__ = ['FONT']