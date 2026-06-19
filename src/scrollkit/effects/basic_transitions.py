"""Basic transition effects for SLDK.

Provides simple but effective transition effects that work well on
LED matrices with CircuitPython performance constraints.
"""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional, Tuple

from ..exceptions import DisplayError
from .base import Effect, register_effect

try:
    # CircuitPython compatibility
    import asyncio
except ImportError:
    asyncio = None


@register_effect('fade_in')
class FadeInEffect(Effect):
    """Fade in effect using display brightness control."""
    
    def __init__(self, duration: float = 1.0, **kwargs):
        """Initialize fade in effect.
        
        Args:
            duration: Fade duration in seconds
            **kwargs: Additional effect parameters
        """
        super().__init__(duration=duration, **kwargs)
    
    async def apply(self, display: Any, render_func: Callable[..., Any]) -> None:
        """Apply fade in effect."""
        # Store original brightness
        original_brightness = getattr(display, 'brightness', 1.0)
        
        # Start with brightness at 0
        if hasattr(display, 'brightness'):
            display.brightness = 0.0
        
        # Render content (at zero brightness)
        await render_func()
        await display.show()
        
        # Fade in by gradually increasing brightness
        steps = 20  # 20 steps for smooth fade
        step_duration = self.duration / steps
        
        for step in range(steps + 1):
            progress = step / steps
            brightness = progress * original_brightness
            
            if hasattr(display, 'brightness'):
                display.brightness = brightness
            
            await display.show()
            
            if step < steps:
                if asyncio:
                    await asyncio.sleep(step_duration)
                else:
                    time.sleep(step_duration)
        
        # Ensure brightness is restored
        if hasattr(display, 'brightness'):
            display.brightness = original_brightness


@register_effect('slide_in')
class SlideInEffect(Effect):
    """Slide in effect that moves content from off-screen."""
    
    def __init__(self, 
                 duration: float = 1.0,
                 direction: str = 'left',  # 'left', 'right', 'up', 'down'
                 **kwargs):
        """Initialize slide in effect.
        
        Args:
            duration: Slide duration in seconds
            direction: Direction to slide from
            **kwargs: Additional effect parameters
        """
        super().__init__(duration=duration, **kwargs)
        self.direction = direction
    
    async def apply(self, display: Any, render_func: Callable[..., Any]) -> None:
        """Apply slide in effect."""
        # Get display dimensions
        width = getattr(display, 'width', 64)
        height = getattr(display, 'height', 32)
        
        # Calculate slide distance
        if self.direction in ['left', 'right']:
            slide_distance = width
        else:  # up, down
            slide_distance = height
        
        # Slide animation
        steps = min(slide_distance, 32)  # Limit steps for performance
        step_duration = self.duration / steps if steps > 0 else 0
        
        for step in range(steps + 1):
            progress = step / steps if steps > 0 else 1.0
            
            # Calculate offset based on direction and progress
            offset_x, offset_y = self._calculate_slide_offset(
                slide_distance, progress
            )
            
            # Clear display
            await display.clear()
            
            # Render with offset
            await self._render_with_offset(display, render_func, offset_x, offset_y)
            
            # Update display
            await display.show()
            
            # Wait for next step
            if step < steps and step_duration > 0:
                if asyncio:
                    await asyncio.sleep(step_duration)
                else:
                    time.sleep(step_duration)
    
    def _calculate_slide_offset(self, distance: int, progress: float) -> Tuple[int, int]:
        """Calculate slide offset for current progress.
        
        Args:
            distance: Total slide distance
            progress: Animation progress (0.0 to 1.0)
            
        Returns:
            Tuple of (offset_x, offset_y)
        """
        # Calculate how much we've moved from the starting position
        moved_distance = int(distance * progress)
        
        if self.direction == 'left':
            # Start from right, slide to left
            return (distance - moved_distance, 0)
        elif self.direction == 'right':
            # Start from left, slide to right
            return (-distance + moved_distance, 0)
        elif self.direction == 'up':
            # Start from bottom, slide up
            return (0, distance - moved_distance)
        elif self.direction == 'down':
            # Start from top, slide down
            return (0, -distance + moved_distance)
        else:
            return (0, 0)
    
    async def _render_with_offset(self, display: Any, render_func: Callable[..., Any], 
                                offset_x: int, offset_y: int) -> None:
        """Render content with position offset.
        
        This is a simplified implementation. A full implementation would
        require the display interface to support offset rendering.
        """
        # Store original offset if display supports it
        original_offset = getattr(display, '_render_offset', (0, 0))
        
        # Set render offset if supported
        if hasattr(display, 'set_render_offset'):
            await display.set_render_offset(offset_x, offset_y)
        
        try:
            # Render content with offset
            await render_func()
        finally:
            # Restore original offset
            if hasattr(display, 'set_render_offset'):
                await display.set_render_offset(*original_offset)


