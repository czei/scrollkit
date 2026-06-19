"""Pytest configuration for the ScrollKit library test suite.

The tests exercise the library against the desktop pygame simulator, headlessly:
SDL is forced to the dummy (windowless) driver so they run in CI without a
display. Set this before pygame is imported anywhere.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
