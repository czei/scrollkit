# CircuitPython Compatibility Guide

This document outlines the CircuitPython compatibility considerations when using PyLEDSimulator and developing code that needs to run on both desktop (simulation) and CircuitPython hardware.

## Overview

PyLEDSimulator implements CircuitPython's display APIs to allow desktop development and testing. However, there are important differences between standard Python and CircuitPython that developers must be aware of.

## Core Compatibility Principles

### 1. Module Availability

CircuitPython has a limited subset of Python's standard library. Many common modules are not available or have limited functionality.

#### Available in CircuitPython:
- `os` (limited functionality)
- `time` (limited functionality)
- `json` (basic functionality only)
- `re` (basic regex support)
- `random` (limited functionality - no `shuffle()`)
- `asyncio` (cooperative multitasking only)
- `gc` (garbage collection)
- `sys` (limited functionality)

#### NOT Available in CircuitPython:
- `pathlib`
- `urllib`
- `threading`
- `subprocess`
- `typing` (type hints must be removed)
- `dataclasses`
- `collections` (except `namedtuple`)
- Most standard library modules

### 2. Exception Handling Differences

CircuitPython uses different exceptions than standard Python:

```python
# ❌ WRONG - Standard Python only
try:
    data = json.loads(response)
except json.JSONDecodeError:  # Not available in CircuitPython
    pass

# ✅ CORRECT - CircuitPython compatible
try:
    data = json.loads(response)
except ValueError:  # CircuitPython raises ValueError for invalid JSON
    pass

# ❌ WRONG - Standard Python only
try:
    with open('file.txt') as f:
        content = f.read()
except FileNotFoundError:  # Not available in CircuitPython
    pass

# ✅ CORRECT - CircuitPython compatible
try:
    with open('file.txt') as f:
        content = f.read()
except OSError:  # CircuitPython only has OSError
    pass
```

### 3. String and Type Operations

```python
# ❌ WRONG - f-string debug syntax not supported
print(f"{value=}")

# ✅ CORRECT - Use regular f-strings
print(f"value={value}")

# ❌ WRONG - match/case not available
match command:
    case "start":
        start()

# ✅ CORRECT - Use if/elif
if command == "start":
    start()
elif command == "stop":
    stop()
```

### 4. Memory Management

CircuitPython has limited memory (typically 256KB-512KB RAM):

```python
# ❌ WRONG - Loading large data structures
data = json.loads(large_file_content)  # May cause MemoryError

# ✅ CORRECT - Process data in chunks or use generators
def process_json_lines(file_path):
    with open(file_path) as f:
        for line in f:
            yield json.loads(line)
```

### 5. File Operations

```python
# ❌ WRONG - Using pathlib
from pathlib import Path
if Path('config.json').exists():
    pass

# ✅ CORRECT - Use os or try/except
import os
try:
    os.stat('config.json')
    file_exists = True
except OSError:
    file_exists = False
```

### 6. Time Operations

```python
# ❌ WRONG - time.time() not always available
start_time = time.time()

# ✅ CORRECT - Use time.monotonic()
start_time = time.monotonic()
```

### 7. Random Module Limitations

```python
# ❌ WRONG - random.shuffle() not available
import random
my_list = [1, 2, 3, 4, 5]
random.shuffle(my_list)

# ✅ CORRECT - Implement simple shuffle
import random

def simple_shuffle(lst):
    """Simple in-place shuffle for CircuitPython compatibility."""
    for i in range(len(lst)):
        j = random.randint(0, len(lst) - 1)
        lst[i], lst[j] = lst[j], lst[i]

my_list = [1, 2, 3, 4, 5]
simple_shuffle(my_list)
```

### 8. Async Operations

```python
# ❌ WRONG - asyncio.run() at module level
import asyncio
asyncio.run(main())

# ✅ CORRECT - Use asyncio properly
import asyncio

async def main():
    # Your async code here
    pass

# At the bottom of your main file:
if __name__ == "__main__":
    asyncio.run(main())
```

## displayio API Changes

### Display.show() Removed in CircuitPython 9.x

The `.show()` method has been removed from Display objects in CircuitPython 9.x:

```python
# ❌ WRONG - Old API (CircuitPython 8.x and earlier)
display.show(None)  # Clear display
display.show(group)  # Show group

# ✅ CORRECT - New API (CircuitPython 9.x)
display.root_group = None  # Clear display
display.root_group = group  # Show group
```

### MatrixPortal Pixel Access

The MatrixPortal class doesn't provide direct pixel manipulation methods:

