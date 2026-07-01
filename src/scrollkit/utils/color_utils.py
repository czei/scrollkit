"""
Color utilities for handling color conversions and manipulations.
Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""

# Color name to (r, g, b) tuple mapping, for quick prototyping/tooling. Distinct
# from ColorUtils.colors below (Title-case names -> hex *strings*, used as
# settings defaults) -- different names, different value format, both kept.
NAMED_COLORS = {
    'red': (255, 0, 0),
    'green': (0, 255, 0),
    'blue': (0, 0, 255),
    'yellow': (255, 255, 0),
    'purple': (128, 0, 128),
    'cyan': (0, 255, 255),
    'white': (255, 255, 255),
    'orange': (255, 165, 0),
    'pink': (255, 192, 203),
    'magenta': (255, 0, 255),
    'lime': (0, 255, 0),
    'teal': (0, 128, 128),
    'navy': (0, 0, 128),
    'brown': (165, 42, 42),
    'gray': (128, 128, 128),
    'grey': (128, 128, 128),
    'black': (0, 0, 0),
}


__all__ = ['ColorUtils', 'NAMED_COLORS']

class ColorUtils:
    """Utilities for handling colors and conversions"""
    
    # Color definitions as a class variable
    colors = {
        "Red": "0xff0000",
        "Green": "0x00ff00",
        "Blue": "0x0000ff",
        "White": "0xffffff",
        "Black": "0x000000",
        "Purple": "0x800080",
        "Yellow": "0xffff00",
        "Orange": "0xffa500",
        "Pink": "0xffc0cb",
        "Old Lace": "0xfdf5e6"
    }

    @staticmethod
    def to_rgb(color_hex):
        """
        Convert a hex color string to an RGB tuple
        
        Args:
            color_hex: A hexadecimal color string (e.g., "0xRRGGBB")
            
        Returns:
            A tuple of (red, green, blue) values, each 0-255
        """
        color_int = int(color_hex, 16)
        r = (color_int >> 16) & 0xFF
        g = (color_int >> 8) & 0xFF
        b = color_int & 0xFF
        return r, g, b

    @staticmethod
    def from_rgb(r, g, b):
        """
        Convert RGB values to a hex color string
        
        Args:
            r: Red value (0-255)
            g: Green value (0-255)
            b: Blue value (0-255)
            
        Returns:
            A hexadecimal color string (e.g., "0xRRGGBB")
        """
        return f"0x{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def scale_color(color_hex, scale_factor):
        """
        Scale a color's brightness by a factor
        
        Args:
            color_hex: A hexadecimal color string (e.g., "0xRRGGBB")
            scale_factor: Factor to scale brightness by (0.0-1.0)
            
        Returns:
            A new hexadecimal color string with adjusted brightness
        """
        if color_hex == "0x000000":
            return color_hex
            
        r, g, b = ColorUtils.to_rgb(color_hex)
        r = int(r * scale_factor)
        g = int(g * scale_factor)
        b = int(b * scale_factor)
        
        # Ensure values stay within valid range
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        
        return ColorUtils.from_rgb(r, g, b)


    @staticmethod
    def hex_str_to_rgb(hex_string):
        # Remove leading characters
        if hex_string.startswith('0x'):
            hex_string = hex_string[2:]

        # Check that the input is valid
        if len(hex_string) != 6:
            raise ValueError('Input string should be in the format #RRGGBB')

        # Split the input into rgb components
        r, g, b = int(hex_string[0:2], 16), int(hex_string[2:4], 16), int(hex_string[4:6], 16)

        return r, g, b

    @staticmethod
    def pad_hex(num):
        hex_val = hex(num)[2:]  # remove '0x'
        # return hex_val.zfill(6)
        length = len(hex_val)
        for i in range(0, 6 - length):
            hex_val = "0" + hex_val
        return hex_val

    @staticmethod
    def hex_str_to_number(hex_string):
        return int(hex_string, 16)

    @staticmethod
    def number_to_hex_string(num):
        return hex(num)