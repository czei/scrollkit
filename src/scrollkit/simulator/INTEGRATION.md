# Integrating PyLEDSimulator with ThemeParkAPI

This document explains how to use PyLEDSimulator to develop and test the LED display functionality of ThemeParkAPI on your desktop before deploying to actual MatrixPortal hardware.

## Overview

PyLEDSimulator provides CircuitPython-compatible APIs that allow the same code to run on both:
- Desktop computers (using pygame for visualization)
- MatrixPortal S3 hardware (using actual CircuitPython)

## Integration Approach

### 1. Conditional Imports

In your ThemeParkAPI code, use conditional imports to support both environments:

```python
# In src/ui/display_impl.py or similar
try:
    # Try hardware imports first
    import board
    import displayio
    import terminalio
    from adafruit_display_text import label
    HARDWARE = True
except ImportError:
    # Fall back to simulator
    from pyledsimulator import displayio
    from pyledsimulator import terminalio
    from pyledsimulator.adafruit_display_text import label
    from pyledsimulator.devices import MatrixPortalS3
    HARDWARE = False
```

### 2. Display Initialization

Create a unified initialization function:

```python
def create_display():
    """Create display for hardware or simulator."""
    if HARDWARE:
        # Hardware is already initialized via board.DISPLAY
        return board.DISPLAY
    else:
        # Create simulated device
        device = MatrixPortalS3()
        device.initialize()
        return device.display
```

### 3. Example Integration

Here's how to modify the existing ThemeParkAPI display code:

```python
# Modified display_impl.py
class HardwareDisplay(DisplayInterface):
    def __init__(self):
        try:
            # Hardware imports
            import board
            import displayio
            from adafruit_display_text import label
            self.display = board.DISPLAY
            self.is_hardware = True
        except ImportError:
            # Simulator imports
            from pyledsimulator.devices import MatrixPortalS3
            from pyledsimulator import displayio
            from pyledsimulator.adafruit_display_text import label
            
            # Create simulated device
            self.device = MatrixPortalS3()
            self.device.initialize()
            self.display = self.device.display
            self.is_hardware = False
            
        self.displayio = displayio
        self.label = label
        
    def run_simulator(self):
        """Run the simulator main loop (desktop only)."""
        if not self.is_hardware:
            self.device.run()
```

### 4. Running in Development

When developing on your desktop:

```python

# Create display
display = HardwareDisplay()

# Create your UI as normal
main_group = display.displayio.Group()

# Add labels, etc.
park_label = display.label.Label(
    font=terminalio.FONT,
    text="Magic Kingdom",
    color=0xFFFFFF
)
main_group.append(park_label)

# Show on display
display.display.show(main_group)

# Run simulator (this starts the pygame window)
if not display.is_hardware:
    display.run_simulator()
```

### 5. Testing Scrolling Displays

The simulator supports the same scrolling functionality:

```python
from pyledsimulator.adafruit_display_text import ScrollingLabel

# Create scrolling wait times
wait_times_scroll = ScrollingLabel(
    font=terminalio.FONT,
    text=format_wait_times(park),
    max_characters=12,
    animate_time=0.3
)
wait_times_scroll.start_scrolling()

# In your update loop
def update():
    wait_times_scroll.update()
    # Update other dynamic content
```

## Benefits

1. **Faster Development**: No need to deploy to hardware for every change
2. **Better Debugging**: Use standard Python debugging tools
3. **CI/CD Integration**: Run visual tests in continuous integration
4. **Demonstrations**: Show the display functionality without hardware

## Example: Theme Park Display

See `examples/theme_park_display.py` for a complete example of simulating a theme park wait times display.

## Deployment

When ready to deploy to hardware:
1. The same code runs on MatrixPortal S3
2. Remove any simulator-specific code (like `device.run()`)
3. Use the standard deployment process (`make copy_to_circuitpy`)

## Performance Considerations

The simulator runs at desktop speeds, which is much faster than CircuitPython hardware. To simulate realistic timing:

1. Use appropriate delays in animations
2. Test scrolling speeds on actual hardware
3. Consider implementing the PerformanceManager for accurate simulation (future enhancement)

## CircuitPython Compatibility

For important information about CircuitPython-specific limitations and compatibility considerations, see [CIRCUITPYTHON_COMPATIBILITY.md](CIRCUITPYTHON_COMPATIBILITY.md). This includes:
- Module availability differences between standard Python and CircuitPython
- Exception handling differences
- Memory constraints on hardware
- Common pitfalls when developing cross-platform code