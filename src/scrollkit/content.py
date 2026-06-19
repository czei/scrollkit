#!/usr/bin/env python3
"""Content module for SLDK.

Re-exports content classes from display.content for convenience.
"""

from __future__ import annotations

try:
    from typing import Any, Optional
except ImportError:  # CircuitPython has no 'typing' module
    pass

from .exceptions import ContentError
from .display.content import DisplayContent, StaticText, ScrollingText, ContentQueue

# Also create RainbowText for tests
class RainbowText(DisplayContent):
    """Rainbow text display content."""
    
    def __init__(self, text: str, x: int = 0, y: int = 0, rainbow_speed: float = 1.0, duration: Optional[float] = None) -> None:
        """Initialize rainbow text.
        
        Args:
            text: Text to display
            x: X coordinate
            y: Y coordinate  
            rainbow_speed: Speed of color cycling
            duration: Display duration in seconds
        """
        super().__init__(duration)
        self.text: str = text
        self.x: int = x
        self.y: int = y
        self.rainbow_speed: float = rainbow_speed
        self._hue_offset: float = 0.0
    
    async def render(self, display: Any) -> None:
        """Render rainbow text to display."""
        # Calculate rainbow color based on time
        hue = (self.elapsed * self.rainbow_speed + self._hue_offset) % 1.0
        color = self._hue_to_rgb(hue)
        
        await display.draw_text(self.text, self.x, self.y, color)
    
    def _hue_to_rgb(self, hue: float) -> int:
        """Convert hue to RGB color."""
        import math
        
        # Simple HSV to RGB conversion with full saturation and value
        h = hue * 6.0
        i = int(h)
        f = h - i
        
        if i == 0:
            r, g, b = 1.0, f, 0.0
        elif i == 1:
            r, g, b = 1.0 - f, 1.0, 0.0
        elif i == 2:
            r, g, b = 0.0, 1.0, f
        elif i == 3:
            r, g, b = 0.0, 1.0 - f, 1.0
        elif i == 4:
            r, g, b = f, 0.0, 1.0
        else:
            r, g, b = 1.0, 0.0, 1.0 - f
        
        # Convert to 24-bit RGB
        return (int(r * 255) << 16) | (int(g * 255) << 8) | int(b * 255)


__all__ = ['DisplayContent', 'StaticText', 'ScrollingText', 'RainbowText', 'ContentQueue']