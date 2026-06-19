"""Enhanced display content with effects integration.

Provides content classes that combine text/graphics with visual effects.
"""

from __future__ import annotations

from typing import Any, List, Optional

from ..exceptions import ContentError

from .content import DisplayContent, ScrollingText, StaticText
from ..effects import EffectsEngine
from ..effects.effects import SparkleEffect, EdgeGlowEffect
from ..effects.particles import ParticleEngine, Sparkle


class EnhancedDisplayContent(DisplayContent):
    """Display content with integrated effects support."""
    
    def __init__(self, duration: Optional[float] = None, enable_effects: bool = True):
        """Initialize enhanced content.
        
        Args:
            duration: Content duration
            enable_effects: Whether to enable visual effects
        """
        super().__init__(duration)
        self.enable_effects: bool = enable_effects
        
        if enable_effects:
            self.effects_engine: Any = EffectsEngine(max_effects=2, target_fps=8)
            self.particle_engine: Any = ParticleEngine(max_particles=4)
        else:
            self.effects_engine: Any = None
            self.particle_engine: Any = None
    
    async def render(self, display) -> None:
        """Render content with effects.
        
        Args:
            display: Display interface
        """
        # Render base content first
        await self.render_base_content(display)
        
        # Apply effects if enabled
        if self.enable_effects:
            if self.effects_engine:
                await self.effects_engine.update(display)
            if self.particle_engine:
                await self.particle_engine.update(display)
    
    async def render_base_content(self, display) -> None:
        """Render the base content without effects.
        
        Override this in subclasses.
        
        Args:
            display: Display interface
        """
        pass
    
    def add_effect(self, effect) -> bool:
        """Add visual effect.
        
        Args:
            effect: Effect instance
        """
        if self.effects_engine:
            return self.effects_engine.add_effect(effect)
        return False
    
    def add_particle(self, particle) -> bool:
        """Add particle effect.
        
        Args:
            particle: Particle instance
        """
        if self.particle_engine:
            return self.particle_engine.add_particle(particle)
        return False
    
    def clear_effects(self) -> None:
        """Clear all effects and particles."""
        if self.effects_engine:
            self.effects_engine.clear_effects()
        if self.particle_engine:
            self.particle_engine.clear_particles()


class SparklingText(EnhancedDisplayContent):
    """Text display with sparkle effects."""
    
    def __init__(self, text: str, color: int = 0xFFFFFF, sparkle_color: int = 0xFFFFFF, 
                 sparkle_intensity: int = 2, duration: Optional[float] = None):
        """Initialize sparkling text.
        
        Args:
            text: Text to display
            color: Text color
            sparkle_color: Sparkle color
            sparkle_intensity: Number of sparkles
            duration: Display duration
        """
        super().__init__(duration, enable_effects=True)
        self.text: str = text
        self.color: int = color
        self.sparkle_color: int = sparkle_color
        self.sparkle_intensity: int = sparkle_intensity
        
        # Add sparkle effect
        if self.effects_engine:
            sparkle = SparkleEffect(intensity=sparkle_intensity)
            self.add_effect(sparkle)
    
    async def render_base_content(self, display) -> None:
        """Render text content."""
        # Simple text rendering - draw text pixels
        # This is a simplified version - real implementation would use font rendering
        
        # For demo purposes, create a simple text pattern
        text_pixels = self._get_text_pixels()
        
        for y, x in text_pixels:
            if 0 <= x < display.width and 0 <= y < display.height:
                await display.set_pixel(x, y, self.color)
    
    def _get_text_pixels(self) -> List[tuple]:
        """Get pixel positions for text.
        
        Returns:
            list: List of (y, x) pixel coordinates
        """
        # Simple hardcoded text patterns for demo
        # In real implementation, this would use font rendering
        
        if "HELLO" in self.text.upper():
            # Simple "HELLO" pattern
            return [
                # H
                (2, 2), (3, 2), (4, 2), (5, 2), (6, 2),
                (2, 4), (3, 4), (4, 4), (5, 4), (6, 4),
                (4, 3),
                # E
                (2, 6), (3, 6), (4, 6), (5, 6), (6, 6),
                (2, 7), (2, 8), (4, 7), (6, 7), (6, 8),
                # L
                (2, 10), (3, 10), (4, 10), (5, 10), (6, 10),
                (6, 11), (6, 12),
                # L
                (2, 14), (3, 14), (4, 14), (5, 14), (6, 14),
                (6, 15), (6, 16),
                # O
                (2, 18), (2, 19), (2, 20),
                (3, 18), (3, 20),
                (4, 18), (4, 20),
                (5, 18), (5, 20),
                (6, 18), (6, 19), (6, 20),
            ]
        else:
            # Generic text pattern
            return [(3, x) for x in range(2, min(30, len(self.text) * 2))]


