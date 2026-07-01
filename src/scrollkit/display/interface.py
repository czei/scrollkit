# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Display interface for SLDK.

This provides the abstract interface that all display implementations must follow.
Compatible with both CircuitPython and desktop Python.
"""

from __future__ import annotations

try:
    from typing import Any, Optional
except ImportError:  # CircuitPython has no 'typing' module
    pass


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

    async def show(self) -> bool:
        """Update the physical display.

        Returns False when the user closed the simulator window (so the app loop
        can shut down); True otherwise.
        """
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
        # Not a silent no-op: a DisplayInterface that can't draw text is a bug,
        # and the concrete displays (Unified/Simulator via GraphicsMixin) all
        # override this.
        raise NotImplementedError("Subclass must implement draw_text()")

    # --- bounded painters + graphics bridge (see display/_graphics.py) --------
    # Real displays mix in GraphicsMixin, which provides concrete implementations
    # backed by C bulk ops (bitmaptools). These stubs document the contract for
    # any other DisplayInterface.

    async def fill_rect(self, x: int, y: int, w: int, h: int, color: int) -> None:
        """Fill a bounded rectangle with ``color`` via a C bulk op (no full loop)."""
        raise NotImplementedError("Subclass must implement fill_rect()")

    async def fill_span(self, y: int, x0: int, x1: int, color: int) -> None:
        """Fill the single-row span ``[x0, x1)`` with ``color``."""
        raise NotImplementedError("Subclass must implement fill_span()")

    async def clear_rect(self, x: int, y: int, w: int, h: int) -> None:
        """Clear a bounded rectangle back to the background."""
        raise NotImplementedError("Subclass must implement clear_rect()")

    def measure_text(self, text: str, font: Any = None) -> int:
        """Rendered pixel width of ``text`` (summed glyph advances; not len*6)."""
        return len(text) * 6   # coarse fallback; real displays override

    @property
    def gfx(self) -> Any:
        """Platform-resolved graphics namespace (Bitmap/Palette/TileGrid/Group/
        bitmaptools), cached per display."""
        raise NotImplementedError("Subclass must implement gfx")

    def add_layer(self, tilegrid: Any) -> None:
        """Composite a TileGrid above content (persistent across frames)."""
        raise NotImplementedError("Subclass must implement add_layer()")

    def remove_layer(self, tilegrid: Any) -> None:
        """Remove a layer added via add_layer()."""
        raise NotImplementedError("Subclass must implement remove_layer()")