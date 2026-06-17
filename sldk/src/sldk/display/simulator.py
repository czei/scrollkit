"""Simulator display implementation for SLDK.

Provides display interface using the LED simulator for desktop development.
"""

from __future__ import annotations

import sys
from typing import Any, Optional

from ..exceptions import SimulatorError

# Verify we're NOT on CircuitPython
if hasattr(sys, 'implementation') and sys.implementation.name == 'circuitpython':
    raise ImportError("Simulator display cannot be used on CircuitPython")

try:
    import asyncio
except ImportError:
    raise ImportError("Simulator requires asyncio")

try:
    from sldk.simulator.devices.matrixportal_s3 import MatrixPortalS3
    from sldk.simulator import displayio
    from sldk.simulator.adafruit_bitmap_font import bitmap_font
    from sldk.simulator.adafruit_display_text.label import Label
    from sldk.simulator.terminalio import FONT as terminalio_FONT
    from sldk.simulator import terminalio as simulator_terminalio
    terminalio = simulator_terminalio
    terminalio.FONT = terminalio_FONT
except ImportError:
    raise ImportError(
        "SLDK simulator not available. "
        "Ensure all SLDK components are properly installed."
    )

from .interface import DisplayInterface


class SimulatorDisplay(DisplayInterface):
    """Simulator display implementation for desktop development."""
    
    def __init__(self, width: int = 64, height: int = 32, scale: int = 10):
        """Initialize simulator display.
        
        Args:
            width: Display width in pixels
            height: Display height in pixels
            scale: Scale factor for window size
        """
        self._width: int = width
        self._height: int = height
        self._scale: int = scale
        self._brightness: float = 0.3
        
        # Simulator components
        self.device: Any = None
        self.matrix: Any = None
        self.display: Any = None
        
        # Display groups
        self.main_group: Any = None
        self._initialized: bool = False
        
        # Default font
        self.font: Any = terminalio.FONT
        
        # For pygame window
        self._window_created: bool = False
        
    @property
    def width(self) -> int:
        """Display width in pixels."""
        return self._width
        
    @property 
    def height(self) -> int:
        """Display height in pixels."""
        return self._height
    
    async def initialize(self) -> None:
        """Initialize the display simulator."""
        if self._initialized:
            return
            
        try:
            # Create simulator device
            self.device = MatrixPortalS3(
                width=self._width,
                height=self._height
            )
            self.device.initialize()
            
            # Get display components
            self.matrix = self.device.matrix
            self.display = self.device.display
            
            # Set up display groups
            self.main_group = displayio.Group()
            self.display.root_group = self.main_group
            
            # Initialize surface
            if hasattr(self.matrix, 'initialize_surface'):
                self.matrix.initialize_surface()
            
            # Set initial brightness
            await self.set_brightness(self._brightness)
            
            self._initialized = True
            print("Simulator display initialized")
            
        except (ImportError, OSError, SimulatorError) as e:
            print(f"Failed to initialize simulator: {e}")
            raise
    
    async def clear(self) -> None:
        """Clear the display."""
        # Hide all groups
        for child in self.main_group:
            if hasattr(child, 'hidden'):
                child.hidden = True
        
        # Fill with black
        if self.matrix and hasattr(self.matrix, 'fill'):
            self.matrix.fill(0x000000)
    
    async def show(self) -> bool:
        """Update the simulated display."""
        if not self.display:
            return True
            
        try:
            import pygame
            
            # Create window if needed
            if not self._window_created:
                await self.create_window()
            
            # Handle events
            if pygame.get_init() and pygame.display.get_surface():
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            return False
            
            # Update display
            self.display.refresh(minimum_frames_per_second=0)
            
            # Render to pygame
            if hasattr(self.matrix, 'render'):
                self.matrix.render()
                
                # Copy matrix surface to main window
                if pygame.get_init() and pygame.display.get_surface():
                    screen = pygame.display.get_surface()
                    matrix_surface = self.matrix.get_surface()
                    if matrix_surface:
                        # Clear screen first
                        screen.fill((0, 0, 0))
                        # Blit matrix surface to screen
                        screen.blit(matrix_surface, (0, 0))
                        # Debug: Draw a test pattern to ensure window is working
                        pygame.draw.circle(screen, (255, 0, 0), (10, 10), 5)  # Red dot in corner
                    else:
                        # No matrix surface, draw debug pattern
                        screen.fill((50, 0, 50))  # Purple background
                        pygame.draw.rect(screen, (255, 255, 0), (50, 50, 100, 50))  # Yellow rect
            
            if pygame.get_init() and pygame.display.get_surface():
                pygame.display.flip()
            
            # Small yield for responsiveness
            await asyncio.sleep(0.001)
            
        except ImportError:
            # Pygame not available, just refresh
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
    
    async def set_brightness(self, brightness: float) -> None:
        """Set display brightness.
        
        Args:
            brightness: Float between 0.0 and 1.0
        """
        self._brightness = max(0.0, min(1.0, brightness))
        
        if self.display:
            try:
                self.display.brightness = self._brightness
            except (AttributeError, TypeError) as e:
                print(f"Failed to set brightness: {e}")
    
    async def draw_text(self, text: str, x: int = 0, y: int = 0, color: int = 0xFFFFFF, font: Any = None) -> None:
        """Draw text on display.
        
        Args:
            text: Text to display
            x: Starting X coordinate
            y: Starting Y coordinate
            color: Text color as 24-bit RGB
            font: Font to use (uses default if None)
        """
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
    
    async def scroll_text(self, text: str, y: int = 0, color: int = 0xFFFFFF, speed: float = 0.05) -> None:
        """Scroll text across display.
        
        Args:
            text: Text to scroll
            y: Y coordinate for text
            color: Text color as 24-bit RGB
            speed: Scroll speed in seconds per pixel
        """
        # Create label
        label = Label(self.font, text=text, color=color)
        label.x = self._width  # Start from right edge
        label.y = y
        
        # Create group
        scroll_group = displayio.Group()
        scroll_group.append(label)
        self.main_group.append(scroll_group)
        
        # Estimate text width
        if hasattr(label, 'bounding_box') and label.bounding_box:
            text_width = label.bounding_box[2]
        else:
            text_width = len(text) * 6  # Fallback estimate
        
        # Scroll until text is off screen
        while label.x > -text_width:
            label.x -= 1
            await self.show()
            await asyncio.sleep(speed)
        
        # Remove the group
        self.main_group.remove(scroll_group)
    
    async def create_window(self, title: str = "SLDK Simulator") -> None:
        """Create the simulator window.
        
        Args:
            title: Window title
        """
        if self._window_created:
            return
            
        try:
            import pygame
            import os
            
            # Force window to appear with environment variables
            os.environ['SDL_VIDEO_WINDOW_POS'] = '100,100'
            os.environ['SDL_VIDEO_CENTERED'] = '1'
            
            if not pygame.get_init():
                pygame.init()
            
            # Calculate window size
            if hasattr(self.matrix, 'surface_width'):
                width = self.matrix.surface_width
                height = self.matrix.surface_height
            else:
                width = self._width * self._scale
                height = self._height * self._scale
            
            print(f"Creating pygame window: {width}x{height}")
            
            # Create window with specific flags
            screen = pygame.display.set_mode((width, height), pygame.SHOWN)
            pygame.display.set_caption(title)
            
            # Force window to front
            screen.fill((50, 50, 50))  # Dark gray background
            pygame.display.flip()
            
            print(f"Window created successfully: {title}")
            self._window_created = True
            
        except ImportError:
            # Pygame not available
            print("Pygame not available for window creation")
            pass
    
    async def run_event_loop(self) -> None:
        """Run the display event loop.
        
        This keeps the simulator window responsive.
        """
        while True:
            result = await self.show()
            if not result:
                break
            await asyncio.sleep(0.01)  # ~100 FPS max