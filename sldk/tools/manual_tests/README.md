# Manual Test Scripts

This directory contains manual testing and debugging scripts for SLDK development. These are **not** part of the automated test suite and are intended for manual verification and troubleshooting.

## Scripts

### test_led_display.py
Manual test for the LED simulator display window. Creates a simple test pattern and keeps the window open for visual inspection.

**Usage**: `python test_led_display.py`

### test_imports.py
Basic import test to verify SLDK module structure is working correctly. Useful for debugging import issues.

**Usage**: `python test_imports.py`

### test_web_imports.py
Tests that all web framework components can be imported. Helps verify the web module structure.

**Usage**: `python test_web_imports.py`

### test_pygame_window.py
Direct pygame window test for debugging display issues. Creates a simple window with shapes to verify pygame is working.

**Usage**: `python test_pygame_window.py`

### visual_effects_demo.py
Interactive visual demo of the effects engine. Shows various effects like sparkles, edge glow, rainbow cycles, and particle systems.

**Usage**: `python visual_effects_demo.py`

## Note

These scripts are for development and debugging purposes only. For automated testing, see the `sldk/test/` directory which contains the proper pytest test suite.