"""Unified display implementation for SLDK.

Provides a unified interface that works on both CircuitPython hardware
and desktop development environments using the LED simulator.
"""

from __future__ import annotations

import sys
import gc
from typing import Any, Dict, Optional

from ..exceptions import DisplayError, SimulatorError

try:
    # Desktop Python
    import asyncio
except ImportError:
    # CircuitPython
    import asyncio

# Platform detection
IS_CIRCUITPYTHON = hasattr(sys, 'implementation') and sys.implementation.name == 'circuitpython'

# Conditional imports based on platform
if IS_CIRCUITPYTHON:
    import displayio
    import terminalio
    try:
        from adafruit_bitmap_font import bitmap_font
    except ImportError:
        bitmap_font = None
    from adafruit_display_text.label import Label
else:
    # SLDK Simulator imports - these will be optional
    try:
        from sldk.simulator.devices.matrixportal_s3 import MatrixPortalS3
        from sldk.simulator import displayio
        from sldk.simulator.adafruit_bitmap_font import bitmap_font
        from sldk.simulator.adafruit_display_text.label import Label
        from sldk.simulator.terminalio import FONT as terminalio_FONT
        # Create module alias for consistency
        from sldk.simulator import terminalio as simulator_terminalio
        terminalio = simulator_terminalio
        terminalio.FONT = terminalio_FONT
        LED_SIMULATOR_AVAILABLE = True
    except ImportError:
        LED_SIMULATOR_AVAILABLE = False
        displayio = None
        terminalio = None
        bitmap_font = None
        Label = None

from .interface import DisplayInterface


