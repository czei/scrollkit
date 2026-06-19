"""Transition effects for SLDK.

Provides simple transition effects optimized for ESP32 performance.
"""

from __future__ import annotations

try:
    import time
    get_time = time.monotonic
except (ImportError, AttributeError):
    import time
    get_time = time.time

try:
    from typing import Any, Optional
except ImportError:  # CircuitPython has no 'typing' module
    pass

from ..exceptions import DisplayError


class TransitionEngine:
    """Engine for managing content transitions."""
    
    def __init__(self) -> None:
        """Initialize transition engine."""
        self.active_transition = None
        self.transition_start_time: float = 0
    
    async def start_transition(self, transition: Any, from_content: Any, to_content: Any) -> None:
        """Start a transition between content.
        
        Args:
            transition: Transition effect instance
            from_content: Current content
            to_content: New content to transition to
        """
        self.active_transition = transition
        self.transition_start_time = get_time()
        transition.from_content = from_content
        transition.to_content = to_content
        await transition.start()
    
    async def update(self, display: Any) -> None:
        """Update active transition.
        
        Args:
            display: Display interface
        """
        if not self.active_transition:
            return
        
        elapsed = get_time() - self.transition_start_time
        progress = min(elapsed / self.active_transition.duration, 1.0)
        
        await self.active_transition.update(display, progress)
        
        if progress >= 1.0:
            await self.active_transition.complete()
            self.active_transition = None
    
    def is_transitioning(self) -> bool:
        """Check if a transition is active.
        
        Returns:
            bool: True if transition is active
        """
        return self.active_transition is not None


class BaseTransition:
    """Base class for transitions."""
    
    def __init__(self, duration: float = 1.0) -> None:
        """Initialize transition.
        
        Args:
            duration: Transition duration in seconds
        """
        self.duration: float = duration
        self.from_content: Any = None
        self.to_content: Any = None
    
    async def start(self) -> None:
        """Called when transition starts."""
        pass
    
    async def update(self, display: Any, progress: float) -> None:
        """Update transition.
        
        Args:
            display: Display interface
            progress: Transition progress (0.0 to 1.0)
        """
        raise NotImplementedError("Subclass must implement update()")
    
    async def complete(self) -> None:
        """Called when transition completes."""
        pass


class FadeTransition(BaseTransition):
    """Fade transition using display brightness."""
    
    def __init__(self, duration: float = 1.0, fade_color: int = 0x000000) -> None:
        """Initialize fade transition.
        
        Args:
            duration: Transition duration
            fade_color: Color to fade through (default black)
        """
        super().__init__(duration)
        self.fade_color: int = fade_color
        self.original_brightness: float = 1.0
        self.phase: str = "fade_out"  # fade_out -> fade_in
    
    async def start(self) -> None:
        """Store original brightness."""
        # Try to get original brightness
        if hasattr(self.from_content, 'display') and hasattr(self.from_content.display, 'brightness'):
            self.original_brightness = self.from_content.display.brightness
        else:
            self.original_brightness = 1.0
    
    async def update(self, display: Any, progress: float) -> None:
        """Update fade transition."""
        if not hasattr(display, 'brightness'):
            # Fallback to instant transition if brightness not supported
            if progress < 0.5:
                if self.from_content:
                    await self.from_content.render(display)
            else:
                if self.to_content:
                    await self.to_content.render(display)
            return
        
        # Two-phase fade: out then in
        if progress < 0.5:
            # Fade out phase
            fade_progress = progress * 2  # 0 to 1
            brightness = self.original_brightness * (1.0 - fade_progress)
            display.brightness = max(brightness, 0.01)  # Prevent complete darkness
            
            # Render original content
            if self.from_content:
                await self.from_content.render(display)
        else:
            # Fade in phase
            fade_progress = (progress - 0.5) * 2  # 0 to 1
            brightness = self.original_brightness * fade_progress
            display.brightness = min(brightness, self.original_brightness)
            
            # Render new content
            if self.to_content:
                await self.to_content.render(display)
    
    async def complete(self) -> None:
        """Restore original brightness."""
        if hasattr(self.to_content, 'display') and hasattr(self.to_content.display, 'brightness'):
            self.to_content.display.brightness = self.original_brightness


