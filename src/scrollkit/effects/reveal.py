"""Reveal effect for SLDK.

Provides a reveal animation that gradually shows content by unveiling
it from one side to the other, similar to wiping away a cover.
"""

from __future__ import annotations

import time
try:
    from typing import Any, Callable, Dict, Optional
except ImportError:  # CircuitPython has no 'typing' module
    pass

from ..exceptions import DisplayError
from .base import Effect, register_effect

try:
    # CircuitPython compatibility
    import asyncio
except ImportError:
    asyncio = None


@register_effect('reveal')
class RevealEffect(Effect):
    """Reveal effect that gradually unveils content.
    
    The reveal effect shows content progressively from one side to another,
    creating a dramatic unveiling animation. This is particularly effective
    for splash screens and important messages.
    """
    
    def __init__(self, 
                 duration: float = 2.0,
                 direction: str = 'right',
                 steps: int = None,
                 pause_at_end: float = 1.0,
                 **kwargs):
        """Initialize reveal effect.
        
        Args:
            duration: Time for the reveal animation in seconds
            direction: Direction of reveal ('left', 'right', 'up', 'down')
            steps: Number of reveal steps (None for smooth based on display width)
            pause_at_end: Time to pause after reveal is complete
            **kwargs: Additional effect parameters
        """
        # Total duration includes reveal time plus pause
        total_duration = duration + pause_at_end
        super().__init__(duration=total_duration, **kwargs)
        
        self.reveal_duration = duration
        self.direction = direction
        self.steps = steps
        self.pause_at_end = pause_at_end
    
    async def apply(self, display: Any, render_func: Callable[..., Any]) -> None:
        """Apply the reveal effect.
        
        Args:
            display: Display interface to render to
            render_func: Function that renders the base content
        """
        start_time = time.time()
        
        # Get display dimensions
        width = getattr(display, 'width', 64)
        height = getattr(display, 'height', 32)
        
        # Calculate steps if not provided
        if self.steps is None:
            if self.direction in ['left', 'right']:
                self.steps = width
            else:  # up, down
                self.steps = height
        
        # Pre-render the content to a buffer if possible
        # For now, we'll render on-demand for each step
        
        # Perform reveal animation
        step_duration = self.reveal_duration / self.steps
        
        for step in range(self.steps + 1):  # +1 to include final complete state
            # Calculate reveal area based on direction and step
            reveal_area = self._calculate_reveal_area(width, height, step)
            
            # Clear display
            await display.clear()
            
            # Render content with clipping to reveal area
            await self._render_with_clipping(display, render_func, reveal_area)
            
            # Update display
            await display.show()
            
            # Wait for next step (except on last step)
            if step < self.steps:
                if asyncio:
                    await asyncio.sleep(step_duration)
                else:
                    time.sleep(step_duration)
        
        # Pause at end with full content displayed
        if self.pause_at_end > 0:
            if asyncio:
                await asyncio.sleep(self.pause_at_end)
            else:
                time.sleep(self.pause_at_end)
    
    def _calculate_reveal_area(self, width: int, height: int, step: int) -> Dict[str, Any]:
        """Calculate the reveal area for the given step.
        
        Args:
            width: Display width
            height: Display height
            step: Current step (0 to self.steps)
            
        Returns:
            Dictionary with reveal area bounds
        """
        progress = step / self.steps if self.steps > 0 else 1.0
        
        if self.direction == 'right':
            # Reveal from left to right
            reveal_width = int(width * progress)
            return {
                'x_start': 0,
                'x_end': reveal_width,
                'y_start': 0,
                'y_end': height
            }
        elif self.direction == 'left':
            # Reveal from right to left
            reveal_width = int(width * progress)
            return {
                'x_start': width - reveal_width,
                'x_end': width,
                'y_start': 0,
                'y_end': height
            }
        elif self.direction == 'down':
            # Reveal from top to bottom
            reveal_height = int(height * progress)
            return {
                'x_start': 0,
                'x_end': width,
                'y_start': 0,
                'y_end': reveal_height
            }
        elif self.direction == 'up':
            # Reveal from bottom to top
            reveal_height = int(height * progress)
            return {
                'x_start': 0,
                'x_end': width,
                'y_start': height - reveal_height,
                'y_end': height
            }
        else:
            # Default: reveal entire area
            return {
                'x_start': 0,
                'x_end': width,
                'y_start': 0,
                'y_end': height
            }
    
    async def _render_with_clipping(self, display: Any, render_func: Callable[..., Any], reveal_area: Dict[str, Any]) -> None:
        """Render content with clipping to the reveal area.
        
        Args:
            display: Display interface
            render_func: Function that renders the content
            reveal_area: Area bounds for clipping
        """
        # Store original display state if needed
        original_clip = getattr(display, '_clip_area', None)
        
        # Set clipping area on display if supported
        if hasattr(display, 'set_clip_area'):
            await display.set_clip_area(
                reveal_area['x_start'],
                reveal_area['y_start'],
                reveal_area['x_end'],
                reveal_area['y_end']
            )
        
        try:
            # Render the content (it will be clipped)
            await render_func()
        finally:
            # Restore original clipping state
            if hasattr(display, 'set_clip_area'):
                if original_clip:
                    await display.set_clip_area(**original_clip)
                else:
                    await display.clear_clip_area()


