# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Font scaling system for PyLEDSimulator.

This module provides different fonts for different scale factors.
Scale 1: viii.bdf (default)
Scale 2: Arial_16.bdf
"""

import os
from ..adafruit_bitmap_font import bitmap_font

class FontScaler:
    """Manages fonts for different scale factors."""
    
    def __init__(self):
        """Initialize the font scaler with default fonts."""
        self._fonts = {}
        self._load_fonts()
    
    def _load_fonts(self):
        """Load fonts for different scales."""
        base_path = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        fonts_path = os.path.join(base_path, 'fonts')
        
        # Scale 1: viii.bdf (already loaded as default FONT)
        from .. import terminalio
        self._fonts[1] = terminalio.FONT
        
        # Scale 2: Junction_regular_24.bdf
        junction_path = os.path.join(fonts_path, 'Arial_16.bdf')
        try:
            self._fonts[2] = bitmap_font.load_font(junction_path)
        except Exception:
            # Fallback to scale 1 font if loading fails
            self._fonts[2] = self._fonts[1]
    
    def get_font_for_scale(self, scale):
        """Get the appropriate font for the given scale.
        
        Args:
            scale: The scale factor (1 or 2)
            
        Returns:
            The appropriate font object
        """
        # Default to scale 1 font for any unrecognized scale
        return self._fonts.get(scale, self._fonts.get(1))

# Global font scaler instance
_font_scaler = FontScaler()

def get_font_for_scale(scale):
    """Get the appropriate font for the given scale.
    
    Args:
        scale: The scale factor (1 or 2)
        
    Returns:
        The appropriate font object
    """
    return _font_scaler.get_font_for_scale(scale)