"""Particle effects for SLDK.

Simple particle systems optimized for ESP32 memory constraints.
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
    import time
    get_time = time.time

try:
    import random
except ImportError:
    # Simple random for CircuitPython if needed
    class SimpleRandom:
        def __init__(self):
            self.seed = int(get_time() * 1000) % 65536
        
        def randint(self, a, b):
            self.seed = (self.seed * 1103515245 + 12345) & 0x7fffffff
            return a + (self.seed % (b - a + 1))
        
        def random(self):
            return self.randint(0, 1000) / 1000.0
    
    random = SimpleRandom()


class ParticleEngine:
    """Lightweight particle engine for ESP32."""
    
    def __init__(self, max_particles: int = 8) -> None:
        """Initialize particle engine.
        
        Args:
            max_particles: Maximum number of particles (keep low for ESP32)
        """
        self.max_particles: int = max_particles
        self.particles: list = []
        self.last_spawn_time: float = 0
    
    def add_particle(self, particle: Any) -> bool:
        """Add particle to system.
        
        Args:
            particle: Particle instance
        """
        if len(self.particles) < self.max_particles:
            particle.spawn_time = get_time()
            self.particles.append(particle)
            return True
        return False
    
    async def update(self, display: Any) -> None:
        """Update all particles.
        
        Args:
            display: Display interface
        """
        current_time = get_time()
        
        # Update particles (backwards to allow removal)
        for i in range(len(self.particles) - 1, -1, -1):
            particle = self.particles[i]
            elapsed = current_time - particle.spawn_time
            
            # Remove dead particles
            if particle.is_dead(elapsed):
                self.particles.pop(i)
                continue
            
            # Update and render particle
            particle.update(elapsed)
            await particle.render(display)
    
    def clear_particles(self) -> None:
        """Remove all particles."""
        self.particles.clear()
    
    def get_particle_count(self) -> int:
        """Get current particle count."""
        return len(self.particles)


class Particle:
    """Base particle class."""
    
    def __init__(self, x: int, y: int, lifetime: float = 2.0) -> None:
        """Initialize particle.
        
        Args:
            x: Starting X position
            y: Starting Y position
            lifetime: Particle lifetime in seconds
        """
        self.start_x: int = x
        self.start_y: int = y
        self.x: float = float(x)
        self.y: float = float(y)
        self.lifetime: float = lifetime
        self.spawn_time: float = 0
    
    def update(self, elapsed_time: float) -> None:
        """Update particle physics.
        
        Args:
            elapsed_time: Time since spawn
        """
        pass  # Override in subclasses
    
    async def render(self, display: Any) -> None:
        """Render particle to display.
        
        Args:
            display: Display interface
        """
        pass  # Override in subclasses
    
    def is_dead(self, elapsed_time: float) -> bool:
        """Check if particle should be removed.
        
        Args:
            elapsed_time: Time since spawn
            
        Returns:
            bool: True if particle is dead
        """
        return elapsed_time > self.lifetime
    
    def get_life_ratio(self, elapsed_time: float) -> float:
        """Get life ratio (0.0 = just born, 1.0 = about to die).
        
        Args:
            elapsed_time: Time since spawn
            
        Returns:
            float: Life ratio
        """
        return min(elapsed_time / self.lifetime, 1.0)


class Sparkle(Particle):
    """Simple sparkle particle."""
    
    def __init__(self, x: int, y: int, color: int = 0xFFFFFF, lifetime: float = 1.0) -> None:
        """Initialize sparkle.
        
        Args:
            x: X position
            y: Y position
            color: Sparkle color
            lifetime: How long sparkle lasts
        """
        super().__init__(x, y, lifetime)
        self.color: int = color
        self.peak_time: float = lifetime * 0.2  # Peak brightness at 20% of lifetime
    
    async def render(self, display: Any) -> None:
        """Render sparkle with fading."""
        # Check bounds
        x = int(self.x)
        y = int(self.y)
        
        if not (0 <= x < display.width and 0 <= y < display.height):
            return
        
        # Calculate brightness based on age
        life_ratio = self.get_life_ratio(get_time() - self.spawn_time)
        
        if life_ratio < 0.2:
            # Growing phase
            brightness = life_ratio / 0.2
        else:
            # Fading phase
            brightness = 1.0 - ((life_ratio - 0.2) / 0.8)
        
        brightness = max(0.0, min(1.0, brightness))
        
        # Apply brightness to color
        r = int(((self.color >> 16) & 0xFF) * brightness)
        g = int(((self.color >> 8) & 0xFF) * brightness)
        b = int((self.color & 0xFF) * brightness)
        
        final_color = (r << 16) | (g << 8) | b
        await display.set_pixel(x, y, final_color)


class RainDrop(Particle):
    """Rain drop particle that falls down."""
    
    def __init__(self, x: int, y: int, speed: float = 10.0, color: int = 0x0080FF, lifetime: float = 3.0) -> None:
        """Initialize rain drop.
        
        Args:
            x: Starting X position
            y: Starting Y position
            speed: Fall speed (pixels per second)
            color: Drop color
            lifetime: Maximum lifetime
        """
        super().__init__(x, y, lifetime)
        self.speed: float = speed
        self.color: int = color
    
    def update(self, elapsed_time: float) -> None:
        """Update rain drop physics."""
        # Move down
        self.y = self.start_y + (self.speed * elapsed_time)
    
    async def render(self, display: Any) -> None:
        """Render rain drop."""
        x = int(self.x)
        y = int(self.y)
        
        # Check if still on screen
        if not (0 <= x < display.width and 0 <= y < display.height):
            return
        
        await display.set_pixel(x, y, self.color)
    
    def is_dead(self, elapsed_time: float) -> bool:
        """Rain drop dies when it falls off screen."""
        return (self.y >= 32) or super().is_dead(elapsed_time)  # Assume 32 pixel height


class Ember(Particle):
    """Fire ember that rises and fades."""
    
    def __init__(self, x: int, y: int, speed: float = 5.0, drift: float = 2.0, lifetime: float = 2.0) -> None:
        """Initialize ember.
        
        Args:
            x: Starting X position
            y: Starting Y position
            speed: Rise speed
            drift: Horizontal drift amount
            lifetime: Ember lifetime
        """
        super().__init__(x, y, lifetime)
        self.speed = speed
        self.drift = drift
        self.drift_direction = 1 if random.random() > 0.5 else -1
        
        # Ember colors (red to yellow to white)
        self.colors: list[int] = [0xFF0000, 0xFF3300, 0xFF6600, 0xFF9900, 0xFFCC00, 0xFFFF00]
    
    def update(self, elapsed_time: float) -> None:
        """Update ember physics."""
        # Move up
        self.y = self.start_y - (self.speed * elapsed_time)
        
        # Drift sideways
        drift_amount = self.drift * elapsed_time * self.drift_direction
        self.x = self.start_x + drift_amount
    
    async def render(self, display: Any) -> None:
        """Render ember with color transition."""
        x = int(self.x)
        y = int(self.y)
        
        if not (0 <= x < display.width and 0 <= y < display.height):
            return
        
        # Color changes over lifetime
        life_ratio = self.get_life_ratio(get_time() - self.spawn_time)
        color_index = int(life_ratio * (len(self.colors) - 1))
        color_index = min(color_index, len(self.colors) - 1)
        
        # Fade brightness over time
        brightness = 1.0 - life_ratio
        color = self.colors[color_index]
        
        r = int(((color >> 16) & 0xFF) * brightness)
        g = int(((color >> 8) & 0xFF) * brightness)
        b = int((color & 0xFF) * brightness)
        
        final_color = (r << 16) | (g << 8) | b
        await display.set_pixel(x, y, final_color)
    
    def is_dead(self, elapsed_time: float) -> bool:
        """Ember dies when it rises off screen or expires."""
        return (self.y < 0) or super().is_dead(elapsed_time)


class Snow(Particle):
    """Snow flake that falls gently."""
    
    def __init__(self, x: int, y: int, speed: float = 3.0, sway: float = 1.0, lifetime: float = 5.0) -> None:
        """Initialize snow flake.
        
        Args:
            x: Starting X position
            y: Starting Y position
            speed: Fall speed
            sway: Side-to-side sway amount
            lifetime: Snow lifetime
        """
        super().__init__(x, y, lifetime)
        self.speed = speed
        self.sway = sway
        self.sway_phase: float = random.random() * 6.28  # Random phase for sway
    
    def update(self, elapsed_time: float) -> None:
        """Update snow physics."""
        # Fall down
        self.y = self.start_y + (self.speed * elapsed_time)
        
        # Sway side to side
        import math
        sway_offset = self.sway * math.sin(elapsed_time * 2 + self.sway_phase)
        self.x = self.start_x + sway_offset
    
    async def render(self, display: Any) -> None:
        """Render snow flake."""
        x = int(self.x)
        y = int(self.y)
        
        if not (0 <= x < display.width and 0 <= y < display.height):
            return
        
        # White snow flake
        await display.set_pixel(x, y, 0xFFFFFF)
    
    def is_dead(self, elapsed_time: float) -> bool:
        """Snow dies when it falls off screen."""
        return (self.y >= 32) or super().is_dead(elapsed_time)