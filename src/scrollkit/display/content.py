"""Display content classes for SLDK.

Provides base classes and implementations for displayable content.
"""

from __future__ import annotations

try:
    from typing import Any, List, Optional
except ImportError:  # CircuitPython has no 'typing' module
    pass

from ..exceptions import ContentError

import time
# Monotonic clock works in both sync and async contexts, on desktop and
# CircuitPython. Avoids asyncio.get_event_loop(), which raises outside a running
# loop on modern Python (and isn't available the same way on CircuitPython).
get_time = lambda: time.monotonic()

# The display loop runs at ~20 FPS (app loop sleeps 0.05 s; the feasibility budget
# is built on the same target). Scroll speed (px/sec) is converted to per-frame
# motion against this. Kept here so the scroll math and the budget stay in sync.
LOOP_FPS = 20

# Set by SLDKApp.__init__ so content objects can read library defaults without
# being tightly coupled to the app.  None when running outside an app context
# (tests, standalone scripts) — helpers fall back to hardcoded values.
_settings = None


def _resolve_color(color):
    """Resolve a color argument to an int.

    ``None``  → library default_color setting (or 0xFFFFFF if no app running)
    ``str``   → a named settings key; reads the current value from _settings
    ``int``   → used as-is
    """
    if color is None:
        color = "default_color"
    if isinstance(color, str):
        if _settings is not None:
            try:
                return _settings.get(color, 0xFFFFFF)
            except Exception:
                pass
        return 0xFFFFFF
    return color


def _resolve_speed(speed):
    """Resolve a speed argument to pixels/second.

    ``None`` → library scroll_speed setting (or 25 if no app running)
    ``int``/``float`` → used as-is
    """
    if speed is None:
        if _settings is not None:
            try:
                return _settings.get_scroll_speed_px()
            except Exception:
                pass
        return 25
    return speed


class DisplayContent:
    """Base class for displayable content."""

    def __init__(self, duration: Optional[float] = None, priority: int = 2):
        """Initialize display content.

        Args:
            duration: How long to display in seconds (None = forever)
            priority: Queue priority (default 2 == Priority.NORMAL). Higher
                values are shown first by DisplayQueue.
        """
        self.duration: Optional[float] = duration
        self.priority: int = priority
        # Stamp the clock at creation so duration-based completion works even
        # when the content is used outside the async start()/render() loop
        # (e.g. added straight to a DisplayQueue). async start() re-stamps it.
        self._start_time: Optional[float] = get_time()
        self._is_complete: bool = False

    def update(self) -> None:
        """Synchronous tick hook.

        Completion is derived from elapsed time (see ``is_complete``), so this
        is a no-op placeholder that application loops may call each frame.
        """
        return None

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

    def describe(self) -> dict:
        """A small, JSON-able summary of this content for verification.

        Subclasses extend this with their own fields (text, position, ...).
        Lets the dev harness read a supported summary rather than poking
        private attributes like ``_position``.
        """
        return {
            "type": type(self).__name__,
            "priority": self.priority,
            "duration": self.duration,
            "elapsed": round(self.elapsed, 2),
            "is_complete": self.is_complete,
        }


class StaticText(DisplayContent):
    """Static text display content."""
    
    def __init__(self, text: str, x: int = 0, y: int = 0, color=None, duration: Optional[float] = None, priority: int = 2):
        """Initialize static text.

        Args:
            text: Text to display
            x: X coordinate
            y: Y coordinate
            color: Text color as 24-bit RGB int (None = use library default_color setting)
            duration: Display duration in seconds
            priority: Queue priority (default Priority.NORMAL)
        """
        super().__init__(duration, priority)
        self.text: str = text
        self.x: int = x
        self.y: int = y
        # None → "default_color"; str → named setting key; int → explicit value
        self._color_setting = "default_color" if color is None else (color if isinstance(color, str) else None)
        self.color: int = _resolve_color(color)

    async def render(self, display) -> None:
        """Render static text to display."""
        await display.draw_text(self.text, self.x, self.y, self.color)

    def describe(self) -> dict:
        info = super().describe()
        info.update({"text": self.text, "x": self.x, "y": self.y})
        return info


