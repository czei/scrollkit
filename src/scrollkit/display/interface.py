"""Display interface for SLDK.

This provides the abstract interface that all display implementations must follow.
Compatible with both CircuitPython and desktop Python.
"""

from __future__ import annotations

try:
    from typing import Any, Optional
except ImportError:  # CircuitPython has no 'typing' module
    pass

from ..exceptions import DisplayError


class DisplayInterface:
    """Base interface for all display implementations."""

    @property
    def width(self) -> int:
        """Display width in pixels."""
        raise NotImplementedError("Subclass must implement width property")

    @property
    def height(self) -> int:
        """Display height in pixels."""
        raise NotImplementedError("Subclass must implement height property")

    async def initialize(self) -> None:
        """Initialize the display hardware or simulator."""
        raise NotImplementedError("Subclass must implement initialize()")

    async def clear(self) -> None:
        """Clear the display."""
        raise NotImplementedError("Subclass must implement clear()")

    async def show(self) -> None:
        """Update the physical display."""
        raise NotImplementedError("Subclass must implement show()")

    async def set_pixel(self, x: int, y: int, color: int) -> None:
        """Set a single pixel color.
        
        Args:
            x: X coordinate
            y: Y coordinate  
            color: Color as 24-bit RGB integer (0xRRGGBB)
        """
        raise NotImplementedError("Subclass must implement set_pixel()")
    
    async def fill(self, color: int) -> None:
        """Fill entire display with color.
        
        Args:
            color: Color as 24-bit RGB integer (0xRRGGBB)
        """
        # Default implementation using set_pixel
        for y in range(self.height):
            for x in range(self.width):
                await self.set_pixel(x, y, color)
    
    async def set_brightness(self, brightness: float) -> None:
        """Set display brightness.
        
        Args:
            brightness: Float between 0.0 and 1.0
        """
        raise NotImplementedError("Subclass must implement set_brightness()")
    
    # Higher-level convenience methods with default implementations
    
    async def draw_text(self, text: str, x: int = 0, y: int = 0, color: int = 0xFFFFFF, font: Any = None) -> None:
        """Draw text on display.
        
        Args:
            text: Text to display
            x: Starting X coordinate
            y: Starting Y coordinate
            color: Text color as 24-bit RGB
            font: Font to use (implementation specific)
        """
        # Subclasses should override with proper text rendering
        pass
    
    async def scroll_text(self, text: str, y: int = 0, color: int = 0xFFFFFF, speed: float = 0.05) -> None:
        """Scroll text across display.
        
        Args:
            text: Text to scroll
            y: Y coordinate for text
            color: Text color as 24-bit RGB
            speed: Scroll speed in seconds per pixel
        """
        # Subclasses should override with efficient scrolling
        pass