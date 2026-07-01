# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Display content classes for SLDK.

Provides base classes and implementations for displayable content.
"""

from __future__ import annotations

try:
    from typing import Any, List, Optional
except ImportError:  # CircuitPython has no 'typing' module
    pass

from .text_fill import DEFAULT_PALETTE_STEPS, normalize_direction

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


__all__ = ['Priority', 'DisplayContent', 'StaticText', 'ScrollingText', 'ContentQueue', 'LOOP_FPS']

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


class Priority:
    """Priority levels for display content, highest wins ties in ContentQueue."""
    IDLE: int = 0
    LOW: int = 1
    NORMAL: int = 2
    HIGH: int = 3
    URGENT: int = 4
    SYSTEM: int = 5


class DisplayContent:
    """Base class for displayable content."""

    def __init__(self, duration: Optional[float] = None, priority: int = Priority.NORMAL):
        """Initialize display content.

        Args:
            duration: How long to display in seconds (None = forever)
            priority: Queue priority (default Priority.NORMAL). Higher
                values are shown first by ContentQueue.
        """
        self.duration: Optional[float] = duration
        self.priority: int = priority
        # Stamp the clock at creation so duration-based completion works even
        # when the content is used outside the async start()/render() loop
        # (e.g. added straight to a ContentQueue). async start() re-stamps it.
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


class _GradientFillMixin:
    """Shared gradient text-fill state for the Label-based text content classes.

    When ``self.palette`` is set, the text is rendered through an indexed-bitmap
    ``GradientTextLayer`` (built once, scrolled by moving its TileGrid) instead of
    the flat single-colour displayio ``Label``. Mono content (``palette is None``)
    never touches any of this — and the renderer module is imported lazily on the
    gradient path only, so the boot/mono path pays no extra RAM.
    """

    def _init_gradient(self, palette, direction, palette_steps) -> None:
        # None → flat single-colour Label path (unchanged). A sequence of >=2
        # colours → gradient; a 1-element sequence → flat fill of that colour.
        self.palette = tuple(palette) if palette else None
        self.direction = normalize_direction(direction)
        self.palette_steps = palette_steps
        self._grad = None            # lazily-built GradientTextLayer
        self._grad_display = None
        self._grad_key = None

    def _grad_active(self, display) -> bool:
        # Fall back to the flat path when there's no font (headless without one),
        # rather than crashing in the rasteriser.
        return self.palette is not None and getattr(display, "font", None) is not None

    def _ensure_grad(self, display) -> None:
        """Build (or rebuild on change) the gradient layer; idempotent per frame."""
        from .gradient_text import GradientTextLayer  # lazy: gradient path only
        key = (self.text, self.palette, self.direction, self.palette_steps,
               self.y, id(getattr(display, "font", None)))
        if (self._grad is not None and self._grad_key == key
                and self._grad_display is display):
            return
        self._detach_grad()
        self._grad = GradientTextLayer(self.text, self.y, self.palette,
                                        self.direction, self.palette_steps)
        self._grad.build(display)
        self._grad_display = display
        self._grad_key = key

    def _detach_grad(self) -> None:
        """Remove the gradient layer and clear state (safe to call repeatedly)."""
        if self._grad is not None and self._grad_display is not None:
            try:
                self._grad.detach(self._grad_display)
            except Exception:
                pass
        self._grad = None
        self._grad_display = None
        self._grad_key = None


class StaticText(_GradientFillMixin, DisplayContent):
    """Static text display content."""

    def __init__(self, text: str, x: int = 0, y: int = 0, color=None,
                 duration: Optional[float] = None, priority: int = Priority.NORMAL,
                 palette=None, direction: str = "vertical",
                 palette_steps: int = DEFAULT_PALETTE_STEPS):
        """Initialize static text.

        Args:
            text: Text to display
            x: X coordinate
            y: Y coordinate
            color: Text color as 24-bit RGB int (None = use library default_color setting)
            duration: Display duration in seconds
            priority: Queue priority (default Priority.NORMAL)
            palette: ``None`` for a flat ``color`` (the default). A sequence of two
                24-bit ``0xRRGGBB`` colours gives a gradient from the first to the
                second; three or more gives a multi-stop gradient. Tip:
                ``depth_palette(color)`` (``scrollkit.display.colors``) derives a
                subtle close ramp from one base colour. When set, ``color`` is
                ignored.
            direction: Gradient axis — ``"vertical"`` (default, top→bottom; reads
                as depth), ``"horizontal"`` (left→right) or ``"diagonal"``. Reverse
                by reversing the ``palette``.
            palette_steps: Number of ramp colours generated from the stops (clamped
                to 2..15; the panel is RGB444, so a few steps is plenty).
        """
        super().__init__(duration, priority)
        self.text: str = text
        self.x: int = x
        self.y: int = y
        # None → "default_color"; str → named setting key; int → explicit value
        self._color_setting = "default_color" if color is None else (color if isinstance(color, str) else None)
        self.color: int = _resolve_color(color)
        self._init_gradient(palette, direction, palette_steps)

    async def start(self) -> None:
        """Detach any prior gradient layer so a re-shown item rebuilds cleanly."""
        await super().start()
        self._detach_grad()

    async def render(self, display) -> None:
        """Render static text — flat ``Label`` path, or a gradient layer."""
        if not self._grad_active(display):
            await display.draw_text(self.text, self.x, self.y, self.color)
            return
        self._ensure_grad(display)
        self._grad.x = self.x

    async def stop(self) -> None:
        await super().stop()
        self._detach_grad()

    def describe(self) -> dict:
        info = super().describe()
        info.update({"text": self.text, "x": self.x, "y": self.y,
                     "gradient": self.palette is not None})
        return info


class ScrollingText(_GradientFillMixin, DisplayContent):
    """Scrolling text display content.

    When speed resolves to 0 (the library's "None" scroll speed setting),
    the text is shown centred on-screen for ``static_duration`` seconds and
    then completes — so the transition effect fires on every repetition without
    any scrolling motion.
    """

    # How long static (speed=0) display lingers before completing.
    DEFAULT_STATIC_DURATION = 5.0

    def __init__(self, text: str, x: Optional[int] = None, y: int = 0,
                 color=None, speed=None, priority: int = Priority.NORMAL,
                 static_duration: float = DEFAULT_STATIC_DURATION,
                 palette=None, direction: str = "vertical",
                 palette_steps: int = DEFAULT_PALETTE_STEPS):
        """Initialize scrolling text.

        Args:
            text: Text to display / scroll.
            x: Starting X (None = right edge for scrolling, centred for static).
            y: Y coordinate (baseline).
            color: 24-bit RGB int (None = library default_color setting).
            speed: px/sec (None = library scroll_speed setting; 0 = static mode).
            priority: Queue priority (default Priority.NORMAL).
            static_duration: Seconds to show text before completing in static mode.
            palette: ``None`` for a flat ``color`` (the default). A sequence of two
                24-bit ``0xRRGGBB`` colours gives a gradient from the first to the
                second; three or more gives a multi-stop gradient. Tip:
                ``depth_palette(color)`` (``scrollkit.display.colors``) derives a
                subtle close ramp from one base colour. When set, ``color`` is
                ignored. The gradient is locked to the letters, so it scrolls with
                the text.
            direction: Gradient axis — ``"vertical"`` (default), ``"horizontal"``
                or ``"diagonal"``. Reverse by reversing the ``palette``.
            palette_steps: Number of ramp colours generated from the stops (clamped
                to 2..15).
        """
        super().__init__(duration=None, priority=priority)
        self.text: str = text
        self.x: Optional[int] = x
        self.y: int = y
        self._color_setting = ("default_color" if color is None
                               else (color if isinstance(color, str) else None))
        self.color: int = _resolve_color(color)
        self._init_gradient(palette, direction, palette_steps)
        self._speed_is_default = (speed is None)
        self._static_duration: float = static_duration
        # Internal speed storage; use the property setter so _static_mode and
        # position state are always consistent.
        self._speed: int = 0
        self._static_mode: bool = False
        self._pos_q: Optional[int] = None
        self._measured_width: Optional[int] = None
        self.speed = _resolve_speed(speed)   # property setter

    # --- speed property -------------------------------------------------------

    @property
    def speed(self) -> int:
        return self._speed

    @speed.setter
    def speed(self, value: int) -> None:
        old_static = self._static_mode
        self._speed = value
        self._static_mode = (value == 0)
        if self._static_mode != old_static:
            # Switching modes: reset position so render() re-initialises for
            # the new mode, and clear any prior completion flag.
            self._pos_q = None
            self._measured_width = None
            self._is_complete = False

    # --- lifecycle ------------------------------------------------------------

    async def start(self) -> None:
        """Reset position so render() re-initialises on the first frame."""
        await super().start()
        self._pos_q = None
        self._measured_width = None
        # Detach any prior gradient layer so a re-shown item rebuilds + re-adds it.
        self._detach_grad()

    async def stop(self) -> None:
        await super().stop()
        self._detach_grad()

    # --- rendering ------------------------------------------------------------

    def _delta_q(self) -> int:
        """Per-frame motion in 1/16-px units, derived from speed (px/sec)."""
        return int(round(self._speed * 16 / LOOP_FPS))

    async def render(self, display) -> None:
        """Render text: scrolling when speed > 0, centred-static when speed == 0.

        With a ``palette`` the glyphs are drawn through a gradient TileGrid that is
        positioned each frame (``self._grad.x``); otherwise the flat-colour Label
        path is used. The scroll bookkeeping (``_pos_q`` / completion) is identical.
        """
        use_grad = self._grad_active(display)
        if use_grad:
            self._ensure_grad(display)

        if self._static_mode:
            # First render in static mode: measure width and choose x position.
            if self._pos_q is None:
                self._measured_width = (self._grad.width if use_grad
                                        else display.measure_text(self.text))
                if self.x is not None:
                    x = self.x
                else:
                    x = max(0, (display.width - self._measured_width) // 2)
                self._pos_q = x << 4
            if use_grad:
                self._grad.x = self._pos_q >> 4
            else:
                await display.draw_text(self.text, self._pos_q >> 4, self.y, self.color)
            return

        # Scrolling mode: initialise position on first render (needs display.width).
        if self._pos_q is None:
            start_x = display.width if self.x is None else self.x
            self._pos_q = int(start_x) << 4
            self._measured_width = (self._grad.width if use_grad
                                    else display.measure_text(self.text))

        if use_grad:
            self._grad.x = self._pos_q >> 4
        else:
            await display.draw_text(self.text, self._pos_q >> 4, self.y, self.color)
        self._pos_q -= self._delta_q()

        if (self._pos_q >> 4) < -self._measured_width:
            self._is_complete = True

    # --- completion -----------------------------------------------------------

    @property
    def is_complete(self) -> bool:
        if self._is_complete:
            return True
        if self._static_mode:
            return self.elapsed >= self._static_duration
        return False

    # --- introspection --------------------------------------------------------

    def describe(self) -> dict:
        info = super().describe()
        info.update({
            "text": self.text,
            "y": self.y,
            "speed": self._speed,
            "static_mode": self._static_mode,
            "position": None if self._pos_q is None else (self._pos_q >> 4),
            "text_width": self._measured_width,
            "started": self._pos_q is not None,
            "gradient": self.palette is not None,
        })
        return info


# Advertised feasibility (read by run_headless(strict=True) and the capabilities
# catalog). Both the flat-colour Label path and the gradient path do ZERO per-frame
# pixel writes and no per-frame allocation: a flat Label is reused and only
# repositioned; a gradient rasterises ONCE and then scrolls by moving its
# TileGrid.x. Metadata lives on the CLASS (CircuitPython can't attach it to a
# function).
_TEXT_FILL_FEASIBILITY = {
    "hardware_safe": True,
    "allocates_per_frame": False,
    "max_pixel_writes_per_frame": 0,
    "modeled_frame_ms": 5.0,
    "note": ("Flat colour reuses a pooled Label; a gradient palette rasterises the "
             "text once and scrolls by moving its TileGrid — zero per-frame pixel "
             "writes either way."),
}
StaticText.FEASIBILITY = dict(_TEXT_FILL_FEASIBILITY)
ScrollingText.FEASIBILITY = dict(_TEXT_FILL_FEASIBILITY)


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
        # Content abandoned by clear() that still needs its async stop() run by the
        # display loop (see clear()). A LIST, not a single slot: a settings change
        # rebuilds the queue twice in quick succession (the synchronous web handler's
        # immediate rebuild, then the scheduled data refresh's teardown), and a
        # single slot would let the second rebuild clobber the first's pending stop —
        # orphaning the on-screen content's overlay layer (e.g. a Swarm reveal's
        # bird/number layers) on screen forever.
        self._pending_stops: List[Any] = []
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
        # Hand the in-flight content to the display loop to stop() on its next
        # frame. stop() is a content's only chance to release external resources it
        # holds — e.g. a persistent overlay layer added to the display's layer group,
        # which the per-frame clear() never touches and so stays on screen until the
        # content detaches it in stop(). A rebuild that drops the current content
        # without stopping it would orphan such a resource forever. Deferring keeps
        # the async stop() out of this synchronous method, so every rebuild path (a
        # timed refresh and a synchronous settings handler alike) is covered with no
        # race. Pending stops ACCUMULATE in a list: several rebuilds before the loop
        # next runs (e.g. a settings handler's immediate rebuild + the scheduled
        # refresh's teardown) each keep their overlay's stop(), so none is clobbered.
        if self._current_content is not None and self._current_content not in self._pending_stops:
            self._pending_stops.append(self._current_content)
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
        # Stop content abandoned by a clear()/rebuild before showing anything new,
        # so it releases its overlay layer (see clear()). Drain the whole list (a
        # rapid double-rebuild can leave more than one), popping each first so a
        # concurrent clear() during stop() isn't lost; guarded so a misbehaving
        # stop() can't wedge the loop. Runs even when the queue is now empty (a
        # rebuild to no items must still detach the old overlay).
        while self._pending_stops:
            pending = self._pending_stops.pop(0)
            try:
                await pending.stop()
            except Exception:
                pass

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