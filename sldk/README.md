# SLDK - Scrolling LED Dev Kit

A lightweight, async-first development framework for creating scrolling LED matrix applications with CircuitPython. Designed for ESP32 and other memory-constrained devices with extensible hardware support.

## Features

- 🚀 **Multi-Hardware Support** - MatrixPortal S3, Adafruit Matrix Portal, custom displays, and more
- 🔄 **Async Throughout** - Built on asyncio for responsive, non-blocking operation
- 🖥️ **Desktop Development** - Full LED simulator for development without hardware
- 🌐 **Web UI** - Optional web interface for configuration (can be disabled)
- 📦 **Easy Deployment** - Built-in .mpy compilation for production
- 🎨 **Flexible Animations** - Extensible animation and content system
- 🔌 **Extensible Hardware** - Easy addition of new CircuitPython-compatible displays

## Installation

### For Development (Desktop)

```bash
pip install sldk[simulator]
```

### For CircuitPython (ESP32)

Copy the `sldk` folder to your device's `lib` directory, or use the built-in deployment tools:

```python
from sldk.deploy import export_mpy
await export_mpy("./myapp", "/Volumes/CIRCUITPY/lib")
```

## Quick Start

```python
from sldk import SLDKApp, ScrollingText

class HelloWorld(SLDKApp):
    async def setup(self):
        """Initialize your app."""
        self.message = ScrollingText("Hello, SLDK!", color=0xFF0000)
    
    async def update_data(self):
        """Update any data (called periodically)."""
        pass  # No data updates needed for hello world
    
    async def prepare_display_content(self):
        """Return content to display."""
        return self.message

# Run the app
if __name__ == "__main__":
    import asyncio
    app = HelloWorld()
    asyncio.run(app.run())
```

## Hardware Support

SLDK is designed to work with any CircuitPython-compatible LED matrix display. There are two ways to add hardware support:

### 1. Application-Specific Hardware (Recommended for Custom Setups)

Override the `create_display()` method in your application:

```python
from sldk import SLDKApp
from sldk.display import DisplayInterface

class MyCustomDisplay(DisplayInterface):
    def __init__(self):
        # Your custom hardware initialization
        pass
        
    async def initialize(self):
        # Initialize your specific hardware
        pass
        
    # Implement required methods...

class MyApp(SLDKApp):
    async def create_display(self):
        """Override to use custom hardware."""
        return MyCustomDisplay()
```

### 2. Contributing Hardware Support to SLDK

For widely-used hardware, contribute support to the library:

```python
# sldk/src/sldk/display/devices/my_device.py
from ..interface import DisplayInterface

class MyDeviceDisplay(DisplayInterface):
    """Support for My Custom LED Matrix."""
    
    def __init__(self, width=64, height=32, **kwargs):
        # Device-specific initialization
        pass
```

Then register it in the hardware detection:

```python
# sldk/src/sldk/display/hardware.py
def detect_hardware():
    """Auto-detect available hardware."""
    try:
        from .devices.my_device import MyDeviceDisplay
        return MyDeviceDisplay()
    except ImportError:
        pass
    # ... other hardware checks
```

### Supported Hardware

