"""CircuitPython displayio.Display equivalent."""

from ..core.led_matrix import LEDMatrix
from ..core.color_utils import rgb565_to_rgb888


class Display:
    """Display manages the screen output.
    
    This class provides the main interface for showing groups and
    managing display properties like brightness and rotation.
    Compatible with CircuitPython's displayio.Display API.
    """
    
    def __init__(self, display_bus, *, width, height, rotation=0,
                 color_depth=16, auto_refresh=True, backlight_pin=None,
                 brightness=1.0, auto_brightness=False, backlight_on_high=True,
                 native_frames_per_second=60):
        """Initialize Display.
        
        Args:
            display_bus: Display bus interface (e.g., FourWire)
            width: Display width in pixels
            height: Display height in pixels
            rotation: Display rotation in degrees (0, 90, 180, 270)
            color_depth: Color depth in bits (default 16)
            auto_refresh: Whether to automatically refresh display
            backlight_pin: Pin for backlight control (ignored in simulator)
            brightness: Initial brightness (0.0 to 1.0)
            auto_brightness: Whether to automatically adjust brightness
            backlight_on_high: Whether backlight is on when pin is high
            native_frames_per_second: Native refresh rate
        """
        self.display_bus = display_bus
        self.width = width
        self.height = height
        self.rotation = rotation
        self.color_depth = color_depth
        self.auto_refresh = auto_refresh
        self._brightness = brightness
        self.auto_brightness = auto_brightness
        self.native_frames_per_second = native_frames_per_second
        
        # Current root group
        self.root_group = None
        
        # Create LED matrix for rendering
        self._matrix = LEDMatrix(width, height)
        self._matrix.set_brightness(brightness)
        
    @property
    def brightness(self):
        """Get display brightness."""
        return self._brightness
        
    @brightness.setter
    def brightness(self, value):
        """Set display brightness.
        
        Args:
            value: Brightness from 0.0 to 1.0
        """
        self._brightness = max(0.0, min(1.0, value))
        self._matrix.set_brightness(self._brightness)
        
    def show(self, group_or_tilegrid):
        """Show a Group or TileGrid on the display.
        
        Args:
            group_or_tilegrid: Group or TileGrid to display
        """
        self.root_group = group_or_tilegrid
        if self.auto_refresh:
            self.refresh()
            
    def refresh(self, *, target_frames_per_second=None, minimum_frames_per_second=1):
        """Manually refresh the display.
        
        Args:
            target_frames_per_second: Target refresh rate
            minimum_frames_per_second: Minimum acceptable refresh rate
        """
        if self.root_group is None:
            return
            
        # Clear the matrix
        self._matrix.clear()
        
        # Render the root group
        self._render_group(self.root_group, 0, 0, 1)
        
        # Update the display
        self._matrix.render()
        
    def _render_group(self, group, offset_x, offset_y, scale):
        """Recursively render a group and its contents.
        
        Args:
            group: Group to render
            offset_x: X offset from parent
            offset_y: Y offset from parent
            scale: Cumulative scale factor
        """
        if hasattr(group, 'hidden') and group.hidden:
            return
            
        # Calculate group position
        group_x = offset_x + (group.x if hasattr(group, 'x') else 0) * scale
        group_y = offset_y + (group.y if hasattr(group, 'y') else 0) * scale
        group_scale = scale * (group.scale if hasattr(group, 'scale') else 1)
        
        # Check if this is a Group with items
        if hasattr(group, '_items'):
            # Render all items in the group
            for item in group._items:
                self._render_group(item, group_x, group_y, group_scale)
        # Check if this is a TileGrid
        elif hasattr(group, 'bitmap') and hasattr(group, 'pixel_shader'):
            self._render_tilegrid(group, group_x, group_y, group_scale)
        # Check if this is a Label (from adafruit_display_text)
        elif hasattr(group, '_bitmap') and hasattr(group, 'color'):
            self._render_label(group, group_x, group_y, group_scale)
            
    def _render_tilegrid(self, tilegrid, x, y, scale):
        """Render a TileGrid to the display.
        
        Args:
            tilegrid: TileGrid to render
            x: X position
            y: Y position
            scale: Scale factor
        """
        if tilegrid.hidden:
            return
            
        # Get bitmap and palette
        bitmap = tilegrid.bitmap
        palette = tilegrid.pixel_shader
        
        # Render each tile
        for tile_y in range(tilegrid.height):
            for tile_x in range(tilegrid.width):
                tile_index = tilegrid[tile_x, tile_y]
                
                # Calculate tile source position
                src_tile_x = (tile_index % tilegrid._tiles_per_row) * tilegrid.tile_width
                src_tile_y = (tile_index // tilegrid._tiles_per_row) * tilegrid.tile_height
                
                # Calculate destination position
                dst_x = x + tile_x * tilegrid.tile_width * scale
                dst_y = y + tile_y * tilegrid.tile_height * scale
                
                # Render tile pixels
                for py in range(tilegrid.tile_height):
                    for px in range(tilegrid.tile_width):
                        # Get pixel from bitmap
                        pixel_value = bitmap[src_tile_x + px, src_tile_y + py]
                        
                        # Skip transparent pixels
                        if palette.is_transparent(pixel_value):
                            continue
                            
                        # Get color from palette
                        color = palette.get_rgb888(pixel_value)
                        
                        # Apply scaling
                        for sy in range(scale):
                            for sx in range(scale):
                                pixel_x = int(dst_x + px * scale + sx)
                                pixel_y = int(dst_y + py * scale + sy)
                                
                                # Set pixel if within bounds
                                if 0 <= pixel_x < self.width and 0 <= pixel_y < self.height:
                                    self._matrix.set_pixel(pixel_x, pixel_y, color)
                                    
    def _render_label(self, label, x, y, scale):
        """Render a Label to the display.
        
        Args:
            label: Label to render
            x: X position
            y: Y position
            scale: Scale factor
        """
        # Labels are Groups that contain a TileGrid, so render them as groups
        self._render_group(label, x, y, scale)
        
    def get_matrix(self):
        """Get the underlying LED matrix.
        
        Returns:
            LEDMatrix instance
        """
        return self._matrix