class GlowingText(EnhancedDisplayContent):
    """Text with edge glow effect."""
    
    def __init__(self, text: str, text_color: int = 0xFFFFFF, glow_color: int = 0x00FFFF, duration: Optional[float] = None):
        """Initialize glowing text.
        
        Args:
            text: Text to display
            text_color: Text color
            glow_color: Glow effect color
            duration: Display duration
        """
        super().__init__(duration, enable_effects=True)
        self.text: str = text
        self.text_color: int = text_color
        self.glow_color: int = glow_color
        
        # Add glow effect
        if self.effects_engine:
            glow = EdgeGlowEffect(color=glow_color)
            self.add_effect(glow)
    
    async def render_base_content(self, display) -> None:
        """Render text with center focus."""
        # Dark background for contrast
        for y in range(display.height):
            for x in range(display.width):
                await display.set_pixel(x, y, 0x001122)
        
        # Render text in center
        text_pixels = self._get_centered_text_pixels(display)
        
        for y, x in text_pixels:
            if 0 <= x < display.width and 0 <= y < display.height:
                await display.set_pixel(x, y, self.text_color)
    
    def _get_centered_text_pixels(self, display) -> List[tuple]:
        """Get centered text pixels.
        
        Args:
            display: Display interface
            
        Returns:
            list: List of (y, x) pixel coordinates
        """
        center_x = display.width // 2
        center_y = display.height // 2
        
        # Simple centered text pattern
        return [
            (center_y - 1, center_x - 2),
            (center_y - 1, center_x - 1),
            (center_y - 1, center_x),
            (center_y - 1, center_x + 1),
            (center_y - 1, center_x + 2),
            (center_y, center_x - 3),
            (center_y, center_x - 2),
            (center_y, center_x - 1),
            (center_y, center_x),
            (center_y, center_x + 1),
            (center_y, center_x + 2),
            (center_y, center_x + 3),
            (center_y + 1, center_x - 2),
            (center_y + 1, center_x - 1),
            (center_y + 1, center_x),
            (center_y + 1, center_x + 1),
            (center_y + 1, center_x + 2),
        ]


class AnimatedBackground(EnhancedDisplayContent):
    """Animated background with particle effects."""
    
    def __init__(self, background_color: int = 0x001133, particle_type: str = "sparkle", 
                 particle_intensity: int = 3, duration: Optional[float] = None):
        """Initialize animated background.
        
        Args:
            background_color: Base background color
            particle_type: Type of particles ("sparkle", "rain", "snow")
            particle_intensity: Particle spawn rate
            duration: Display duration
        """
        super().__init__(duration, enable_effects=True)
        self.background_color: int = background_color
        self.particle_type: str = particle_type
        self.particle_intensity: int = particle_intensity
        self.last_spawn_time: float = 0
        self.spawn_interval: float = 0.5  # Spawn particles every 500ms
    
    async def render_base_content(self, display) -> None:
        """Render animated background."""
        # Fill with background color
        for y in range(display.height):
            for x in range(display.width):
                await display.set_pixel(x, y, self.background_color)
        
        # Spawn particles occasionally
        import time
        current_time = time.time()
        
        if current_time - self.last_spawn_time > self.spawn_interval:
            self._spawn_particles(display)
            self.last_spawn_time = current_time
    
    def _spawn_particles(self, display) -> None:
        """Spawn particles based on type."""
        import random
        
        for _ in range(self.particle_intensity):
            x = random.randint(0, display.width - 1)
            
            if self.particle_type == "sparkle":
                y = random.randint(0, display.height - 1)
                color = random.choice([0xFFFFFF, 0xFFFF00, 0xFF00FF, 0x00FFFF])
                particle = Sparkle(x, y, color=color, lifetime=1.5)
                self.add_particle(particle)
            
            elif self.particle_type == "rain":
                from ..effects.particles import RainDrop
                raindrop = RainDrop(x, -1, speed=10.0, color=0x4080FF)
                self.add_particle(raindrop)
            
            elif self.particle_type == "snow":
                from ..effects.particles import Snow
                snowflake = Snow(x, -1, speed=4.0, sway=1.5)
                self.add_particle(snowflake)


class RainbowText(EnhancedDisplayContent):
    """Text with rainbow color cycling."""
    
    def __init__(self, text: str, cycle_speed: float = 1.0, duration: Optional[float] = None):
        """Initialize rainbow text.
        
        Args:
            text: Text to display
            cycle_speed: Color cycling speed
            duration: Display duration
        """
        super().__init__(duration, enable_effects=False)  # No effects engine needed
        self.text: str = text
        self.cycle_speed: float = cycle_speed
        
        # Pre-calculated rainbow colors
        self.rainbow_colors: List[int] = [
            0xFF0000, 0xFF3300, 0xFF6600, 0xFF9900, 0xFFCC00, 0xFFFF00,
            0xCCFF00, 0x99FF00, 0x66FF00, 0x33FF00, 0x00FF00, 0x00FF33,
            0x00FF66, 0x00FF99, 0x00FFCC, 0x00FFFF, 0x00CCFF, 0x0099FF,
            0x0066FF, 0x0033FF, 0x0000FF, 0x3300FF, 0x6600FF, 0x9900FF,
            0xCC00FF, 0xFF00FF, 0xFF00CC, 0xFF0099, 0xFF0066, 0xFF0033
        ]
    
    async def render_base_content(self, display) -> None:
        """Render rainbow text."""
        # Calculate current color based on elapsed time
        color_index = int(self.elapsed * self.cycle_speed * 5) % len(self.rainbow_colors)
        current_color = self.rainbow_colors[color_index]
        
        # Render text with current rainbow color
        text_pixels = self._get_text_pixels()
        
        for y, x in text_pixels:
            if 0 <= x < display.width and 0 <= y < display.height:
                await display.set_pixel(x, y, current_color)
    
    def _get_text_pixels(self) -> List[tuple]:
        """Get text pixel positions."""
        # Simple text pattern for demo
        return [(4, x) for x in range(5, 25)]  # Horizontal line of text