@register_effect('reveal_center')
class RevealCenterEffect(Effect):
    """Reveal effect that unveils content from the center outward."""
    
    def __init__(self, 
                 duration: float = 2.0,
                 mode: str = 'expand',  # 'expand' or 'iris'
                 pause_at_end: float = 1.0,
                 **kwargs):
        """Initialize center reveal effect.
        
        Args:
            duration: Time for the reveal animation in seconds
            mode: Reveal mode ('expand' for rectangular, 'iris' for circular)
            pause_at_end: Time to pause after reveal is complete
            **kwargs: Additional effect parameters
        """
        total_duration = duration + pause_at_end
        super().__init__(duration=total_duration, **kwargs)
        
        self.reveal_duration = duration
        self.mode = mode
        self.pause_at_end = pause_at_end
    
    async def apply(self, display: Any, render_func: Callable[..., Any]) -> None:
        """Apply the center reveal effect."""
        start_time = time.time()
        
        # Get display dimensions
        width = getattr(display, 'width', 64)
        height = getattr(display, 'height', 32)
        
        # Calculate center
        center_x = width // 2
        center_y = height // 2
        
        # Calculate maximum radius
        max_radius = max(center_x, center_y, width - center_x, height - center_y)
        
        # Perform reveal animation
        steps = max_radius
        step_duration = self.reveal_duration / steps if steps > 0 else 0
        
        for step in range(steps + 1):
            # Calculate reveal area
            radius = step
            reveal_area = self._calculate_center_reveal_area(
                width, height, center_x, center_y, radius
            )
            
            # Clear display
            await display.clear()
            
            # Render with clipping
            await self._render_with_center_clipping(display, render_func, reveal_area)
            
            # Update display
            await display.show()
            
            # Wait for next step
            if step < steps and step_duration > 0:
                if asyncio:
                    await asyncio.sleep(step_duration)
                else:
                    time.sleep(step_duration)
        
        # Pause at end
        if self.pause_at_end > 0:
            if asyncio:
                await asyncio.sleep(self.pause_at_end)
            else:
                time.sleep(self.pause_at_end)
    
    def _calculate_center_reveal_area(self, width: int, height: int, 
                                    center_x: int, center_y: int, radius: int) -> Dict[str, Any]:
        """Calculate the center reveal area."""
        if self.mode == 'iris':
            # Circular reveal
            return {
                'type': 'circle',
                'center_x': center_x,
                'center_y': center_y,
                'radius': radius
            }
        else:
            # Rectangular expand
            half_radius = radius
            return {
                'type': 'rect',
                'x_start': max(0, center_x - half_radius),
                'x_end': min(width, center_x + half_radius),
                'y_start': max(0, center_y - half_radius),
                'y_end': min(height, center_y + half_radius)
            }
    
    async def _render_with_center_clipping(self, display: Any, render_func: Callable[..., Any], reveal_area: Dict[str, Any]) -> None:
        """Render content with center clipping."""
        # For simplicity, we'll use rectangular clipping even for circular mode
        # Advanced displays could implement true circular clipping
        
        if reveal_area['type'] == 'circle':
            # Convert circle to bounding rectangle for basic clipping
            radius = reveal_area['radius']
            center_x = reveal_area['center_x']
            center_y = reveal_area['center_y']
            
            x_start = max(0, center_x - radius)
            x_end = min(getattr(display, 'width', 64), center_x + radius)
            y_start = max(0, center_y - radius)
            y_end = min(getattr(display, 'height', 32), center_y + radius)
            
            clip_area = {
                'x_start': x_start,
                'x_end': x_end,
                'y_start': y_start,
                'y_end': y_end
            }
        else:
            # Rectangle
            clip_area = reveal_area
        
        # Apply clipping if supported
        if hasattr(display, 'set_clip_area'):
            await display.set_clip_area(
                clip_area['x_start'],
                clip_area['y_start'], 
                clip_area['x_end'],
                clip_area['y_end']
            )
        
        try:
            await render_func()
        finally:
            if hasattr(display, 'clear_clip_area'):
                await display.clear_clip_area()