```python
# ❌ WRONG - No set_pixel/get_pixel methods
matrixportal.set_pixel(x, y, color)
color = matrixportal.get_pixel(x, y)

# ✅ CORRECT - Use displayio.Bitmap
bitmap = displayio.Bitmap(width, height, num_colors)
palette = displayio.Palette(num_colors)
palette[0] = 0x000000  # Black
palette[1] = 0xFFFF00  # Yellow

tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
group = displayio.Group()
group.append(tile_grid)
display.root_group = group

# Set pixels via bitmap
bitmap[x, y] = 1  # Set to color index 1 (yellow)
```

## PyLEDSimulator-Specific Compatibility

### 1. Conditional Imports

Always structure imports to support both environments:

```python
try:
    # Try hardware imports first
    import board
    import displayio
    import terminalio
    from adafruit_display_text import label
    HARDWARE_AVAILABLE = True
except ImportError:
    # Fall back to simulator
    from pyledsimulator import displayio
    from pyledsimulator import terminalio
    from pyledsimulator.adafruit_display_text import label
    HARDWARE_AVAILABLE = False
```

### 2. Display Initialization

```python
def get_display():
    """Get display for hardware or simulator."""
    if HARDWARE_AVAILABLE:
        return board.DISPLAY
    else:
        from pyledsimulator.devices import MatrixPortalS3
        device = MatrixPortalS3()
        device.initialize()
        return device.display
```

### 3. Performance Differences

The simulator runs at desktop speeds, which is much faster than CircuitPython:

```python
# Add delays to simulate hardware timing
if not HARDWARE_AVAILABLE:
    time.sleep(0.1)  # Simulate hardware processing time
```

### 4. Memory Constraints Simulation

When developing with the simulator, be mindful of hardware memory limits:

```python
# Even though desktop has more memory, design for hardware constraints
MAX_SPRITES = 10  # Limit based on hardware capabilities
MAX_TEXT_LENGTH = 100  # Avoid long strings
```

## Common Pitfalls and Solutions

### 1. HTTP Libraries

```python
# ❌ WRONG - Using requests
import requests
response = requests.get(url)

# ✅ CORRECT - Use adafruit_requests
import adafruit_requests
response = adafruit_requests.get(url)
```

### 2. JSON Handling

```python
# ❌ WRONG - Expecting specific exceptions
try:
    data = json.loads(text)
except json.JSONDecodeError as e:
    print(f"JSON error at position {e.pos}")

# ✅ CORRECT - Handle generic ValueError
try:
    data = json.loads(text)
except ValueError as e:
    print(f"JSON error: {e}")
```

### 3. Type Hints

```python
# ❌ WRONG - Using type hints
def process_data(data: dict[str, Any]) -> list[str]:
    pass

# ✅ CORRECT - Remove type hints or use comments
def process_data(data):  # type: (dict) -> list
    """Process data dictionary and return list of strings."""
    pass
```

## Testing for Compatibility

### 1. Linting for CircuitPython

Use the project's linting tools to catch compatibility issues:

```bash
make lint-errors  # Catches undefined names and syntax errors
```

### 2. Import Testing

Test imports in both environments:

```python
# test_imports.py
def test_imports():
    """Verify all imports work in current environment."""
    try:
        import json
        import time
        import os
        print("✓ Core imports successful")
    except ImportError as e:
        print(f"✗ Import failed: {e}")
```

### 3. Memory Testing

```python
import gc

def check_memory():
    """Check available memory (CircuitPython only)."""
    gc.collect()
    if hasattr(gc, 'mem_free'):
        print(f"Free memory: {gc.mem_free()} bytes")
```

## Best Practices

1. **Always test on hardware**: The simulator is for development, but final testing must be on actual hardware
2. **Use minimal dependencies**: Stick to CircuitPython built-ins when possible
3. **Handle errors gracefully**: Assume operations can fail due to memory or hardware constraints
4. **Keep it simple**: Complex Python features are often not available
5. **Check CircuitPython docs**: When in doubt, consult https://docs.circuitpython.org/

## Useful Resources

- [CircuitPython API Reference](https://docs.circuitpython.org/en/latest/docs/library/index.html)
- [CircuitPython vs MicroPython](https://docs.circuitpython.org/en/latest/docs/design_guide.html)
- [Adafruit Learn Guides](https://learn.adafruit.com/category/circuitpython)

## Version Compatibility

PyLEDSimulator targets CircuitPython 8.x and 9.x compatibility. Features specific to newer versions should be avoided or have fallbacks.