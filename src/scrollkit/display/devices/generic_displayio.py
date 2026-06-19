"""Generic displayio device driver for SLDK.

Supports any CircuitPython device with displayio support.
"""

import sys

# Verify we're on CircuitPython
if not (hasattr(sys, 'implementation') and sys.implementation.name == 'circuitpython'):
    raise ImportError("Generic displayio can only be used on CircuitPython")

import displayio
import terminalio
try:
    from adafruit_display_text.label import Label
except ImportError:
    Label = None

from ..interface import DisplayInterface


class GenericDisplayIODevice(DisplayInterface):
    """Generic displayio-based display driver.
    
    This driver works with any CircuitPython device that supports displayio.
    Users need to provide their own display initialization.
    """
    
    def __init__(self, display_obj=None, width=64, height=32, **kwargs):
        """Initialize generic displayio device.
        
        Args:
            display_obj: Pre-initialized displayio.Display object
            width: Display width in pixels (if display_obj not provided)
            height: Display height in pixels (if display_obj not provided)
            **kwargs: Additional parameters
        """
        self._width = width
        self._height = height
        self._brightness = 0.3
        self._external_display = display_obj
        
        # Display components
        self.display = display_obj
        self.main_group = None
        self._initialized = False
        
        # Default font
        self.font = terminalio.FONT
        
    @property
    def width(self):
        """Display width in pixels."""
        if self.display and hasattr(self.display, 'width'):
            return self.display.width
        return self._width
        
    @property
    def height(self):
        """Display height in pixels."""
        if self.display and hasattr(self.display, 'height'):
            return self.display.height
        return self._height
    
    async def initialize(self):
        """Initialize the generic displayio device."""
        if self._initialized:
            return
            
        try:
            # If no external display provided, try to get the built-in display
            if not self.display:
                self.display = displayio.Display.get_builtin_display()
                
            if not self.display:
                raise RuntimeError(
                    "No display available. Provide display_obj parameter "
                    "or ensure your device has a built-in display."
                )
            
            # Set up display groups
            self.main_group = displayio.Group()
            self.display.root_group = self.main_group
            
            # Set initial brightness
            await self.set_brightness(self._brightness)
            
            self._initialized = True
            print(f"Generic displayio initialized: {self.width}x{self.height}")
            
        except Exception as e:
            print(f"Failed to initialize generic displayio: {e}")
            raise
    
    async def clear(self):
        """Clear the display."""
        # Hide all groups
        while len(self.main_group) > 0:
            self.main_group.pop()
        
        # Fill with black if possible
        if hasattr(self.display, 'fill'):
            self.display.fill(0x000000)
    
    async def show(self):
        """Update the physical display."""
        if self.display and hasattr(self.display, 'refresh'):
            self.display.refresh(minimum_frames_per_second=0)
        return True
    
    async def set_pixel(self, x, y, color):
        """Set a single pixel color.
        
        Note: This is a basic implementation. For better performance,
        override this method with hardware-specific pixel access.
        
        Args:
            x: X coordinate
            y: Y coordinate
            color: Color as 24-bit RGB integer
        """
        # Create a 1x1 bitmap for the pixel
        bitmap = displayio.Bitmap(1, 1, 1)
        palette = displayio.Palette(1)
        palette[0] = color
        
        tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
        
        # Position the pixel
        pixel_group = displayio.Group()
        pixel_group.x = x
        pixel_group.y = y
        pixel_group.append(tile_grid)
        
        self.main_group.append(pixel_group)
    
    async def fill(self, color):
        """Fill entire display with color.
        
        Args:
            color: Color as 24-bit RGB integer
        """
        # Create full-screen bitmap
        bitmap = displayio.Bitmap(self.width, self.height, 1)
        palette = displayio.Palette(1)
        palette[0] = color
        
        tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
        
        # Clear existing content and add fill
        await self.clear()
        fill_group = displayio.Group()
        fill_group.append(tile_grid)
        self.main_group.append(fill_group)
    
    async def set_brightness(self, brightness):
        """Set display brightness.
        
        Args:
            brightness: Float between 0.0 and 1.0
        """
        self._brightness = max(0.0, min(1.0, brightness))
        
        if self.display and hasattr(self.display, 'brightness'):
            try:
                self.display.brightness = self._brightness
            except Exception as e:
                print(f"Failed to set brightness: {e}")
    
    async def draw_text(self, text, x=0, y=0, color=0xFFFFFF, font=None):
        """Draw text on display.
        
        Args:
            text: Text to display
            x: Starting X coordinate
            y: Starting Y coordinate
            color: Text color as 24-bit RGB
            font: Font to use (uses default if None)
        """
        if not Label:
            print("adafruit_display_text not available")
            return
            
        # Use provided font or default
        if font is None:
            font = self.font
            
        # Create label
        label = Label(font, text=text, color=color)
        label.x = x
        label.y = y
        
        # Create a group for this label
        label_group = displayio.Group()
        label_group.append(label)
        self.main_group.append(label_group)