class ScrollingText(DisplayContent):
    """Scrolling text display content."""
    
    def __init__(self, text: str, x: Optional[int] = None, y: int = 0, color=None, speed=None, priority: int = 2):
        """Initialize scrolling text.

        Args:
            text: Text to scroll
            x: Starting X coordinate (None = start from right edge)
            y: Y coordinate
            color: Text color as 24-bit RGB int (None = use library default_color setting)
            speed: Scroll speed in pixels per second (None = use library scroll_speed setting)
            priority: Queue priority (default Priority.NORMAL)
        """
        super().__init__(duration=None, priority=priority)  # Scrolls until complete
        self.text: str = text
        self.x: Optional[int] = x
        self.y: int = y
        self._color_setting = "default_color" if color is None else (color if isinstance(color, str) else None)
        self.color: int = _resolve_color(color)
        self._speed_is_default = (speed is None)
        self.speed: int = _resolve_speed(speed)
        # Position is a fixed-point accumulator in 1/16-px units, so a sub-pixel
        # per-frame speed still produces smooth integer motion. Render x = pos>>4.
        self._pos_q: Optional[int] = None
        self._measured_width: Optional[int] = None

    async def start(self) -> None:
        """Start scrolling from the right edge."""
        await super().start()
        # Position + measured width are established on the first render (we need a
        # display to measure against). Reset so a restarted item re-initializes.
        self._pos_q = None
        self._measured_width = None

    def _delta_q(self) -> int:
        """Per-frame motion in 1/16-px units, derived from speed (px/sec)."""
        return int(round(self.speed * 16 / LOOP_FPS))

    async def render(self, display) -> None:
        """Render scrolling text to display (fixed-point sub-pixel motion)."""
        # First render: set the start position and measure the real text width
        # ONCE (never per frame — measuring is off the hot path).
        if self._pos_q is None:
            start_x = display.width if self.x is None else self.x
            self._pos_q = int(start_x) << 4
            self._measured_width = display.measure_text(self.text)

        # Draw the (reused) Label at the current integer position.
        await display.draw_text(self.text, self._pos_q >> 4, self.y, self.color)

        # Advance left by the speed-derived sub-pixel delta.
        self._pos_q -= self._delta_q()

        # Complete once the whole measured width has scrolled off the left edge.
        if (self._pos_q >> 4) < -self._measured_width:
            self._is_complete = True

    @property
    def is_complete(self) -> bool:
        """Check if text has scrolled off screen."""
        return self._is_complete

    def describe(self) -> dict:
        info = super().describe()
        info.update({
            "text": self.text,
            "y": self.y,
            "speed": self.speed,
            "position": None if self._pos_q is None else (self._pos_q >> 4),
            "text_width": self._measured_width,
            "started": self._pos_q is not None,
        })
        return info


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
        # Incremented every time a content item starts (first play counts as 1;
        # each subsequent cycle increments by 1). The display loop detects
        # changes to fire transitions between plays without relying on object
        # identity (which stays constant when a single-item queue loops).
        self._advance_count: int = 0
    
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
        # _advance_count is intentionally NOT reset: the display loop tracks it
        # to detect advances; a reset would look like the first play and suppress
        # the transition for the item that follows a rebuild.
    
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
            self._current_content = self._items[self._current_index]
            await self._current_content.start()
            self._advance_count += 1
        elif self._current_content.is_complete:
            await self._current_content.stop()
            self._current_index = (self._current_index + 1) % len(self._items)
            self._current_content = self._items[self._current_index]
            await self._current_content.start()
            self._advance_count += 1
        
        return self._current_content
    
    def __iter__(self):
        """Allow iteration over queue items."""
        return iter(self._items)
    
    @property
    def is_empty(self) -> bool:
        """Check if queue is empty."""
        return len(self._items) == 0