@register_effect('wipe')
class WipeEffect(Effect):
    """Wipe effect that replaces old content with new content."""
    
    def __init__(self, 
                 duration: float = 1.0,
                 direction: str = 'right',  # 'left', 'right', 'up', 'down'
                 **kwargs):
        """Initialize wipe effect.
        
        Args:
            duration: Wipe duration in seconds
            direction: Direction of wipe
            **kwargs: Additional effect parameters
        """
        super().__init__(duration=duration, **kwargs)
        self.direction = direction
    
    async def apply(self, display: Any, render_func: Callable[..., Any]) -> None:
        """Apply wipe effect.
        
        Note: This is a simplified implementation. A full wipe effect
        would need to capture the previous display state.
        """
        # Get display dimensions
        width = getattr(display, 'width', 64)
        height = getattr(display, 'height', 32)
        
        # Calculate steps
        if self.direction in ['left', 'right']:
            steps = width
        else:  # up, down
            steps = height
        
        step_duration = self.duration / steps if steps > 0 else 0
        
        # Perform wipe animation
        for step in range(steps + 1):
            # Calculate wipe area
            wipe_area = self._calculate_wipe_area(width, height, step, steps)
            
            # Clear display
            await display.clear()
            
            # Render new content with clipping to wiped area
            await self._render_with_wipe_clipping(display, render_func, wipe_area)
            
            # Update display
            await display.show()
            
            # Wait for next step
            if step < steps and step_duration > 0:
                if asyncio:
                    await asyncio.sleep(step_duration)
                else:
                    time.sleep(step_duration)
    
    def _calculate_wipe_area(self, width: int, height: int, 
                           step: int, total_steps: int) -> Dict[str, Any]:
        """Calculate the wiped area for current step."""
        progress = step / total_steps if total_steps > 0 else 1.0
        
        if self.direction == 'right':
            # Wipe from left to right
            wipe_width = int(width * progress)
            return {
                'x_start': 0,
                'x_end': wipe_width,
                'y_start': 0,
                'y_end': height
            }
        elif self.direction == 'left':
            # Wipe from right to left
            wipe_width = int(width * progress)
            return {
                'x_start': width - wipe_width,
                'x_end': width,
                'y_start': 0,
                'y_end': height
            }
        elif self.direction == 'down':
            # Wipe from top to bottom
            wipe_height = int(height * progress)
            return {
                'x_start': 0,
                'x_end': width,
                'y_start': 0,
                'y_end': wipe_height
            }
        elif self.direction == 'up':
            # Wipe from bottom to top
            wipe_height = int(height * progress)
            return {
                'x_start': 0,
                'x_end': width,
                'y_start': height - wipe_height,
                'y_end': height
            }
        else:
            # Default: entire area
            return {
                'x_start': 0,
                'x_end': width,
                'y_start': 0,
                'y_end': height
            }
    
    async def _render_with_wipe_clipping(self, display: Any, render_func: Callable[..., Any], 
                                       wipe_area: Dict[str, Any]) -> None:
        """Render content with wipe clipping."""
        # Set clipping area if supported
        if hasattr(display, 'set_clip_area'):
            await display.set_clip_area(
                wipe_area['x_start'],
                wipe_area['y_start'],
                wipe_area['x_end'],
                wipe_area['y_end']
            )
        
        try:
            await render_func()
        finally:
            if hasattr(display, 'clear_clip_area'):
                await display.clear_clip_area()


