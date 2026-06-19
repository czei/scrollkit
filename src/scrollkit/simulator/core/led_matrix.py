"""Core LED matrix simulation with pixel-level control."""

import pygame
import numpy as np
from .pixel_buffer import PixelBuffer
from .color_utils import apply_brightness


class LEDMatrix:
    """Core LED matrix simulation with pixel-level control.
    
    This class simulates the physical appearance of an LED matrix display,
    including realistic LED rendering with configurable pitch and appearance.
    """
    
    def __init__(self, width, height, pitch=3.0, led_size=None, performance_manager=None):
        """Initialize LED matrix.
        
        Args:
            width: Matrix width in pixels
            height: Matrix height in pixels  
            pitch: LED pitch in mm (2.5, 3, 4, 5, or 6)
            led_size: Optional LED size override in pixels
            performance_manager: Optional performance simulation manager
        """
        self.width = width
        self.height = height
        self.pitch = pitch
        
        # Calculate LED size and spacing based on pitch
        # For a given pitch, LED size is typically 80% of pitch
        # Scale factor adjusted to match physical 192mm x 96mm display (725x362 pixels at 96 DPI)
        # 192mm / 64 pixels = 3mm pitch, display should be ~725 pixels wide
        if led_size is None:
            self.led_size = int(pitch * 0.8 * 3.75)  # 9 pixel LED size
        else:
            self.led_size = led_size
        self.spacing = int(pitch * 0.2 * 3.75)  # 2 pixel spacing
        
        self.pixel_buffer = PixelBuffer(width, height)
        self.brightness = 1.0
        self.performance_manager = performance_manager
        
        # Calculate surface size based on LED arrangement
        self.surface_width = width * (self.led_size + self.spacing) - self.spacing
        self.surface_height = height * (self.led_size + self.spacing) - self.spacing
        
        # Create pygame surface for rendering
        self.surface = None
        self._led_cache = {}  # Cache rendered LED circles
        self._background_color = (30, 30, 30)  # Medium gray background for realistic appearance
        
    def initialize_surface(self):
        """Initialize the pygame surface for rendering."""
        if not pygame.get_init():
            pygame.init()
            
        self.surface = pygame.Surface((self.surface_width, self.surface_height))
        self.surface.fill(self._background_color)
        
        # Pre-render some common LED appearances for performance
        self._create_led_cache()
        
    def set_pixel(self, x, y, color):
        """Set a single pixel color.
        
        Args:
            x: X coordinate (0 to width-1)
            y: Y coordinate (0 to height-1)
            color: Color as (r, g, b) tuple or RGB value
        """
        if self.performance_manager and self.performance_manager.enabled:
            # Simulate pixel write delay
            self.performance_manager.simulate_instruction_delay(3)
            
        self.pixel_buffer.set_pixel(x, y, color)
        
    def get_pixel(self, x, y):
        """Get a single pixel color.
        
        Args:
            x: X coordinate (0 to width-1)
            y: Y coordinate (0 to height-1)
            
        Returns:
            Color as (r, g, b) tuple
        """
        return self.pixel_buffer.get_pixel(x, y)
        
    def fill(self, color):
        """Fill all pixels with a single color.
        
        Args:
            color: Color as (r, g, b) tuple or RGB value
        """
        self.pixel_buffer.fill(color)
        
    def clear(self):
        """Clear all pixels to black."""
        self.pixel_buffer.clear()
        
    def set_brightness(self, brightness):
        """Set display brightness.
        
        Args:
            brightness: Float from 0.0 to 1.0
        """
        self.brightness = max(0.0, min(1.0, brightness))
        
    def render(self):
        """Render the matrix to pygame surface."""
        if self.surface is None:
            self.initialize_surface()
            
        if self.performance_manager and self.performance_manager.enabled:
            # Simulate display refresh delay
            self.performance_manager.simulate_io_operation("display_refresh")
            # Simulate potential GC pause during rendering
            self.performance_manager.simulate_gc_pause()
            
        # Only update dirty regions if tracking is enabled
        if self.pixel_buffer.is_dirty():
            dirty_region = self.pixel_buffer.get_dirty_region()
            
            if dirty_region is None:
                # Full update
                self._render_full()
            else:
                # Partial update (future optimization)
                self._render_full()  # For now, always do full update
                
            self.pixel_buffer.clear_dirty()
            
    def _render_full(self):
        """Render all LEDs to the surface."""
        # Clear surface
        self.surface.fill(self._background_color)
        
        # Get pixel data
        pixels = self.pixel_buffer.get_buffer()
        
        # Render each LED
        for y in range(self.height):
            for x in range(self.width):
                color = tuple(pixels[y, x])
                if self.brightness < 1.0:
                    color = apply_brightness(color, self.brightness)
                    
                self._render_led(x, y, color)
                
    def _render_led(self, x, y, color):
        """Render a single LED at the given position.
        
        Args:
            x: LED X position
            y: LED Y position
            color: Color as (r, g, b) tuple
        """
        # Calculate LED position on surface
        led_x = x * (self.led_size + self.spacing)
        led_y = y * (self.led_size + self.spacing)
        
        # Check if we have this LED appearance cached
        # Convert to regular Python ints to avoid numpy type issues
        cache_key = (int(color[0]), int(color[1]), int(color[2]))
        if cache_key in self._led_cache:
            led_surface = self._led_cache[cache_key]
        else:
            # Create new LED appearance
            led_surface = self._create_led_surface(color)
            # Cache it if cache isn't too large
            if len(self._led_cache) < 256:
                self._led_cache[cache_key] = led_surface
                
        # Blit LED to main surface
        self.surface.blit(led_surface, (led_x, led_y))
        
    def _create_led_surface(self, color):
        """Create a surface for a single LED with given color.
        
        Args:
            color: Color as (r, g, b) tuple
            
        Returns:
            Pygame surface with rendered LED
        """
        # Create surface with per-pixel alpha
        led_surface = pygame.Surface((self.led_size, self.led_size), pygame.SRCALPHA)
        
        # Draw LED as a perfect circle to simulate real LED
        center = self.led_size // 2
        radius = self.led_size // 2 - 1
        
        # For 100% brightness, enhance the LED appearance for maximum visibility
        enhanced_color = color
        if hasattr(self, 'brightness') and self.brightness == 1.0:
            # At 100% brightness, make LEDs extra bright by enhancing the base color
            enhanced_color = tuple(min(255, int(c * 1.15)) for c in color)
        
        # For realistic LED matrix appearance, "off" LEDs should be visible
        color_sum = int(color[0]) + int(color[1]) + int(color[2])
        
        if color_sum <= 20:  # "Off" LEDs - show as dark grey circles
            # Draw visible "off" LED as dark grey circle
            off_led_color = (60, 60, 60)  # Dark grey but visible
            pygame.draw.circle(led_surface, off_led_color, (center, center), radius)
            # Add subtle darker outline for depth
            pygame.draw.circle(led_surface, (40, 40, 40), (center, center), radius, 1)
        else:
            # Draw main LED circle for "on" LEDs
            pygame.draw.circle(led_surface, enhanced_color, (center, center), radius)
            
            # Add subtle gradient for realism without creating diamond shape
            # Create a smaller, dimmer circle for subtle depth
            # Avoid sharp highlights that create diamond appearance
            inner_radius = max(1, radius - 3)
            gradient_intensity = 15  # Very subtle
            gradient_color = tuple(min(255, int(c) + gradient_intensity) for c in enhanced_color)
            pygame.draw.circle(led_surface, gradient_color, (center, center), inner_radius)
            
        return led_surface
        
    def _create_led_cache(self):
        """Pre-create commonly used LED appearances."""
        # Cache black LED
        self._led_cache[(0, 0, 0)] = self._create_led_surface((0, 0, 0))
        
        # Cache primary colors at full brightness
        for color in [(255, 0, 0), (0, 255, 0), (0, 0, 255), 
                      (255, 255, 0), (255, 0, 255), (0, 255, 255),
                      (255, 255, 255)]:
            self._led_cache[color] = self._create_led_surface(color)
            
    def get_surface(self):
        """Get the pygame surface for this matrix.
        
        Returns:
            Pygame surface containing rendered LEDs
        """
        if self.surface is None:
            self.initialize_surface()
        return self.surface
        
    def save_screenshot(self, filename):
        """Save a screenshot of the current matrix state.
        
        Args:
            filename: Path to save the screenshot
        """
        if self.surface:
            pygame.image.save(self.surface, filename)