# Copyright (c) 2024-2026 Michael Czeiszperger
"""Color manipulation utilities for LED simulation."""

def rgb565_to_rgb888(color565):
    """Convert RGB565 color to RGB888 (standard 24-bit RGB).
    
    Args:
        color565: 16-bit color value in RGB565 format
        
    Returns:
        Tuple of (r, g, b) values in 0-255 range
    """
    r = ((color565 >> 11) & 0x1F) << 3
    g = ((color565 >> 5) & 0x3F) << 2
    b = (color565 & 0x1F) << 3
    
    # Add the MSB bits to the LSB for better color accuracy
    r |= r >> 5
    g |= g >> 6
    b |= b >> 5
    
    return (r, g, b)


def rgb888_to_rgb565(r, g, b):
    """Convert RGB888 color to RGB565.
    
    Args:
        r: Red component (0-255)
        g: Green component (0-255)
        b: Blue component (0-255)
        
    Returns:
        16-bit color value in RGB565 format
    """
    return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)


def apply_brightness(color, brightness):
    """Apply brightness adjustment to RGB color.
    
    Args:
        color: Tuple of (r, g, b) values
        brightness: Float from 0.0 to 1.0
        
    Returns:
        Tuple of brightness-adjusted (r, g, b) values
    """
    return tuple(int(c * brightness) for c in color)


# Common color constants matching CircuitPython
BLACK = 0x0000
WHITE = 0xFFFF
RED = 0xF800
GREEN = 0x07E0
BLUE = 0x001F
CYAN = 0x07FF
MAGENTA = 0xF81F
YELLOW = 0xFFE0
ORANGE = 0xFD20
PURPLE = 0x8010