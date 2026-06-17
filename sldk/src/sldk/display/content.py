"""Display content classes for SLDK.

Provides base classes and implementations for displayable content.
"""

from __future__ import annotations

from typing import Any, List, Optional

from ..exceptions import ContentError

try:
    # Desktop Python
    import asyncio
    get_time = lambda: asyncio.get_event_loop().time()
except (ImportError, AttributeError):
    # CircuitPython
    import time
    get_time = lambda: time.monotonic()


class DisplayContent:
    """Base class for displayable content."""
    
    def __init__(self, duration: Optional[float] = None):
        """Initialize display content.
        
        Args:
            duration: How long to display in seconds (None = forever)
        """
        self.duration: Optional[float] = duration
        self._start_time: Optional[float] = None
        self._is_complete: bool = False
    
    async def start(self) -> None:
        """Called when content starts displaying."""
        self._start_time = get_time()
        self._is_complete = False
    
    async def stop(self) -> None:
        """Called when content stops displaying."""
        self._is_complete = True
    
    async def render(self, display) -> None:
        """Render content to display.
        
        Args:
            display: DisplayInterface instance
        """
        raise NotImplementedError("Subclass must implement render()")
    
    @property
    def elapsed(self) -> float:
        """Time elapsed since content started displaying."""
        if self._start_time is None:
            return 0.0
        return get_time() - self._start_time
    
    @property
    def is_complete(self) -> bool:
        """Check if content display is complete."""
        if self._is_complete:
            return True
        if self.duration is None:
            return False
        return self.elapsed >= self.duration


class StaticText(DisplayContent):
    """Static text display content."""
    
    def __init__(self, text: str, x: int = 0, y: int = 0, color: int = 0xFFFFFF, duration: Optional[float] = None):
        """Initialize static text.
        
        Args:
            text: Text to display
            x: X coordinate
            y: Y coordinate
            color: Text color as 24-bit RGB
            duration: Display duration in seconds
        """
        super().__init__(duration)
        self.text: str = text
        self.x: int = x
        self.y: int = y
        self.color: int = color
    
    async def render(self, display) -> None:
        """Render static text to display."""
        await display.draw_text(self.text, self.x, self.y, self.color)


class ScrollingText(DisplayContent):
    """Scrolling text display content."""
    
    def __init__(self, text: str, x: Optional[int] = None, y: int = 0, color: int = 0xFFFFFF, speed: int = 30):
        """Initialize scrolling text.
        
        Args:
            text: Text to scroll
            x: Starting X coordinate (None = start from right edge)
            y: Y coordinate
            color: Text color as 24-bit RGB
            speed: Scroll speed in pixels per second
        """
        super().__init__(duration=None)  # Scrolls until complete
        self.text: str = text
        self.x: Optional[int] = x
        self.y: int = y
        self.color: int = color
        self.speed: int = speed
        self._position: Optional[int] = None
        self._text_width: Optional[int] = None
    
    async def start(self) -> None:
        """Start scrolling from right edge."""
        await super().start()
        # Position will be set on first render when we have display
        self._position = None
    
    async def render(self, display) -> None:
        """Render scrolling text to display."""
        # Initialize position on first render
        if self._position is None:
            if self.x is None:
                self._position = display.width
            else:
                self._position = self.x
            # Estimate text width (6 pixels per char as default)
            self._text_width = len(self.text) * 6
        
        # Draw text at current position
        await display.draw_text(self.text, self._position, self.y, self.color)
        
        # Move text left
        self._position -= 1
        
        # Check if scrolling is complete
        if self._position < -self._text_width:
            self._is_complete = True
            
    @property
    def is_complete(self) -> bool:
        """Check if text has scrolled off screen."""
        return self._is_complete


class ContentQueue:
    """Queue for managing display content."""
    
    def __init__(self, loop: bool = True):
        """Initialize content queue.
        
        Args:
            loop: Whether to loop back to start when queue ends
        """
        self.loop: bool = loop
        self._items: List[Any] = []
        self._current_index: int = 0
        self._current_content: Optional[Any] = None
    
    def add(self, content) -> None:
        """Add content to queue.
        
        Args:
            content: DisplayContent instance
        """
        self._items.append(content)
    
    def add_content(self, content) -> None:
        """Add content to queue (alias for add).
        
        Args:
            content: DisplayContent instance
        """
        self.add(content)
    
    def clear(self) -> None:
        """Clear all content from queue."""
        self._items.clear()
        self._current_index = 0
        self._current_content = None
    
    def get_content_count(self) -> int:
        """Get number of items in queue."""
        return len(self._items)
    
    def get_current_content(self) -> Optional[Any]:
        """Get current content item (synchronous version)."""
        if not self._items:
            return None
        if self._current_content is None:
            self._current_content = self._items[0]
        return self._current_content
    
    async def get_current(self) -> Optional[Any]:
        """Get current content to display."""
        if not self._items:
            return None
        
        # Check if we need to advance
        if self._current_content is None:
            # First time - start with first item
            self._current_content = self._items[self._current_index]
            await self._current_content.start()
        elif self._current_content.is_complete:
            # Stop current content
            await self._current_content.stop()
            
            # Advance to next
            self._current_index = (self._current_index + 1) % len(self._items)
            
            # Start new content
            self._current_content = self._items[self._current_index]
            await self._current_content.start()
        
        return self._current_content
    
    def __iter__(self):
        """Allow iteration over queue items."""
        return iter(self._items)
    
    @property
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._items) == 0