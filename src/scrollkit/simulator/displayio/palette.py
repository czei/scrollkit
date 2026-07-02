# Copyright (c) 2024-2026 Michael Czeiszperger
"""CircuitPython displayio.Palette equivalent."""

from ..core.color_utils import rgb565_to_rgb888, rgb888_to_rgb565


class Palette:
    """Color palette for indexed color display.
    
    Stores a collection of colors that can be referenced by index.
    Compatible with CircuitPython's displayio.Palette API.
    """
    
    def __init__(self, color_count):
        """Initialize palette with specified number of colors.
        
        Args:
            color_count: Maximum number of colors in palette
        """
        self._color_count = color_count
        self._colors = [None] * color_count
        self._transparent = [False] * color_count
        
    def __len__(self):
        """Get number of colors in palette."""
        return self._color_count
        
    def __setitem__(self, index, color):
        """Set a color in the palette.
        
        Args:
            index: Color index (0 to color_count-1)
            color: Color value as RGB565 integer or RGB888 tuple
        """
        if not 0 <= index < self._color_count:
            raise IndexError(f"Palette index {index} out of range")
            
        if isinstance(color, (list, tuple)):
            # Convert RGB888 tuple to RGB565
            if len(color) >= 3:
                self._colors[index] = rgb888_to_rgb565(color[0], color[1], color[2])
            else:
                raise ValueError("Color tuple must have at least 3 values")
        else:
            # displayio palettes take 24-bit RGB888 integers (0xRRGGBB). Do NOT
            # guess RGB565-vs-RGB888 by magnitude: colors with a zero red byte
            # (e.g. green 0x00FF00, blue 0x0000FF) are <= 0xFFFF and would be
            # mis-read as RGB565, rendering green as yellow, blue as purple, etc.
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
            self._colors[index] = rgb888_to_rgb565(r, g, b)
            
    def __getitem__(self, index):
        """Get a color from the palette.
        
        Args:
            index: Color index
            
        Returns:
            Color value as RGB565 integer
        """
        if not 0 <= index < self._color_count:
            raise IndexError(f"Palette index {index} out of range")
            
        color = self._colors[index]
        return 0 if color is None else color
        
    def make_transparent(self, index):
        """Make a palette entry transparent.
        
        Args:
            index: Color index to make transparent
        """
        if not 0 <= index < self._color_count:
            raise IndexError(f"Palette index {index} out of range")
            
        self._transparent[index] = True
        
    def make_opaque(self, index):
        """Make a palette entry opaque.
        
        Args:
            index: Color index to make opaque
        """
        if not 0 <= index < self._color_count:
            raise IndexError(f"Palette index {index} out of range")
            
        self._transparent[index] = False
        
    def is_transparent(self, index):
        """Check if a palette entry is transparent.
        
        Args:
            index: Color index to check
            
        Returns:
            True if transparent, False otherwise
        """
        if not 0 <= index < self._color_count:
            return False
            
        return self._transparent[index]
        
    def get_rgb888(self, index):
        """Get a color as RGB888 tuple.
        
        Args:
            index: Color index
            
        Returns:
            (r, g, b) tuple in 0-255 range
        """
        color565 = self[index]
        return rgb565_to_rgb888(color565)