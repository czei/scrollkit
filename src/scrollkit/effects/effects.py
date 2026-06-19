"""Core effects engine for SLDK.

Provides lightweight visual effects optimized for ESP32 performance.
"""

from __future__ import annotations

try:
    from typing import Any, List, Optional
except ImportError:  # CircuitPython has no 'typing' module
    pass

from ..exceptions import DisplayError

try:
    import time
    get_time = time.monotonic
except (ImportError, AttributeError):
    # Fallback for testing
    import time
    get_time = time.time

try:
    import math
except ImportError:
    # Basic math for CircuitPython if math module limited
    class SimpleMath:
        @staticmethod
        def sin(x):
            # Simple sine approximation if needed
            return x - (x**3)/6 + (x**5)/120
        
        @staticmethod
        def cos(x):
            return SimpleMath.sin(x + 1.5708)  # sin(x + π/2)
        
        pi = 3.14159
    
    math = SimpleMath()


class EffectsEngine:
    """Lightweight effects engine for ESP32-friendly visual effects.
    
    Designed to work within CircuitPython memory and performance constraints.
    """
    
    def __init__(self, max_effects: int = 2, target_fps: int = 5) -> None:
        """Initialize effects engine.
        
        Args:
            max_effects: Maximum concurrent effects (memory constraint)
            target_fps: Target effects frame rate (performance constraint)
        """
        self.max_effects: int = max_effects
        self.target_fps: int = target_fps
        self.frame_duration: float = 1.0 / target_fps
        
        self.active_effects: list = []
        self.last_frame_time: float = 0
        
        # Pre-allocated color tables to save memory
        self.rainbow_colors: list[int] = [
            0xFF0000, 0xFF3300, 0xFF6600, 0xFF9900, 0xFFCC00, 0xFFFF00,
            0xCCFF00, 0x99FF00, 0x66FF00, 0x33FF00, 0x00FF00, 0x00FF33,
            0x00FF66, 0x00FF99, 0x00FFCC, 0x00FFFF, 0x00CCFF, 0x0099FF,
            0x0066FF, 0x0033FF, 0x0000FF, 0x3300FF, 0x6600FF, 0x9900FF,
            0xCC00FF, 0xFF00FF, 0xFF00CC, 0xFF0099, 0xFF0066, 0xFF0033
        ]
        
        self.warm_colors: list[int] = [0xFF4500, 0xFF6347, 0xFF7F50, 0xFFA500, 0xFFD700]
        self.cool_colors: list[int] = [0x00FFFF, 0x87CEEB, 0x4169E1, 0x0000FF, 0x8A2BE2]
    
    def add_effect(self, effect: Any) -> bool:
        """Add effect to active list.
        
        Args:
            effect: Effect instance to add
        """
        if len(self.active_effects) < self.max_effects:
            effect.start_time = get_time()
            self.active_effects.append(effect)
            return True
        return False
    
    def remove_effect(self, effect: Any) -> None:
        """Remove effect from active list.
        
        Args:
            effect: Effect instance to remove
        """
        if effect in self.active_effects:
            self.active_effects.remove(effect)
    
    async def update(self, display: Any) -> None:
        """Update all active effects.
        
        Args:
            display: Display interface
        """
        current_time = get_time()
        
        # Frame rate limiting
        if current_time - self.last_frame_time < self.frame_duration:
            return
        
        self.last_frame_time = current_time
        
        # Update effects (backwards to allow removal during iteration)
        for i in range(len(self.active_effects) - 1, -1, -1):
            effect = self.active_effects[i]
            
            # Check if effect is expired
            if effect.duration and (current_time - effect.start_time) > effect.duration:
                self.active_effects.pop(i)
                continue
            
            # Update effect
            try:
                await effect.update(display, current_time - effect.start_time)
            except Exception as e:
                print(f"Effect error: {e}")
                self.active_effects.pop(i)
    
    def clear_effects(self) -> None:
        """Clear all active effects."""
        self.active_effects.clear()
    
    def get_rainbow_color(self, position: float, time_offset: float = 0) -> int:
        """Get rainbow color from pre-calculated table.
        
        Args:
            position: Position in rainbow (0.0 to 1.0)
            time_offset: Time-based offset for animation
            
        Returns:
            int: RGB color value
        """
        # Add time offset for animation
        animated_position = (position + time_offset) % 1.0
        
        # Map to color table index
        index = int(animated_position * len(self.rainbow_colors)) % len(self.rainbow_colors)
        return self.rainbow_colors[index]
    
    def blend_colors(self, color1: int, color2: int, ratio: float) -> int:
        """Blend two colors together.
        
        Args:
            color1: First color (RGB int)
            color2: Second color (RGB int)
            ratio: Blend ratio (0.0 = color1, 1.0 = color2)
            
        Returns:
            int: Blended color
        """
        # Extract RGB components
        r1 = (color1 >> 16) & 0xFF
        g1 = (color1 >> 8) & 0xFF
        b1 = color1 & 0xFF
        
        r2 = (color2 >> 16) & 0xFF
        g2 = (color2 >> 8) & 0xFF
        b2 = color2 & 0xFF
        
        # Linear interpolation
        r = int(r1 + (r2 - r1) * ratio)
        g = int(g1 + (g2 - g1) * ratio)
        b = int(b1 + (b2 - b1) * ratio)
        
        return (r << 16) | (g << 8) | b


