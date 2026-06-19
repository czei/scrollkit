"""Pixel buffer management for LED matrix simulation."""

import numpy as np


class PixelBuffer:
    """Manages the pixel data for an LED matrix.
    
    This class provides efficient storage and manipulation of pixel data
    using numpy arrays for performance.
    """
    
    def __init__(self, width, height):
        """Initialize pixel buffer.
        
        Args:
            width: Width of the matrix in pixels
            height: Height of the matrix in pixels
        """
        self.width = width
        self.height = height
        # Store pixels as RGB888 internally for better color accuracy
        self._buffer = np.zeros((height, width, 3), dtype=np.uint8)
        self._dirty = True
        self._dirty_region = None
        
    def set_pixel(self, x, y, color):
        """Set a single pixel color.
        
        Args:
            x: X coordinate (0 to width-1)
            y: Y coordinate (0 to height-1)
            color: Color as (r, g, b) tuple or single RGB value
        """
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
            
        if isinstance(color, (list, tuple)):
            self._buffer[y, x] = color[:3]
        else:
            # Assume it's a packed RGB value
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
            self._buffer[y, x] = [r, g, b]
            
        self._mark_dirty(x, y, x, y)
        
    def get_pixel(self, x, y):
        """Get a single pixel color.
        
        Args:
            x: X coordinate (0 to width-1)
            y: Y coordinate (0 to height-1)
            
        Returns:
            Color as (r, g, b) tuple
        """
        if not (0 <= x < self.width and 0 <= y < self.height):
            return (0, 0, 0)
        return tuple(self._buffer[y, x])
        
    def fill(self, color):
        """Fill entire buffer with a single color.
        
        Args:
            color: Color as (r, g, b) tuple or single RGB value
        """
        if isinstance(color, (list, tuple)):
            self._buffer[:] = color[:3]
        else:
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
            self._buffer[:] = [r, g, b]
            
        self._dirty = True
        self._dirty_region = None
        
    def clear(self):
        """Clear all pixels to black."""
        self._buffer.fill(0)
        self._dirty = True
        self._dirty_region = None
        
    def blit(self, source, x=0, y=0, key_color=None):
        """Copy pixels from another buffer.
        
        Args:
            source: Source PixelBuffer
            x: Destination X coordinate
            y: Destination Y coordinate
            key_color: Optional color to treat as transparent
        """
        # Calculate source and destination regions
        src_x = max(0, -x)
        src_y = max(0, -y)
        dst_x = max(0, x)
        dst_y = max(0, y)
        
        copy_width = min(source.width - src_x, self.width - dst_x)
        copy_height = min(source.height - src_y, self.height - dst_y)
        
        if copy_width <= 0 or copy_height <= 0:
            return
            
        # Copy the pixel data
        src_data = source._buffer[src_y:src_y + copy_height, src_x:src_x + copy_width]
        
        if key_color is not None:
            # Create mask for non-transparent pixels
            if isinstance(key_color, (list, tuple)):
                mask = np.any(src_data != key_color[:3], axis=2)
            else:
                r = (key_color >> 16) & 0xFF
                g = (key_color >> 8) & 0xFF
                b = key_color & 0xFF
                mask = np.any(src_data != [r, g, b], axis=2)
                
            # Only copy non-transparent pixels
            dst_slice = self._buffer[dst_y:dst_y + copy_height, dst_x:dst_x + copy_width]
            dst_slice[mask] = src_data[mask]
        else:
            # Copy all pixels
            self._buffer[dst_y:dst_y + copy_height, dst_x:dst_x + copy_width] = src_data
            
        self._mark_dirty(dst_x, dst_y, dst_x + copy_width - 1, dst_y + copy_height - 1)
        
    def get_buffer(self):
        """Get the raw numpy buffer.
        
        Returns:
            Numpy array of shape (height, width, 3)
        """
        return self._buffer
        
    def is_dirty(self):
        """Check if buffer has been modified.
        
        Returns:
            True if buffer has been modified since last clear_dirty()
        """
        return self._dirty
        
    def get_dirty_region(self):
        """Get the region that has been modified.
        
        Returns:
            Tuple of (x1, y1, x2, y2) or None if entire buffer is dirty
        """
        return self._dirty_region
        
    def clear_dirty(self):
        """Clear the dirty flag."""
        self._dirty = False
        self._dirty_region = None
        
    def _mark_dirty(self, x1, y1, x2, y2):
        """Mark a region as dirty.
        
        Args:
            x1, y1: Top-left corner
            x2, y2: Bottom-right corner
        """
        self._dirty = True
        
        if self._dirty_region is None:
            self._dirty_region = (x1, y1, x2, y2)
        else:
            # Expand existing dirty region
            old_x1, old_y1, old_x2, old_y2 = self._dirty_region
            self._dirty_region = (
                min(x1, old_x1),
                min(y1, old_y1),
                max(x2, old_x2),
                max(y2, old_y2)
            )
            
    def apply_brightness(self, brightness):
        """Apply brightness adjustment to all pixels.
        
        Args:
            brightness: Float from 0.0 to 1.0
        """
        self._buffer = (self._buffer * brightness).astype(np.uint8)
        self._dirty = True
        self._dirty_region = None