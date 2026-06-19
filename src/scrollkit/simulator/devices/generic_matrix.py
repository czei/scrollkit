"""Generic LED matrix device for custom configurations."""

from .base_device import BaseDevice
from ..core import LEDMatrix
from ..displayio import Display, FourWire


class GenericMatrix(BaseDevice):
    """Generic LED matrix device with customizable parameters.
    
    Use this for non-standard matrix configurations.
    """
    
    def __init__(self, width, height, pitch=4.0, led_size=None):
        """Initialize generic matrix.
        
        Args:
            width: Display width in pixels
            height: Display height in pixels
            pitch: LED pitch in mm (default 4.0)
            led_size: Optional custom LED size in pixels
        """
        super().__init__(width, height, pitch)
        self.led_size = led_size
        
    def initialize(self):
        """Initialize generic matrix device."""
        # Create LED matrix with custom parameters
        self.matrix = LEDMatrix(
            self.width,
            self.height,
            pitch=self.pitch,
            led_size=self.led_size,
            performance_manager=self.performance_manager
        )
        
        # Create display bus (stub for compatibility)
        self.display_bus = FourWire(
            spi_bus=None,
            command=None,
            chip_select=None,
            reset=None
        )
        
        # Create display
        self.display = Display(
            self.display_bus,
            width=self.width,
            height=self.height,
            rotation=0,
            color_depth=16,
            auto_refresh=True
        )
        
        # Link display to matrix
        self.display._matrix = self.matrix
        
    @property
    def default_font(self):
        """Get the default font for this device."""
        from ..terminalio import FONT
        return FONT