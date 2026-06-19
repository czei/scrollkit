"""Base class for LED matrix devices."""

from abc import ABC, abstractmethod
from ..core import LEDMatrix, DisplayManager
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
        self.display_manager = None
        
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
            
    def run(self, update_callback=None, title=None):
        """Run the device simulation.
        
        Args:
            update_callback: Optional callback function called each frame
            title: Window title (defaults to device name)
        """
        if not self.display_manager:
            self.display_manager = DisplayManager()
            
        if not title:
            title = self.__class__.__name__
            
        # Add display to manager
        self.display_manager.add_display(self.matrix)
        
        # Create window and run with enhanced update callback
        self.display_manager.create_window(title=title)
        
        def enhanced_update_callback():
            # Call user's update callback first
            if update_callback:
                update_callback()
            # Refresh the displayio content to the matrix
            if self.display:
                self.display.refresh()
        
        self.display_manager.run(enhanced_update_callback)
        
    def run_once(self):
        """Run a single update cycle without entering main loop."""
        if not self.display_manager:
            self.display_manager = DisplayManager()
            self.display_manager.add_display(self.matrix)
            
        self.display_manager.run_once()
        
    def save_screenshot(self, filename):
        """Save a screenshot of the display.
        
        Args:
            filename: Path to save screenshot
        """
        if self.matrix:
            self.matrix.save_screenshot(filename)
            
    def get_surface(self):
        """Get the pygame surface for this device.
        
        Returns:
            Pygame surface or None
        """
        if self.matrix:
            return self.matrix.get_surface()
        return None