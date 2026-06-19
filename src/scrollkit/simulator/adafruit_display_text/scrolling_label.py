"""Scrolling text label implementation."""

import time
from .label import Label


class ScrollingLabel(Label):
    """A label that can scroll text horizontally.
    
    Compatible with CircuitPython's adafruit_display_text.scrolling_label.ScrollingLabel API.
    """
    
    def __init__(self, font, *, text="", max_characters=None, color=0xFFFFFF,
                 background_color=None, line_spacing=1.25, background_tight=False,
                 padding_top=0, padding_bottom=0, padding_left=0, padding_right=0,
                 anchor_point=None, anchored_position=None, scale=1,
                 base_alignment=False, tab_replacement=(4, " "), label_direction="LTR",
                 animate_time=0.3, current_index=0, **kwargs):
        """Initialize ScrollingLabel.
        
        Args:
            font: Font to use for text
            text: Full text to scroll
            max_characters: Maximum number of characters to show at once
            color: Text color (RGB565 or RGB888)
            background_color: Background color (None for transparent)
            line_spacing: Line spacing multiplier
            background_tight: Whether background fits text tightly
            padding_top: Top padding in pixels
            padding_bottom: Bottom padding in pixels
            padding_left: Left padding in pixels
            padding_right: Right padding in pixels
            anchor_point: Anchor point as (x, y) normalized values
            anchored_position: Position for anchor point
            scale: Scale factor for text
            base_alignment: Whether to align text baselines
            tab_replacement: Tuple of (spaces, character) for tab replacement
            label_direction: Text direction ("LTR" or "RTL")
            animate_time: Time in seconds between scroll steps
            current_index: Starting index in the text
            **kwargs: Additional keyword arguments
        """
        self._full_text = str(text)
        self.max_characters = max_characters or 10
        self.animate_time = animate_time
        self.current_index = current_index
        self._last_animate_time = 0
        self._is_scrolling = False
        
        # Initialize with visible portion of text
        visible_text = self._get_visible_text()
        
        super().__init__(
            font, text=visible_text, color=color, background_color=background_color,
            line_spacing=line_spacing, background_tight=background_tight,
            padding_top=padding_top, padding_bottom=padding_bottom,
            padding_left=padding_left, padding_right=padding_right,
            anchor_point=anchor_point, anchored_position=anchored_position,
            scale=scale, base_alignment=base_alignment,
            tab_replacement=tab_replacement, label_direction=label_direction,
            **kwargs
        )
        
    @property
    def full_text(self):
        """Get the full text string."""
        return self._full_text
        
    @full_text.setter
    def full_text(self, new_text):
        """Set the full text to scroll.
        
        Args:
            new_text: New text string
        """
        self._full_text = str(new_text)
        self.current_index = 0
        self._update_visible_text()
        
    def _get_visible_text(self):
        """Get the currently visible portion of text."""
        if not self._full_text:
            return ""
            
        # Handle wrapping
        text_len = len(self._full_text)
        if text_len <= self.max_characters:
            return self._full_text
            
        # Get visible portion with wrapping
        visible = ""
        for i in range(self.max_characters):
            char_index = (self.current_index + i) % text_len
            visible += self._full_text[char_index]
            
        return visible
        
    def _update_visible_text(self):
        """Update the displayed text to show current visible portion."""
        visible_text = self._get_visible_text()
        super(ScrollingLabel, self.__class__).text.fset(self, visible_text)
        
    def update(self, force=False):
        """Update the scroll position if enough time has passed.
        
        Args:
            force: Force update regardless of time
            
        Returns:
            True if text was scrolled, False otherwise
        """
        current_time = time.monotonic()
        
        if force or (self._is_scrolling and 
                     current_time - self._last_animate_time >= self.animate_time):
            self.scroll()
            self._last_animate_time = current_time
            return True
            
        return False
        
    def scroll(self):
        """Scroll the text by one character."""
        if len(self._full_text) > self.max_characters:
            self.current_index = (self.current_index + 1) % len(self._full_text)
            self._update_visible_text()
            
    def scroll_left(self):
        """Scroll the text left by one character."""
        self.scroll()
        
    def scroll_right(self):
        """Scroll the text right by one character."""
        if len(self._full_text) > self.max_characters:
            self.current_index = (self.current_index - 1) % len(self._full_text)
            self._update_visible_text()
            
    def start_scrolling(self):
        """Start automatic scrolling."""
        self._is_scrolling = True
        self._last_animate_time = time.monotonic()
        
    def stop_scrolling(self):
        """Stop automatic scrolling."""
        self._is_scrolling = False
        
    def reset_scrolling(self):
        """Reset scroll position to beginning."""
        self.current_index = 0
        self._update_visible_text()
        
    @property
    def is_scrolling(self):
        """Check if currently scrolling."""
        return self._is_scrolling