class SimpleEffect:
    """Base class for simple effects."""
    
    def __init__(self, duration: Optional[float] = None) -> None:
        """Initialize effect.
        
        Args:
            duration: Effect duration in seconds (None = infinite)
        """
        self.duration: Optional[float] = duration
        self.start_time: float = 0
    
    async def update(self, display: Any, elapsed_time: float) -> None:
        """Update effect for current frame.
        
        Args:
            display: Display interface
            elapsed_time: Time since effect started
        """
        raise NotImplementedError("Subclass must implement update()")


class RainbowCycleEffect(SimpleEffect):
    """Rainbow color cycling effect."""
    
    def __init__(self, speed: float = 1.0, duration: Optional[float] = None) -> None:
        """Initialize rainbow cycle.
        
        Args:
            speed: Animation speed multiplier
            duration: Effect duration
        """
        super().__init__(duration)
        self.speed: float = speed
        self.last_update_time: float = 0
        self.update_interval: float = 0.2  # Update every 200ms for performance
    
    async def update(self, display: Any, elapsed_time: float) -> None:
        """Apply rainbow cycling to entire display."""
        # Throttle updates for performance
        if elapsed_time - self.last_update_time < self.update_interval:
            return
        
        self.last_update_time = elapsed_time
        
        # Calculate rainbow progression
        time_offset = (elapsed_time * self.speed * 0.1) % 1.0
        
        # Apply rainbow to all pixels (simplified for performance)
        color_index = int(time_offset * 30) % 30  # 30 rainbow colors
        rainbow_color = [
            0xFF0000, 0xFF1A00, 0xFF3300, 0xFF4D00, 0xFF6600, 0xFF8000,
            0xFF9900, 0xFFB300, 0xFFCC00, 0xFFE600, 0xFFFF00, 0xE6FF00,
            0xCCFF00, 0xB3FF00, 0x99FF00, 0x80FF00, 0x66FF00, 0x4DFF00,
            0x33FF00, 0x1AFF00, 0x00FF00, 0x00FF1A, 0x00FF33, 0x00FF4D,
            0x00FF66, 0x00FF80, 0x00FF99, 0x00FFB3, 0x00FFCC, 0x00FFE6
        ][color_index]
        
        # Only update a few pixels per frame for performance
        width = display.width
        height = display.height
        
        # Update 4 pixels per frame in a pattern
        frame_offset = int(elapsed_time * 10) % (width * height)
        
        for i in range(4):  # Update 4 pixels max per frame
            pixel_index = (frame_offset + i) % (width * height)
            x = pixel_index % width
            y = pixel_index // width
            
            # Slight color variation based on position
            position_offset = (x + y) * 0.1
            final_color = rainbow_color
            
            await display.set_pixel(x, y, final_color)


class SparkleEffect(SimpleEffect):
    """Simple sparkle effect with minimal memory usage."""
    
    def __init__(self, intensity: int = 3, duration: Optional[float] = None) -> None:
        """Initialize sparkle effect.
        
        Args:
            intensity: Number of sparkles (1-5 recommended for ESP32)
            duration: Effect duration
        """
        super().__init__(duration)
        self.intensity: int = min(intensity, 5)  # Limit for performance
        self.sparkle_positions: list = []
        self.sparkle_life: list = []
        self.last_spawn_time: float = 0
        self.spawn_interval: float = 0.3  # New sparkle every 300ms
    
    async def update(self, display: Any, elapsed_time: float) -> None:
        """Update sparkles."""
        # Spawn new sparkle occasionally
        if elapsed_time - self.last_spawn_time > self.spawn_interval:
            if len(self.sparkle_positions) < self.intensity:
                import random
                x = random.randint(0, display.width - 1)
                y = random.randint(0, display.height - 1)
                self.sparkle_positions.append((x, y))
                self.sparkle_life.append(elapsed_time)
                self.last_spawn_time = elapsed_time
        
        # Update existing sparkles
        for i in range(len(self.sparkle_positions) - 1, -1, -1):
            x, y = self.sparkle_positions[i]
            life = elapsed_time - self.sparkle_life[i]
            
            if life > 1.0:  # Sparkle dies after 1 second
                self.sparkle_positions.pop(i)
                self.sparkle_life.pop(i)
                continue
            
            # Fade sparkle based on age
            brightness = max(0, 1.0 - life)
            intensity = int(brightness * 255)
            color = (intensity << 16) | (intensity << 8) | intensity  # White
            
            await display.set_pixel(x, y, color)


