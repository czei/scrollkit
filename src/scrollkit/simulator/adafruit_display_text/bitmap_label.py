"""Bitmap label implementation for more efficient text rendering."""

from .label import Label


class BitmapLabel(Label):
    """An enhanced label that renders more efficiently using bitmaps.
    
    This is effectively the same as Label in our implementation since
    we already use bitmaps for rendering. Provided for API compatibility
    with CircuitPython's adafruit_display_text.bitmap_label.BitmapLabel.
    """
    
    def __init__(self, font, *, text="", color=0xFFFFFF, background_color=None,
                 line_spacing=1.25, background_tight=False, padding_top=0,
                 padding_bottom=0, padding_left=0, padding_right=0,
                 anchor_point=None, anchored_position=None, scale=1,
                 base_alignment=False, tab_replacement=(4, " "), label_direction="LTR",
                 save_text=True, **kwargs):
        """Initialize BitmapLabel.
        
        Args:
            font: Font to use for text
            text: Initial text to display
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
            save_text: Whether to save the text string (for memory optimization)
            **kwargs: Additional keyword arguments
        """
        self.save_text = save_text
        
        super().__init__(
            font, text=text, color=color, background_color=background_color,
            line_spacing=line_spacing, background_tight=background_tight,
            padding_top=padding_top, padding_bottom=padding_bottom,
            padding_left=padding_left, padding_right=padding_right,
            anchor_point=anchor_point, anchored_position=anchored_position,
            scale=scale, base_alignment=base_alignment,
            tab_replacement=tab_replacement, label_direction=label_direction,
            **kwargs
        )
        
    @property
    def text(self):
        """Get the current text."""
        if self.save_text:
            return self._text
        else:
            return None
            
    @text.setter
    def text(self, new_text):
        """Set the text to display.
        
        Args:
            new_text: New text string
        """
        # Always process the text for rendering
        old_save = self.save_text
        self.save_text = True
        super(BitmapLabel, self.__class__).text.fset(self, new_text)
        
        # Clear saved text if not saving
        if not old_save:
            self.save_text = False
            self._text = None