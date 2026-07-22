# Copyright (c) 2024-2026 Michael Czeiszperger
"""MatrixPortal S3 device simulation."""

from .base_device import BaseDevice
from ..core import LEDMatrix
from ..displayio import Display, FourWire


class MatrixPortalS3(BaseDevice):
    """Simulated Adafruit MatrixPortal S3 device.
    
    Standard configuration with 64x32 RGB LED matrix.
    """
    
    def __init__(self, pitch=3.0, width=64, height=32):
        """Initialize MatrixPortal S3.
        
        Args:
            pitch: LED pitch in mm (default 3.0 for 192x96mm physical size)
            width: Display width in pixels (default 64)
            height: Display height in pixels (default 32)
        """
        super().__init__(width, height, pitch)
        
        # Board-specific attributes
        self.NEOPIXEL = None  # Status NeoPixel (not simulated)
        # The real S3 carries an LIS3DH at I2C 0x19 (NOT the 0x18 Adafruit's
        # libraries default to). The simulator has no I2C bus to emulate, so the
        # virtual gravity vector lives on the display (arrow keys /
        # set_virtual_tilt) and scrollkit.sensors.tilt.TiltSensor reads it there;
        # this attribute just records that the board HAS the part.
        self.ACCELEROMETER = "lis3dh"
        self.ACCELEROMETER_I2C_ADDRESS = 0x19
        
    def initialize(self):
        """Initialize MatrixPortal S3 specific features."""
        # Create LED matrix
        self.matrix = LEDMatrix(
            self.width, 
            self.height, 
            pitch=self.pitch,
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
        
        # Create board module stub
        self._create_board_module()
        
    def _create_board_module(self):
        """Create board module attributes for compatibility."""
        # This would normally be done by importing board
        # but we create a simple stub here
        class BoardStub:
            def __init__(self, display):
                self.DISPLAY = display
                
        self.board = BoardStub(self.display)
        
    def set_text_color(self, color):
        """Set default text color (convenience method).
        
        Args:
            color: RGB color value
        """
        # This is a convenience method not in the real hardware
        # but useful for the simulator
        pass
        
    @property
    def default_font(self):
        """Get the default font for this device."""
        from ..terminalio import FONT
        return FONT