class WipeTransition(BaseTransition):
    """Wipe transition - progressive reveal."""
    
    def __init__(self, duration: float = 1.0, direction: str = "left") -> None:
        """Initialize wipe transition.
        
        Args:
            duration: Transition duration
            direction: Wipe direction ("left", "right", "up", "down")
        """
        super().__init__(duration)
        self.direction: str = direction
    
    async def update(self, display: Any, progress: float) -> None:
        """Update wipe transition."""
        width = display.width
        height = display.height
        
        if self.direction == "left":
            # Wipe from left to right
            split_x = int(progress * width)
            
            for y in range(height):
                for x in range(width):
                    if x < split_x:
                        # Show new content
                        if self.to_content:
                            # Get pixel color from new content (simplified)
                            color = self._get_content_pixel_color(x, y, progress)
                            await display.set_pixel(x, y, color)
                    # Old content pixels are left unchanged
        
        elif self.direction == "right":
            # Wipe from right to left
            split_x = width - int(progress * width)
            
            for y in range(height):
                for x in range(width):
                    if x >= split_x:
                        # Show new content
                        color = self._get_content_pixel_color(x, y, progress)
                        await display.set_pixel(x, y, color)
        
        elif self.direction == "up":
            # Wipe from top to bottom
            split_y = int(progress * height)
            
            for y in range(height):
                for x in range(width):
                    if y < split_y:
                        # Show new content
                        color = self._get_content_pixel_color(x, y, progress)
                        await display.set_pixel(x, y, color)
        
        elif self.direction == "down":
            # Wipe from bottom to top
            split_y = height - int(progress * height)
            
            for y in range(height):
                for x in range(width):
                    if y >= split_y:
                        # Show new content
                        color = self._get_content_pixel_color(x, y, progress)
                        await display.set_pixel(x, y, color)
    
    def _get_content_pixel_color(self, x: int, y: int, progress: float) -> int:
        """Get pixel color for new content at position.
        
        This is a simplified implementation - in reality you'd
        render the content to a buffer first, but that uses too
        much memory for ESP32.
        
        Args:
            x: X coordinate
            y: Y coordinate
            progress: Transition progress
            
        Returns:
            int: RGB color value
        """
        # Simple colored pattern for demonstration
        # In real implementation, this would query the actual content
        
        # Create a simple gradient based on position
        r = int((x / 64.0) * 255) if hasattr(self, '_width') else int((x / 32.0) * 255)
        g = int((y / 32.0) * 255) if hasattr(self, '_height') else int((y / 16.0) * 255)
        b = int(progress * 255)
        
        return (r << 16) | (g << 8) | b


class SlideTransition(BaseTransition):
    """Slide transition - content slides in from edge."""
    
    def __init__(self, duration: float = 1.0, direction: str = "left", easing: str = "linear") -> None:
        """Initialize slide transition.
        
        Args:
            duration: Transition duration
            direction: Slide direction ("left", "right", "up", "down")
            easing: Easing function ("linear", "ease_out")
        """
        super().__init__(duration)
        self.direction: str = direction
        self.easing: str = easing
    
    def _apply_easing(self, progress: float) -> float:
        """Apply easing function to progress.
        
        Args:
            progress: Linear progress (0.0 to 1.0)
            
        Returns:
            float: Eased progress
        """
        if self.easing == "ease_out":
            # Simple ease-out: 1 - (1-t)^2
            return 1 - (1 - progress) ** 2
        else:
            # Linear
            return progress
    
    async def update(self, display: Any, progress: float) -> None:
        """Update slide transition."""
        eased_progress = self._apply_easing(progress)
        
        width = display.width
        height = display.height
        
        # Clear display first
        await display.clear()
        
        if self.direction == "left":
            # Slide from left edge
            offset_x = int(eased_progress * width) - width
            
            # Render new content at offset position
            await self._render_content_at_offset(display, self.to_content, offset_x, 0)
            
        elif self.direction == "right":
            # Slide from right edge
            offset_x = width - int(eased_progress * width)
            
            # Render new content at offset position
            await self._render_content_at_offset(display, self.to_content, offset_x, 0)
        
        elif self.direction == "up":
            # Slide from top edge
            offset_y = int(eased_progress * height) - height
            
            # Render new content at offset position
            await self._render_content_at_offset(display, self.to_content, 0, offset_y)
        
        elif self.direction == "down":
            # Slide from bottom edge
            offset_y = height - int(eased_progress * height)
            
            # Render new content at offset position
            await self._render_content_at_offset(display, self.to_content, 0, offset_y)
    
    async def _render_content_at_offset(self, display: Any, content: Any, offset_x: int, offset_y: int) -> None:
        """Render content at offset position.
        
        Args:
            display: Display interface
            content: Content to render
            offset_x: X offset
            offset_y: Y offset
        """
        # Simplified rendering - create a colored rectangle for demo
        width = display.width
        height = display.height
        
        # Demo: render a simple colored rectangle
        for y in range(height):
            for x in range(width):
                render_x = x + offset_x
                render_y = y + offset_y
                
                # Only render if within display bounds
                if 0 <= render_x < width and 0 <= render_y < height:
                    # Simple color pattern for demo
                    color = ((render_x * 4) << 16) | ((render_y * 8) << 8) | 0x80
                    await display.set_pixel(render_x, render_y, color)