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

    # NOTE: the old static conversion helpers (to_rgb/from_rgb/scale_color/
    # hex_str_to_rgb/pad_hex/hex_str_to_number/number_to_hex_string) were
    # removed as dead code — zero callers anywhere, including tests and the
    # app. The modern int-based color API is scrollkit.display.colors. This
    # class survives only to carry the hex-string `colors` table the settings
    # schema consumes.