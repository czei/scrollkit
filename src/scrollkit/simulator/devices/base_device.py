# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Base class for LED matrix devices."""

from abc import ABC, abstractmethod
from ..core import LEDMatrix
from ..displayio import Display, FourWire


class BaseDevice(ABC):
    """Abstract base class for LED matrix devices.
    
    Provides common functionality for all simulated devices.
    """
    
    def __init__(self, width, height, pitch=4.0):
        """Initialize base device.
        
        Args:
            width: Display width in pixels
            height: Display height in pixels
            pitch: LED pitch in mm
        """
        self.width = width
        self.height = height
        self.pitch = pitch
        
        # Display components
        self.display = None
        self.matrix = None
        self.display_bus = None

        # Performance simulation (optional)
        self.performance_manager = None
        
    @abstractmethod
    def initialize(self):
        """Initialize the device.
        
        Must be implemented by subclasses.
        """
        raise NotImplementedError
        
    def set_brightness(self, brightness):
        """Set display brightness.
        
        Args:
            brightness: Brightness value from 0.0 to 1.0
        """
        if self.display:
            self.display.brightness = brightness
            
    def clear(self):
        """Clear the display."""
        if self.matrix:
            self.matrix.clear()
            
    def show(self, group_or_tilegrid):
        """Show a Group or TileGrid on the display.
        
        Args:
            group_or_tilegrid: Display object to show
        """
        if self.display:
            self.display.root_group = group_or_tilegrid
            
    def refresh(self):
        """Refresh the display."""
        if self.display:
            self.display.refresh()
            
    def get_surface(self):
        """Get the pygame surface for this device.
        
        Returns:
            Pygame surface or None
        """
        if self.matrix:
            return self.matrix.get_surface()
        return None