"""BDF font loading and rendering for bitmap displays."""

import os
from ..displayio import Bitmap, Palette
from .glyph_cache import GlyphCache


class BitmapFont:
    """Bitmap font for rendering text on displays.
    
    Loads and renders BDF (Bitmap Distribution Format) fonts.
    Compatible with CircuitPython's adafruit_bitmap_font API.
    """
    
    def __init__(self):
        """Initialize empty bitmap font."""
        self.name = None
        self.size = 0
        self.height = 0
        self.ascent = 0
        self.descent = 0
        # Global font metrics from BDF
        self.font_bounding_box = None  # (width, height, x_offset, y_offset)
        self.font_ascent = None   # From FONT_ASCENT property
        self.font_descent = None  # From FONT_DESCENT property
        self.baseline_to_top = 0  # Distance from baseline to top of font bounding box
        self.glyphs = {}
        self.default_char = ord('?')
        self._glyph_cache = GlyphCache()
        
    def load_font(self, filename):
        """Load a BDF font file.
        
        Args:
            filename: Path to BDF font file
        """
        self.glyphs.clear()
        self._glyph_cache.clear()
        
        with open(filename, 'r', encoding='latin-1') as f:
            self._parse_bdf(f)
            
    def _parse_bdf(self, file):
        """Parse BDF font file.
        
        Args:
            file: Open file object
        """
        current_char = None
        current_bitmap = []
        current_dwidth = None
        in_bitmap = False
        in_properties = False
        
        for line in file:
            line = line.strip()
            
            if line.startswith('FONT '):
                self.name = line[5:].strip()
            elif line.startswith('SIZE'):
                parts = line.split()
                if len(parts) >= 2:
                    self.size = int(parts[1])
            elif line.startswith('FONTBOUNDINGBOX'):
                parts = line.split()
                if len(parts) >= 5:
                    bbox_width = int(parts[1])
                    bbox_height = int(parts[2])
                    bbox_x_offset = int(parts[3])
                    bbox_y_offset = int(parts[4])
                    self.font_bounding_box = (bbox_width, bbox_height, bbox_x_offset, bbox_y_offset)
                    # Set initial values (may be overridden by FONT_ASCENT/FONT_DESCENT)
                    self.height = bbox_height
                    self.ascent = bbox_height + bbox_y_offset  # Distance from baseline to top
                    self.descent = -bbox_y_offset  # Distance from baseline to bottom
                    self.baseline_to_top = self.ascent
            elif line.startswith('STARTPROPERTIES'):
                in_properties = True
            elif line.startswith('ENDPROPERTIES'):
                in_properties = False
            elif in_properties and line.startswith('FONT_ASCENT'):
                parts = line.split()
                if len(parts) >= 2:
                    self.font_ascent = int(parts[1])
                    self.ascent = self.font_ascent
                    self.baseline_to_top = self.font_ascent
            elif in_properties and line.startswith('FONT_DESCENT'):
                parts = line.split()
                if len(parts) >= 2:
                    self.font_descent = int(parts[1])
                    self.descent = self.font_descent
                    # Update total height if we have both ascent and descent
                    if self.font_ascent is not None:
                        self.height = self.font_ascent + self.font_descent
            elif line.startswith('STARTCHAR'):
                current_char = None
                current_bitmap = []
                current_dwidth = None
            elif line.startswith('ENCODING'):
                current_char = int(line.split()[1])
            elif line.startswith('DWIDTH'):
                # Parse device width (advance width for kerning)
                parts = line.split()
                if len(parts) >= 2:
                    current_dwidth = int(parts[1])
            elif line.startswith('BBX'):
                if current_char is not None:
                    parts = line.split()
                    if len(parts) >= 5:
                        char_width = int(parts[1])
                        char_height = int(parts[2])
                        x_offset = int(parts[3])
                        y_offset = int(parts[4])
                        
                        if current_char not in self.glyphs:
                            self.glyphs[current_char] = {
                                'width': char_width,
                                'height': char_height,
                                'x_offset': x_offset,
                                'y_offset': y_offset,
                                'dwidth': current_dwidth if current_dwidth is not None else char_width,  # Use DWIDTH or fallback to bitmap width
                                'bitmap': []
                            }
            elif line.startswith('BITMAP'):
                in_bitmap = True
                current_bitmap = []
            elif line.startswith('ENDCHAR'):
                if current_char is not None and current_char in self.glyphs:
                    self.glyphs[current_char]['bitmap'] = current_bitmap
                in_bitmap = False
                current_char = None
            elif in_bitmap and current_char is not None:
                # Parse hex bitmap data
                current_bitmap.append(line)
                
    def get_glyph(self, char):
        """Get glyph information for a character.
        
        Args:
            char: Character or character code
            
        Returns:
            Dictionary with glyph information or None
        """
        if isinstance(char, str):
            char_code = ord(char)
        else:
            char_code = char
            
        # Check cache first
        cached = self._glyph_cache.get(char_code)
        if cached:
            return cached
            
        # Get glyph data
        if char_code not in self.glyphs:
            # Use default character
            char_code = self.default_char
            if char_code not in self.glyphs:
                return None
                
        glyph_data = self.glyphs[char_code]
        
        # Create bitmap for glyph
        width = glyph_data['width']
        height = glyph_data['height']
        
        if width == 0 or height == 0:
            # Handle zero-size glyphs (like spaces) - they still need DWIDTH for advancement
            result = {
                'bitmap': None,  # No bitmap to render
                'width': width,
                'height': height,
                'dx': glyph_data['dwidth'],  # Still use DWIDTH for spacing
                'dy': 0,
                'x_offset': glyph_data['x_offset'],
                'y_offset': glyph_data['y_offset']
            }
            # Cache the result
            self._glyph_cache.put(char_code, None, result)
            return result
            
        # Create bitmap with 2 colors (0=background, 1=foreground)
        bitmap = Bitmap(width, height, 2)
        
        # Parse hex bitmap data
        for y, hex_line in enumerate(glyph_data['bitmap']):
            if y >= height:
                break
                
            # Convert hex to binary
            byte_width = (width + 7) // 8
            hex_line = hex_line.ljust(byte_width * 2, '0')
            
            for byte_idx in range(0, len(hex_line), 2):
                if byte_idx // 2 >= byte_width:
                    break
                    
                byte_val = int(hex_line[byte_idx:byte_idx + 2], 16)
                
                for bit in range(8):
                    x = (byte_idx // 2) * 8 + bit
                    if x >= width:
                        break
                        
                    if byte_val & (0x80 >> bit):
                        bitmap[x, y] = 1
                    else:
                        bitmap[x, y] = 0
                        
        # Create result dictionary
        result = {
            'bitmap': bitmap,
            'width': width,
            'height': height,
            'dx': glyph_data['dwidth'],  # Use DWIDTH for proper kerning/spacing
            'dy': 0,
            'x_offset': glyph_data['x_offset'],
            'y_offset': glyph_data['y_offset']
        }
        
        # Cache the result
        self._glyph_cache.put(char_code, bitmap, result)
        
        return result
        
    def get_bounding_box(self):
        """Get font bounding box.
        
        Returns:
            Tuple of (width, height, x_offset, y_offset)
        """
        # Calculate from all glyphs
        min_x = 0
        max_x = 0
        min_y = 0
        max_y = 0
        
        for glyph_data in self.glyphs.values():
            x_offset = glyph_data['x_offset']
            y_offset = glyph_data['y_offset']
            width = glyph_data['width']
            height = glyph_data['height']
            
            min_x = min(min_x, x_offset)
            max_x = max(max_x, x_offset + width)
            min_y = min(min_y, y_offset)
            max_y = max(max_y, y_offset + height)
            
        return (max_x - min_x, max_y - min_y, min_x, min_y)
        

def load_font(filename, bitmap_class=Bitmap):
    """Load a font file.
    
    Args:
        filename: Path to font file
        bitmap_class: Bitmap class to use (for compatibility)
        
    Returns:
        BitmapFont instance
    """
    font = BitmapFont()
    
    # Check if file exists, otherwise try to find it in package fonts
    if not os.path.exists(filename):
        # Try package fonts directory
        package_dir = os.path.dirname(os.path.dirname(__file__))
        fonts_dir = os.path.join(package_dir, 'fonts')
        filename = os.path.join(fonts_dir, os.path.basename(filename))
        
    font.load_font(filename)
    return font