# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Core LED matrix simulation with pixel-level control."""

import os
from .pixel_buffer import PixelBuffer
from .color_utils import apply_brightness

# pygame is imported lazily (inside the methods that build the desktop "LED
# circle" window surface) so the pixel-buffer render path stays pure-Python +
# numpy and importable in headless environments without pygame (e.g. Pyodide in
# the browser, or CI). See the ``headless`` flag below.


class LEDMatrix:
    """Core LED matrix simulation with pixel-level control.
    
    This class simulates the physical appearance of an LED matrix display,
    including realistic LED rendering with configurable pitch and appearance.
    """
    
    def __init__(self, width, height, pitch=3.0, led_size=None, performance_manager=None,
                 headless=False, bit_depth=4):
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
        # Headless: populate the pixel buffer but skip the pygame window surface
        # entirely (no pygame import). Per-instance, or process-wide via
        # SCROLLKIT_HEADLESS=1 (used by the browser/Pyodide and CI render paths).
        self.headless = headless or os.environ.get("SCROLLKIT_HEADLESS") == "1"
        
        # Calculate surface size based on LED arrangement
        self.surface_width = width * (self.led_size + self.spacing) - self.spacing
        self.surface_height = height * (self.led_size + self.spacing) - self.spacing
        
        # Create pygame surface for rendering
        self.surface = None
        self._background_color = (8, 8, 11)  # near-black, like a powered-but-unlit HUB75 panel

        # Honest colour: quantise to the panel's per-channel bit depth (16 levels
        # at bit_depth=4) so the simulator shows what the hardware actually shows,
        # not full 24-bit colour the panel can't display. Set ``bit_depth`` to 6
        # (and the caches self-refresh) for the smooth-gradient finale.
        self.bit_depth = bit_depth
        self.posterize = True

        # Round-LED + soft-glow appearance geometry, derived from the LED size so
        # it tracks the configured pitch (matches the rendered hero stills).
        self._dot_radius = max(2, int(round(self.led_size * 0.46)))
        self._core_radius = max(1, int(round(self.led_size * 0.22)))
        self._off_radius = max(1, int(round(self.led_size * 0.30)))
        self._off_color = (22, 22, 26)            # faint unlit LED, so the grid reads
        self._glow_reach = max(self.led_size,     # how far the additive halo bleeds
                               int(round((self.led_size + self.spacing) * 0.95)))
        self._glow_cache = {}      # posterised color -> additive glow halo sprite
        self._dot_cache = {}       # posterised color -> crisp LED dot sprite
        self._base_surface = None  # near-black bg + unlit-LED grid (rebuilt only if cleared)
        
    def initialize_surface(self):
        """Initialize the pygame surface for rendering (no-op when headless)."""
        if self.headless:
            return
        import pygame
        if not pygame.get_init():
            pygame.init()
            
        self.surface = pygame.Surface((self.surface_width, self.surface_height))
        self.surface.fill(self._background_color)
        
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
        """Draw the (already-populated) pixel buffer to the pygame window surface.

        The buffer is filled by set_pixel()/fill() before this runs. When
        headless the perf model still runs (it models device timing, not pixels)
        but the pygame surface step is skipped, so no pygame is needed.
        """

        if self.performance_manager and self.performance_manager.enabled:
            # Simulate display refresh delay
            self.performance_manager.simulate_io_operation("display_refresh")
            # Simulate potential GC pause during rendering
            self.performance_manager.simulate_gc_pause()
            
        if self.headless:
            # Buffer already populated by set_pixel(); skip the pygame surface.
            self.pixel_buffer.clear_dirty()
            return

        if self.surface is None:
            self.initialize_surface()

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
            
    def _posterize_color(self, color):
        """Quantise an (r, g, b) to the panel's per-channel bit depth.

        At ``bit_depth=4`` each channel snaps to 16 levels (multiples of 17) — the
        honest hardware colour. Returns plain Python ints (no numpy scalars).
        """
        if not self.posterize:
            return (int(color[0]), int(color[1]), int(color[2]))
        levels = (1 << self.bit_depth) - 1
        if levels <= 0:
            return (int(color[0]), int(color[1]), int(color[2]))
        return tuple(int(round(int(c) / 255.0 * levels)) * 255 // levels
                     for c in color)

    # All round LEDs are drawn supersampled then smooth-scaled down: a plain small
    # pygame circle rasterises to a chunky diamond, so we draw big and shrink for
    # clean anti-aliased dots (matches the rendered hero stills).
    @staticmethod
    def _aa_scale(surface, size):
        import pygame
        return pygame.transform.smoothscale(surface, size)

    def _build_base_surface(self):
        """Build (and cache) the static panel: near-black ground + the unlit-LED grid."""
        import pygame
        ss = 3
        big = pygame.Surface((self.surface_width * ss, self.surface_height * ss))
        big.fill(self._background_color)
        step = (self.led_size + self.spacing) * ss
        half = (self.led_size // 2) * ss
        rad = max(1, self._off_radius * ss)
        for gy in range(self.height):
            cy = gy * step + half
            for gx in range(self.width):
                cx = gx * step + half
                pygame.draw.circle(big, self._off_color, (cx, cy), rad)
        return self._aa_scale(big, (self.surface_width, self.surface_height))

    def _glow_sprite(self, color):
        """A radial additive halo for an 'on' LED of ``color`` (cached per colour).

        Drawn on black so an additive blit contributes only the glow; overlapping
        halos sum, giving the soft bleed of a real panel.
        """
        import pygame
        sprite = self._glow_cache.get(color)
        if sprite is not None:
            return sprite
        ss = 2
        reach = self._glow_reach
        big = pygame.Surface((2 * reach * ss, 2 * reach * ss))  # RGB; additive ignores black
        big.fill((0, 0, 0))
        steps = 6
        for k in range(steps):
            t = k / (steps - 1)                           # 0 outer .. 1 inner
            rad = int(round((reach - t * (reach - self._dot_radius)) * ss))
            bright = 0.10 + 0.42 * t                      # dim at the edge, bright near the core
            col = tuple(min(255, int(ch * bright)) for ch in color)
            pygame.draw.circle(big, col, (reach * ss, reach * ss), max(1, rad))
        sprite = self._aa_scale(big, (2 * reach, 2 * reach))
        if len(self._glow_cache) < 256:
            self._glow_cache[color] = sprite
        return sprite

    def _dot_sprite(self, color):
        """The crisp LED dot + bright core for an 'on' LED (cached per colour)."""
        import pygame
        sprite = self._dot_cache.get(color)
        if sprite is not None:
            return sprite
        ss = 4
        size = self.led_size
        big = pygame.Surface((size * ss, size * ss), pygame.SRCALPHA)
        center = (size // 2) * ss
        pygame.draw.circle(big, color, (center, center), self._dot_radius * ss)
        core = tuple(min(255, int(ch * 1.18) + 40) for ch in color)
        pygame.draw.circle(big, core, (center, center), max(1, self._core_radius * ss))
        sprite = self._aa_scale(big, (size, size))
        if len(self._dot_cache) < 256:
            self._dot_cache[color] = sprite
        return sprite

    def _render_full(self):
        """Render the panel: near-black ground + unlit grid, then additive glow + dots.

        Two passes so every halo blooms *under* every crisp dot (and overlapping
        halos add), matching the rendered hero stills.
        """
        import pygame
        if self._base_surface is None:
            self._base_surface = self._build_base_surface()
        self.surface.blit(self._base_surface, (0, 0))

        pixels = self.pixel_buffer.get_buffer()
        step = self.led_size + self.spacing
        half = self.led_size // 2

        lit = []
        for y in range(self.height):
            for x in range(self.width):
                color = tuple(int(c) for c in pixels[y, x])
                if self.brightness < 1.0:
                    color = apply_brightness(color, self.brightness)
                color = self._posterize_color(color)
                if color[0] + color[1] + color[2] <= 24:
                    continue   # 'off' — the unlit grid in the base shows through
                lit.append((x * step, y * step, color))

        reach = self._glow_reach
        for led_x, led_y, color in lit:
            self.surface.blit(self._glow_sprite(color),
                              (led_x + half - reach, led_y + half - reach),
                              special_flags=pygame.BLEND_RGB_ADD)
        for led_x, led_y, color in lit:
            self.surface.blit(self._dot_sprite(color), (led_x, led_y))
            
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
            import pygame
            pygame.image.save(self.surface, filename)