| Hardware | Status | Notes |
|----------|--------|--------|
| **Adafruit MatrixPortal S3** | ✅ Built-in | Default ESP32-S3 board |
| **Adafruit Matrix Portal** | 🚧 Planned | Original Matrix Portal |
| **Raspberry Pi** | 📋 Planned | With rpi-rgb-led-matrix |
| **Generic SPI Matrices** | 📋 Planned | Via displayio |
| **Your Hardware** | 🔌 [Contribute!](#contributing-hardware) | |

## Architecture

SLDK uses a three-process architecture for optimal performance:

1. **Display Process** - Handles all rendering at consistent frame rate
2. **Data Update Process** - Manages background data fetching  
3. **Web Server Process** - Provides configuration UI (optional)

On memory-constrained devices, the system gracefully degrades, prioritizing the display process.

## Memory Usage

- Core library: <50KB
- With web server: +30KB
- With animations: +15KB

Total memory footprint can be kept under 100KB for basic applications.

## Documentation

See the [docs](docs/) directory for detailed documentation.

## Examples

Check out the [examples](examples/) directory for more complex applications.

## Status

✅ **Phase 1 Complete** - Core Display System
✅ **Phase 2 Complete** - Hardware Abstraction  
✅ **Phase 3 Complete** - Web Framework
✅ **Phase 4 Complete** - OTA Updates

Current implementation includes:
- **Display System**: Hardware/simulator abstraction with unified API
- **Content Classes**: ScrollingText, StaticText, custom DisplayContent
- **Application Framework**: Three-process async architecture (display, data, web)
- **Platform Detection**: Automatic CircuitPython vs desktop detection
- **Memory Management**: Automatic feature degradation based on available memory
- **Web Framework**: Complete web server with settings UI, status pages, and API endpoints
- **OTA Updates**: Full over-the-air update system with progress tracking and web interface
- **Examples**: Hello World, Animation Demo, and advanced applications

### Working Features
- ✅ Unified display that works on both hardware and simulator
- ✅ Content queue with automatic cycling
- ✅ Async throughout for ESP32 compatibility
- ✅ Memory-aware process spawning
- ✅ Basic text rendering and scrolling
- ✅ Custom animation support
- ✅ Multi-hardware support with auto-detection
- ✅ Web interface for configuration and monitoring
- ✅ Over-the-air updates with web management
- ✅ CircuitPython and development environment compatibility

### Next Phases
- 🚧 **Phase 5**: Advanced Animations (transitions, effects)
- 📋 **Phase 6**: Package Distribution (PyPI, CircuitPython bundle)

## Contributing Hardware

SLDK welcomes hardware contributions! To add support for new devices:

### Step 1: Create Device Driver

Create a new file in `sldk/src/sldk/display/devices/`:

```python
# your_device.py
from ..interface import DisplayInterface

class YourDeviceDisplay(DisplayInterface):
    """Support for Your LED Matrix Device."""
    
    def __init__(self, width=64, height=32, **kwargs):
        super().__init__()
        self._width = width
        self._height = height
        # Device-specific initialization
        
    @property
    def width(self):
        return self._width
        
    @property
    def height(self):
        return self._height
        
    async def initialize(self):
        """Initialize your hardware."""
        # Your initialization code
        pass
        
    async def clear(self):
        """Clear the display."""
        # Your clear implementation
        pass
        
    async def show(self):
        """Update the physical display."""
        # Your show implementation
        pass
        
    async def set_pixel(self, x, y, color):
        """Set a single pixel."""
        # Your pixel implementation
        pass
```

### Step 2: Register Device

Add detection logic to `sldk/src/sldk/display/hardware.py`:

```python
def detect_hardware():
    """Auto-detect available hardware."""
    
    # Check for your device
    try:
        # Device-specific detection logic
        import your_device_module
        return YourDeviceDisplay()
    except ImportError:
        pass
        
    # Existing device checks...
```

### Step 3: Test and Submit

1. Test with the examples: `python examples/hello_world.py`
2. Add documentation and examples for your device
3. Submit a pull request with your changes

### Hardware Requirements

For CircuitPython compatibility, your device should support:

- **displayio**: Standard CircuitPython display framework
- **Memory Constraints**: Work with <200KB available RAM
- **Async Operations**: Non-blocking initialization and updates
- **Color Depth**: Minimum 16-bit color (RGB565)

Popular hardware targets:
- Adafruit MatrixPortal series
- ESP32 with LED matrices
- Raspberry Pi with GPIO matrices  
- Custom CircuitPython boards
- Generic SPI/I2C displays

## License

MIT License - see LICENSE file for details.