class UnifiedDisplay(DisplayInterface):
    """Unified display that auto-detects hardware vs simulator."""
    
    def __init__(self, width: int = 64, height: int = 32):
        """Initialize unified display.
        
        Args:
            width: Display width in pixels
            height: Display height in pixels
        """
        self._width: int = width
        self._height: int = height
        self._brightness: float = 0.3
        
        # Platform specific components
        self.hardware: Any = None
        self.matrix: Any = None
        self.display: Any = None
        self.device: Any = None  # For simulator
        
        # Display components
        self.main_group: Any = None
        self._initialized: bool = False
        
        # For text rendering
        self.font: Any = None
        self._text_labels: Dict[str, Any] = {}  # Cache for text labels
        
    @property
    def width(self) -> int:
        """Display width in pixels."""
        return self._width
        
    @property
    def height(self) -> int:
        """Display height in pixels."""
        return self._height
    
    async def initialize(self) -> None:
        """Initialize the display hardware or simulator."""
        if self._initialized:
            return
            
        try:
            # Platform-specific hardware initialization
            self._initialize_hardware()
            
            # Set up display groups
            self.main_group = displayio.Group()
            self.display.root_group = self.main_group
            
            # Load default font
            self.font = terminalio.FONT if terminalio else None
            
            # Set initial brightness
            await self.set_brightness(self._brightness)
            
            self._initialized = True
            print(f"Display initialized ({'CircuitPython' if IS_CIRCUITPYTHON else 'Simulator'})")
            
        except (DisplayError, ImportError, OSError) as e:
            print(f"Failed to initialize display: {e}")
            raise
    
    def _initialize_hardware(self) -> None:
        """Initialize the display hardware/simulator."""
        if IS_CIRCUITPYTHON:
            # Try hardware auto-detection first
            try:
                from .devices import detect_hardware
                hardware_display = detect_hardware(
                    width=self._width, 
                    height=self._height
                )
                
                if hardware_display:
                    self.hardware = hardware_display
                    self.matrix = hardware_display
                    self.display = hardware_display.display if hasattr(hardware_display, 'display') else hardware_display
                    return
            except ImportError:
                pass
            
            # Fallback to MatrixPortal Matrix
            try:
                from adafruit_matrixportal.matrix import Matrix
                self.hardware = Matrix(width=self._width, height=self._height)
                self.display = self.hardware.display
                self.matrix = self.hardware
            except ImportError:
                raise ImportError("No compatible hardware found")
        else:
            if not LED_SIMULATOR_AVAILABLE:
                raise ImportError(
                    "LED simulator not available. "
                    "Install with: pip install sldk[simulator]"
                )
            
            # Create MatrixPortal S3 device
            self.device = MatrixPortalS3(width=self._width, height=self._height)
            self.device.initialize()
            
            # Get references to the display components
            self.matrix = self.device.matrix
            self.display = self.device.display
            self.hardware = self.device  # For compatibility
            
            # Initialize surface for simulator
            if hasattr(self.matrix, 'initialize_surface'):
                self.matrix.initialize_surface()
    
    async def clear(self) -> None:
        """Clear the display."""
        # Hide all groups
        for child in self.main_group:
            if hasattr(child, 'hidden'):
                child.hidden = True
        
        # Clear any pixel data
        if self.matrix and hasattr(self.matrix, 'fill'):
            self.matrix.fill(0x000000)
    
    async def show(self) -> bool:
        """Update the physical display."""
        if IS_CIRCUITPYTHON:
            if self.hardware:
                self.hardware.display.refresh(minimum_frames_per_second=0)
            return True
        else:
            # Simulator needs pygame event handling
            return await self._update_simulator()
    
    async def _update_simulator(self) -> bool:
        """Update the simulator display."""
        if not self.display:
            return True
            
        try:
            import pygame
            
            # Check if pygame is initialized
            if not pygame.get_init():
                self.display.refresh(minimum_frames_per_second=0)
                return True
            
            # Check if window exists
            if pygame.display.get_surface() is None:
                self.display.refresh(minimum_frames_per_second=0)
                return True
            
            # Handle events to keep window responsive
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return False
            
            # Update the display
            self.display.refresh(minimum_frames_per_second=0)
            
            # Update pygame display - use same pattern as DisplayManager
            screen = pygame.display.get_surface()
            if screen and hasattr(self.matrix, 'render') and hasattr(self.matrix, 'get_surface'):
                # Clear screen
                screen.fill((0, 0, 0))
                
                # Render matrix and blit to screen
                self.matrix.render()
                matrix_surface = self.matrix.get_surface()
                if matrix_surface:
                    screen.blit(matrix_surface, (0, 0))
                        
            pygame.display.flip()
            
            # Small yield for responsiveness
            await asyncio.sleep(0.001)
            
        except ImportError:
            # Pygame not available
            if self.display:
                self.display.refresh(minimum_frames_per_second=0)
        
        return True
    
    async def set_pixel(self, x: int, y: int, color: int) -> None:
        """Set a single pixel color.
        
        Args:
            x: X coordinate
            y: Y coordinate
            color: Color as 24-bit RGB integer
        """
        if self.matrix and 0 <= x < self._width and 0 <= y < self._height:
            # Try different methods to set pixel
            if hasattr(self.matrix, 'set_pixel'):
                self.matrix.set_pixel(x, y, color)
            elif hasattr(self.matrix, '__setitem__'):
                try:
                    self.matrix[x, y] = color
                except (TypeError, AttributeError):
                    # Try alternative indexing
                    try:
                        self.matrix[y][x] = color
                    except (TypeError, AttributeError, IndexError):
                        # Fallback - print for debugging
                        print(f"Cannot set pixel at ({x}, {y}) to {color:06X}")
            else:
                print(f"Matrix object has no set_pixel method: {type(self.matrix)}")
    
    async def fill(self, color: int) -> None:
        """Fill entire display with color.
        
        Args:
            color: Color as 24-bit RGB integer
        """
        if self.matrix and hasattr(self.matrix, 'fill'):
            self.matrix.fill(color)
        else:
            # Fallback to pixel-by-pixel
            await super().fill(color)
    
    async def set_brightness(self, brightness: float) -> None:
        """Set display brightness.
        
        Args:
            brightness: Float between 0.0 and 1.0
        """
        self._brightness = max(0.0, min(1.0, brightness))
        
        if self.display:
            try:
                if IS_CIRCUITPYTHON:
                    self.hardware.display.brightness = self._brightness
                else:
                    self.display.brightness = self._brightness
            except (AttributeError, TypeError) as e:
                print(f"Failed to set brightness: {e}")
    
    async def draw_text(self, text: str, x: int = 0, y: int = 0, color: int = 0xFFFFFF, font: Any = None) -> None:
        """Draw text on display using displayio labels.
        
        Args:
            text: Text to display
            x: Starting X coordinate
            y: Starting Y coordinate
            color: Text color as 24-bit RGB
            font: Font to use (uses default if None)
        """
        if not Label:
            # Label class not available
            return
            
        # Use provided font or default
        if font is None:
            font = self.font
        if font is None:
            return
            
        # Create unique key for this text label
        label_key = f"{text}_{x}_{y}"
        
        # Create or update label
        if label_key in self._text_labels:
            label = self._text_labels[label_key]
            label.text = text
            label.color = color
        else:
            label = Label(font, text=text, color=color)
            label.x = x
            label.y = y
            self._text_labels[label_key] = label
            
            # Create a group for this label
            label_group = displayio.Group()
            label_group.append(label)
            self.main_group.append(label_group)
    
    def _convert_color(self, color: Any) -> int:
        """Convert color to platform-appropriate format.
        
        Args:
            color: Color value (int or hex string)
            
        Returns:
            Integer color value
        """
        if isinstance(color, str):
            return int(color, 16)
        return int(color)
    
    async def create_window(self, title: str = "SLDK Display") -> None:
        """Create display window (simulator only).
        
        Args:
            title: Window title
        """
        if IS_CIRCUITPYTHON:
            # No window needed on hardware
            return
            
        try:
            import pygame
            
            if not pygame.get_init():
                pygame.init()
            
            # Create window
            if hasattr(self.matrix, 'surface_width'):
                width = self.matrix.surface_width
                height = self.matrix.surface_height
            else:
                # Default scale of 10x
                width = self._width * 10
                height = self._height * 10
                
            screen = pygame.display.set_mode((width, height))
            pygame.display.set_caption(title)
            
        except ImportError:
            pass  # Pygame not available
    
    async def run_event_loop(self) -> None:
        """Run the display event loop (simulator only).
        
        This keeps the simulator window responsive.
        Should be run as a background task.
        """
        if IS_CIRCUITPYTHON:
            return
            
        while True:
            result = await self.show()
            if not result:
                break
            await asyncio.sleep(0.01)  # ~100 FPS max