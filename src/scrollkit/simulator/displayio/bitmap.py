"""CircuitPython displayio.Bitmap equivalent."""

import numpy as np


class Bitmap:
    """Bitmap for pixel data storage.
    
    Stores pixel data as palette indices. Each pixel is an index
    into a Palette object that defines the actual colors.
    Compatible with CircuitPython's displayio.Bitmap API.
    """
    
    def __init__(self, width, height, value_count):
        """Initialize bitmap with specified dimensions.
        
        Args:
            width: Bitmap width in pixels
            height: Bitmap height in pixels
            value_count: Number of different values each pixel can have
        """
        self.width = width
        self.height = height
        self.value_count = value_count
        
        # Determine data type based on value count
        if value_count <= 2:
            self._bits_per_value = 1
            dtype = np.uint8
        elif value_count <= 4:
            self._bits_per_value = 2
            dtype = np.uint8
        elif value_count <= 16:
            self._bits_per_value = 4
            dtype = np.uint8
        elif value_count <= 256:
            self._bits_per_value = 8
            dtype = np.uint8
        else:
            self._bits_per_value = 16
            dtype = np.uint16
            
        # Create buffer to store pixel values
        self._buffer = np.zeros((height, width), dtype=dtype)
        
    def __setitem__(self, index, value):
        """Set pixel value.
        
        Args:
            index: (x, y) tuple or flat index
            value: Palette index value
        """
        if isinstance(index, tuple):
            x, y = index
            if not (0 <= x < self.width and 0 <= y < self.height):
                raise IndexError(f"Pixel index ({x}, {y}) out of bounds")
        else:
            # Convert flat index to x, y
            y = index // self.width
            x = index % self.width
            if not (0 <= index < self.width * self.height):
                raise IndexError(f"Pixel index {index} out of bounds")
                
        if not 0 <= value < self.value_count:
            raise ValueError(f"Pixel value {value} out of range")
            
        self._buffer[y, x] = value
        
    def __getitem__(self, index):
        """Get pixel value.
        
        Args:
            index: (x, y) tuple or flat index
            
        Returns:
            Palette index value
        """
        if isinstance(index, tuple):
            x, y = index
            if not (0 <= x < self.width and 0 <= y < self.height):
                raise IndexError(f"Pixel index ({x}, {y}) out of bounds")
        else:
            # Convert flat index to x, y
            y = index // self.width
            x = index % self.width
            if not (0 <= index < self.width * self.height):
                raise IndexError(f"Pixel index {index} out of bounds")
                
        return int(self._buffer[y, x])
        
    def fill(self, value):
        """Fill entire bitmap with a single value.
        
        Args:
            value: Palette index value to fill with
        """
        if not 0 <= value < self.value_count:
            raise ValueError(f"Pixel value {value} out of range")
            
        self._buffer.fill(value)
        
    def blit(self, x, y, source_bitmap, *, x1=0, y1=0, x2=None, y2=None, skip_index=None):
        """Copy pixels from another bitmap.
        
        Args:
            x: Destination X coordinate
            y: Destination Y coordinate
            source_bitmap: Source Bitmap to copy from
            x1: Source left edge (default 0)
            y1: Source top edge (default 0)
            x2: Source right edge (default source width)
            y2: Source bottom edge (default source height)
            skip_index: Palette index to treat as transparent
        """
        # Set default source bounds
        if x2 is None:
            x2 = source_bitmap.width
        if y2 is None:
            y2 = source_bitmap.height
            
        # Calculate copy region
        src_width = x2 - x1
        src_height = y2 - y1
        
        # Clip to destination bounds
        copy_width = min(src_width, self.width - x)
        copy_height = min(src_height, self.height - y)
        
        if copy_width <= 0 or copy_height <= 0:
            return
            
        # Clip source region
        if x < 0:
            x1 -= x
            copy_width += x
            x = 0
        if y < 0:
            y1 -= y
            copy_height += y
            y = 0
            
        # Copy pixel data
        src_data = source_bitmap._buffer[y1:y1 + copy_height, x1:x1 + copy_width]
        
        if skip_index is not None:
            # Copy only non-transparent pixels
            mask = src_data != skip_index
            dst_slice = self._buffer[y:y + copy_height, x:x + copy_width]
            dst_slice[mask] = src_data[mask]
        else:
            # Copy all pixels
            self._buffer[y:y + copy_height, x:x + copy_width] = src_data
            
    @property
    def bits_per_value(self):
        """Get the number of bits per pixel value."""
        return self._bits_per_value