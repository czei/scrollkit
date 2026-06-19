# LED Simulator

A standalone Python library for simulating LED matrix displays used with CircuitPython boards. The library provides a visual representation of LED hardware using Pygame, allowing developers to test their code on desktop platforms before deploying to actual hardware.

## Features

- **Pixel-Perfect LED Simulation**: Realistic LED rendering with configurable pitch (2.5, 3, 4, 5, 6mm)
- **CircuitPython API Compatibility**: Implements displayio, terminalio, and adafruit_display_text APIs
- **Multi-Display Support**: Tile multiple displays together (up to 4x4 grid)
- **Font Support**: BDF font loading with bundled fonts
- **Performance Simulation**: Optional hardware performance characteristics simulation
- **Device Emulation**: Pre-configured device profiles (MatrixPortal S3, etc.)

## Installation

```bash
pip install led_simulator
```

## Quick Start

```python
from led_simulator.devices import MatrixPortalS3
from led_simulator.displayio import Group
from led_simulator.adafruit_display_text import Label
from led_simulator.terminalio import FONT

# Create device
device = MatrixPortalS3()
device.initialize()

# Create text label
text_group = Group()
label = Label(font=FONT, text="Hello LED!")
label.x = 0
label.y = 15
text_group.append(label)

# Show on display
device.display.show(text_group)

# Run the simulation
device.run()
```

## API Compatibility

PyLEDSimulator aims for "sufficient API compatibility" with CircuitPython's displayio module. This means:
- Your CircuitPython code should work with minimal or no modifications
- The visual output closely matches real hardware
- Some advanced features may have behavioral differences (documented below)

### Known Limitations

- Rendering order nuances may differ slightly from hardware
- Memory management follows Python's model, not CircuitPython's
- Some rotation/scaling transforms may have minor differences
- Font rendering may have slight metric differences

### CircuitPython Compatibility

For detailed information about writing code that works in both the simulator and on CircuitPython hardware, see [CIRCUITPYTHON_COMPATIBILITY.md](CIRCUITPYTHON_COMPATIBILITY.md). This guide covers:
- Module availability differences
- Exception handling in CircuitPython
- Memory constraints
- Common pitfalls and solutions

## Examples

See the `examples/` directory for various usage examples:
- `matrixportal_s3_example.py` - Basic MatrixPortal S3 simulation
- `scrolling_text_example.py` - Text scrolling demonstration
- `dual_zone_example.py` - Multi-zone display example
- `multi_display_example.py` - Multiple display coordination
- `rainbow_text.py` - Colorful text effects
- `pixel_dust.py` - Particle effects simulation

## License

Apache License 2.0

## Attribution

Portions of this project are adapted from CircuitPython:
- Copyright (c) 2016-2024 Adafruit Industries
- Licensed under MIT License
- See ATTRIBUTION.md for details