class PulseEffect(SimpleEffect):
    """Brightness pulse effect using display brightness control."""
    
    def __init__(self, speed: float = 1.0, min_brightness: float = 0.1, max_brightness: float = 1.0, duration: Optional[float] = None) -> None:
        """Initialize pulse effect.
        
        Args:
            speed: Pulse speed
            min_brightness: Minimum brightness (0.0-1.0)
            max_brightness: Maximum brightness (0.0-1.0)
            duration: Effect duration
        """
        super().__init__(duration)
        self.speed: float = speed
        self.min_brightness: float = min_brightness
        self.max_brightness: float = max_brightness
        self.original_brightness: Optional[float] = None
    
    async def update(self, display: Any, elapsed_time: float) -> None:
        """Update brightness pulse."""
        # Store original brightness on first update
        if self.original_brightness is None:
            self.original_brightness = getattr(display, 'brightness', 1.0)
        
        # Calculate pulse using sine wave
        cycle_time = elapsed_time * self.speed
        pulse_value = math.sin(cycle_time * 2 * math.pi)  # -1 to 1
        
        # Map to brightness range
        brightness_range = self.max_brightness - self.min_brightness
        brightness = self.min_brightness + (pulse_value + 1) * 0.5 * brightness_range
        
        # Apply brightness if display supports it
        if hasattr(display, 'brightness'):
            display.brightness = brightness


class EdgeGlowEffect(SimpleEffect):
    """Simple edge glow effect."""
    
    def __init__(self, color: int = 0x00FFFF, duration: Optional[float] = None) -> None:
        """Initialize edge glow.
        
        Args:
            color: Glow color
            duration: Effect duration
        """
        super().__init__(duration)
        self.color: int = color
        self.last_update: float = 0
        self.update_interval: float = 0.1  # Update every 100ms
    
    async def update(self, display: Any, elapsed_time: float) -> None:
        """Update edge glow."""
        if elapsed_time - self.last_update < self.update_interval:
            return
        
        self.last_update = elapsed_time
        
        # Calculate glow intensity
        intensity = (math.sin(elapsed_time * 3) + 1) * 0.5  # 0 to 1
        
        # Extract color components
        r = int(((self.color >> 16) & 0xFF) * intensity)
        g = int(((self.color >> 8) & 0xFF) * intensity)
        b = int((self.color & 0xFF) * intensity)
        glow_color = (r << 16) | (g << 8) | b
        
        # Draw edges (top, bottom, left, right)
        width = display.width
        height = display.height
        
        # Top and bottom edges
        for x in range(0, width, 2):  # Every other pixel for performance
            await display.set_pixel(x, 0, glow_color)
            await display.set_pixel(x, height - 1, glow_color)
        
        # Left and right edges  
        for y in range(0, height, 2):  # Every other pixel for performance
            await display.set_pixel(0, y, glow_color)
            await display.set_pixel(width - 1, y, glow_color)


class CornerFlashEffect(SimpleEffect):
    """Flash the corners of the display."""
    
    def __init__(self, color: int = 0xFFFFFF, flash_duration: float = 0.2, interval: float = 1.0, duration: Optional[float] = None) -> None:
        """Initialize corner flash.
        
        Args:
            color: Flash color
            flash_duration: How long each flash lasts
            interval: Time between flashes
            duration: Total effect duration
        """
        super().__init__(duration)
        self.color: int = color
        self.flash_duration: float = flash_duration
        self.interval: float = interval
    
    async def update(self, display: Any, elapsed_time: float) -> None:
        """Update corner flash."""
        # Calculate if we're in a flash period
        cycle_time = elapsed_time % self.interval
        
        if cycle_time < self.flash_duration:
            # Flash is active
            width = display.width
            height = display.height
            
            # Flash corners
            await display.set_pixel(0, 0, self.color)  # Top-left
            await display.set_pixel(width - 1, 0, self.color)  # Top-right
            await display.set_pixel(0, height - 1, self.color)  # Bottom-left
            await display.set_pixel(width - 1, height - 1, self.color)  # Bottom-right