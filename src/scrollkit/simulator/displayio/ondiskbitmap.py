"""CircuitPython displayio.OnDiskBitmap equivalent."""

from PIL import Image
import numpy as np
from .bitmap import Bitmap
from .palette import Palette
from ..core.color_utils import rgb888_to_rgb565


class OnDiskBitmap:
    """Load bitmap images from disk.
    
    Supports loading BMP and other image formats from disk.
    Creates a bitmap and palette from the loaded image.
    Compatible with CircuitPython's displayio.OnDiskBitmap API.
    """
    
    def __init__(self, file_path):
        """Initialize OnDiskBitmap from file.
        
        Args:
            file_path: Path to image file
        """
        self.file_path = file_path
        self._load_image()
        
    def _load_image(self):
        """Load image from disk and create bitmap/palette."""
        # Load image using PIL
        img = Image.open(self.file_path)
        
        # Convert to RGB if needed
        if img.mode != 'RGB':
            if img.mode == 'P':
                # Palette mode - extract palette
                img = img.convert('RGB')
            elif img.mode == 'RGBA':
                # Convert RGBA to RGB with white background
                background = Image.new('RGB', img.size, (255, 255, 255))
                background.paste(img, mask=img.split()[3])
                img = background
            else:
                img = img.convert('RGB')
                
        # Get image dimensions
        self.width = img.width
        self.height = img.height
        
        # Convert to numpy array
        img_array = np.array(img)
        
        # Create palette with unique colors (up to 256)
        unique_colors = {}
        color_index = 0
        
        # Create bitmap
        self.bitmap = Bitmap(self.width, self.height, 256)
        
        # Process pixels and build palette
        for y in range(self.height):
            for x in range(self.width):
                color = tuple(img_array[y, x])
                
                if color not in unique_colors:
                    if color_index < 256:
                        unique_colors[color] = color_index
                        color_index += 1
                    else:
                        # Find closest existing color
                        closest_idx = self._find_closest_color(color, unique_colors)
                        unique_colors[color] = closest_idx
                        
                self.bitmap[x, y] = unique_colors[color]
                
        # Create palette
        self.palette = Palette(len(unique_colors))
        for color, idx in unique_colors.items():
            self.palette[idx] = rgb888_to_rgb565(color[0], color[1], color[2])
            
    def _find_closest_color(self, target_color, color_dict):
        """Find closest color in palette.
        
        Args:
            target_color: Target RGB color tuple
            color_dict: Dictionary of existing colors
            
        Returns:
            Index of closest color
        """
        min_distance = float('inf')
        closest_idx = 0
        
        for color, idx in color_dict.items():
            # Calculate color distance (simple RGB distance)
            distance = sum((a - b) ** 2 for a, b in zip(target_color, color))
            if distance < min_distance:
                min_distance = distance
                closest_idx = idx
                
        return closest_idx
        
    @property
    def pixel_shader(self):
        """Get the palette (alias for CircuitPython compatibility)."""
        return self.palette