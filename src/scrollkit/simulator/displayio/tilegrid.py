"""CircuitPython displayio.TileGrid equivalent."""


class TileGrid:
    """TileGrid arranges bitmap tiles on screen.
    
    A TileGrid is a grid of tiles that are sourced from a bitmap.
    Each tile can be individually positioned and colored using a palette.
    Compatible with CircuitPython's displayio.TileGrid API.
    """
    
    def __init__(self, bitmap, *, pixel_shader, width=1, height=1, 
                 tile_width=None, tile_height=None, default_tile=0, x=0, y=0):
        """Initialize TileGrid.
        
        Args:
            bitmap: Source bitmap containing tile graphics
            pixel_shader: Palette to use for coloring
            width: Number of tiles wide (default 1)
            height: Number of tiles high (default 1)
            tile_width: Width of each tile in pixels (default: bitmap width)
            tile_height: Height of each tile in pixels (default: bitmap height)
            default_tile: Default tile index (default 0)
            x: X position of grid (default 0)
            y: Y position of grid (default 0)
        """
        self.bitmap = bitmap
        self.pixel_shader = pixel_shader
        self.width = width
        self.height = height
        
        # Set tile dimensions
        if tile_width is None:
            self.tile_width = bitmap.width
        else:
            self.tile_width = tile_width
            
        if tile_height is None:
            self.tile_height = bitmap.height
        else:
            self.tile_height = tile_height
            
        # Calculate tiles per row in bitmap
        self._tiles_per_row = bitmap.width // self.tile_width
        
        # Initialize tile indices
        self._tiles = [[default_tile for _ in range(width)] for _ in range(height)]
        
        # Position and visibility
        self.x = x
        self.y = y
        self.hidden = False
        self._transpose_xy = False
        self._flip_x = False
        self._flip_y = False
        
    def __setitem__(self, index, tile_index):
        """Set tile at given position.
        
        Args:
            index: (x, y) tuple or flat index
            tile_index: Index of tile in bitmap
        """
        if isinstance(index, tuple):
            x, y = index
            if not (0 <= x < self.width and 0 <= y < self.height):
                raise IndexError(f"Tile index ({x}, {y}) out of bounds")
        else:
            # Convert flat index to x, y
            y = index // self.width
            x = index % self.width
            if not (0 <= index < self.width * self.height):
                raise IndexError(f"Tile index {index} out of bounds")
                
        self._tiles[y][x] = tile_index
        
    def __getitem__(self, index):
        """Get tile at given position.
        
        Args:
            index: (x, y) tuple or flat index
            
        Returns:
            Tile index
        """
        if isinstance(index, tuple):
            x, y = index
            if not (0 <= x < self.width and 0 <= y < self.height):
                raise IndexError(f"Tile index ({x}, {y}) out of bounds")
        else:
            # Convert flat index to x, y
            y = index // self.width
            x = index % self.width
            if not (0 <= index < self.width * self.height):
                raise IndexError(f"Tile index {index} out of bounds")
                
        return self._tiles[y][x]
        
    @property
    def transpose_xy(self):
        """Get transpose_xy setting."""
        return self._transpose_xy
        
    @transpose_xy.setter
    def transpose_xy(self, value):
        """Set whether to swap x and y coordinates."""
        self._transpose_xy = bool(value)
        
    @property
    def flip_x(self):
        """Get flip_x setting."""
        return self._flip_x
        
    @flip_x.setter
    def flip_x(self, value):
        """Set whether to flip horizontally."""
        self._flip_x = bool(value)
        
    @property
    def flip_y(self):
        """Get flip_y setting."""
        return self._flip_y
        
    @flip_y.setter  
    def flip_y(self, value):
        """Set whether to flip vertically."""
        self._flip_y = bool(value)
        
    def get_tile_bitmap(self, tile_index):
        """Get bitmap data for a specific tile.
        
        Args:
            tile_index: Index of tile to get
            
        Returns:
            Bitmap-like object with tile data
        """
        # Calculate tile position in source bitmap
        tile_x = (tile_index % self._tiles_per_row) * self.tile_width
        tile_y = (tile_index // self._tiles_per_row) * self.tile_height
        
        # Create a view of the tile data
        # (In actual implementation, this would return a view of the bitmap data)
        return (tile_x, tile_y, self.tile_width, self.tile_height)
        
    @property
    def pixel_width(self):
        """Get total width in pixels."""
        return self.width * self.tile_width
        
    @property
    def pixel_height(self):
        """Get total height in pixels."""
        return self.height * self.tile_height