@register_effect('pulse')
class PulseEffect(Effect):
    """Pulse effect that varies brightness rhythmically."""
    
    def __init__(self, 
                 duration: float = 2.0,
                 pulses: int = 2,
                 min_brightness: float = 0.3,
                 max_brightness: float = 1.0,
                 **kwargs):
        """Initialize pulse effect.
        
        Args:
            duration: Total effect duration in seconds
            pulses: Number of pulses
            min_brightness: Minimum brightness (0.0-1.0)
            max_brightness: Maximum brightness (0.0-1.0)
            **kwargs: Additional effect parameters
        """
        super().__init__(duration=duration, **kwargs)
        self.pulses = pulses
        self.min_brightness = min_brightness
        self.max_brightness = max_brightness
    
    async def apply(self, display: Any, render_func: Callable[..., Any]) -> None:
        """Apply pulse effect."""
        # Store original brightness
        original_brightness = getattr(display, 'brightness', 1.0)
        
        # Render content once
        await render_func()
        
        # Pulse animation
        total_steps = self.pulses * 20  # 20 steps per pulse
        step_duration = self.duration / total_steps if total_steps > 0 else 0
        
        for step in range(total_steps + 1):
            # Calculate pulse progress (0 to 1 and back)
            pulse_progress = (step % 20) / 10.0  # 0 to 2
            if pulse_progress > 1.0:
                pulse_progress = 2.0 - pulse_progress  # 2 to 1 becomes 0 to 1
            
            # Map to brightness range
            brightness_range = self.max_brightness - self.min_brightness
            brightness = self.min_brightness + pulse_progress * brightness_range
            
            # Apply brightness
            if hasattr(display, 'brightness'):
                display.brightness = brightness
            
            await display.show()
            
            # Wait for next step
            if step < total_steps and step_duration > 0:
                if asyncio:
                    await asyncio.sleep(step_duration)
                else:
                    time.sleep(step_duration)
        
        # Restore original brightness
        if hasattr(display, 'brightness'):
            display.brightness = original_brightness


@register_effect('flash')
class FlashEffect(Effect):
    """Flash effect that briefly shows content at full brightness."""
    
    def __init__(self, 
                 duration: float = 0.5,
                 flashes: int = 3,
                 flash_brightness: float = 1.0,
                 **kwargs):
        """Initialize flash effect.
        
        Args:
            duration: Total effect duration in seconds
            flashes: Number of flashes
            flash_brightness: Brightness during flash
            **kwargs: Additional effect parameters
        """
        super().__init__(duration=duration, **kwargs)
        self.flashes = flashes
        self.flash_brightness = flash_brightness
    
    async def apply(self, display: Any, render_func: Callable[..., Any]) -> None:
        """Apply flash effect."""
        # Store original brightness
        original_brightness = getattr(display, 'brightness', 1.0)
        
        # Calculate timing
        flash_duration = self.duration / (self.flashes * 2)  # On and off periods
        
        for flash in range(self.flashes):
            # Flash on
            if hasattr(display, 'brightness'):
                display.brightness = self.flash_brightness
            
            await render_func()
            await display.show()
            
            if asyncio:
                await asyncio.sleep(flash_duration)
            else:
                time.sleep(flash_duration)
            
            # Flash off (or dim)
            if hasattr(display, 'brightness'):
                display.brightness = original_brightness * 0.1  # Very dim
            
            await display.show()
            
            if flash < self.flashes - 1:  # Don't wait after last flash
                if asyncio:
                    await asyncio.sleep(flash_duration)
                else:
                    time.sleep(flash_duration)
        
        # Restore original brightness and content
        if hasattr(display, 'brightness'):
            display.brightness = original_brightness
        
        await render_func()
        await display.show()