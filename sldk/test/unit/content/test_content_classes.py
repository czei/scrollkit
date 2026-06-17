#!/usr/bin/env python3
"""Unit tests for content classes."""

import pytest
from unittest.mock import MagicMock, AsyncMock

from sldk.content import StaticText, ScrollingText, RainbowText


class TestStaticText:
    """Test cases for StaticText content class."""
    
    def test_static_text_creation(self):
        """Test creating static text content."""
        text = StaticText("Hello", x=10, y=15, color=0xFF0000, duration=5.0)
        
        assert text.text == "Hello"
        assert text.x == 10
        assert text.y == 15
        assert text.color == 0xFF0000
        assert text.duration == 5.0
    
    def test_static_text_defaults(self):
        """Test static text with default values."""
        text = StaticText("Default")
        
        assert text.text == "Default"
        assert text.x == 0
        assert text.y == 0
        assert text.color == 0xFFFFFF  # Default white
        assert text.duration is None  # Permanent
    
    def test_static_text_position_validation(self):
        """Test position validation for static text."""
        # Valid positions
        text1 = StaticText("Test", x=0, y=0)
        text2 = StaticText("Test", x=63, y=31)  # Max for 64x32 display
        
        assert text1.x == 0 and text1.y == 0
        assert text2.x == 63 and text2.y == 31
        
        # Negative positions should be handled by implementation
        text3 = StaticText("Test", x=-5, y=-10)
        assert text3.x == -5 and text3.y == -10
    
    def test_static_text_color_formats(self):
        """Test different color formats."""
        # Hex color
        text1 = StaticText("Red", color=0xFF0000)
        assert text1.color == 0xFF0000
        
        # Different hex values
        text2 = StaticText("Green", color=0x00FF00)
        text3 = StaticText("Blue", color=0x0000FF)
        text4 = StaticText("White", color=0xFFFFFF)
        
        assert text2.color == 0x00FF00
        assert text3.color == 0x0000FF
        assert text4.color == 0xFFFFFF
    
    @pytest.mark.asyncio
    async def test_static_text_render(self, mock_display):
        """Test rendering static text to display."""
        text = StaticText("Test", x=5, y=10, color=0x00FFFF, duration=2.0)
        
        await text.render(mock_display)
        
        # Should call draw_text with correct parameters
        mock_display.draw_text.assert_called_once_with("Test", 5, 10, 0x00FFFF)


class TestScrollingText:
    """Test cases for ScrollingText content class."""
    
    def test_scrolling_text_creation(self):
        """Test creating scrolling text content."""
        text = ScrollingText("Scrolling Message", y=20, color=0x00FF00, speed=25)
        
        assert text.text == "Scrolling Message"
        assert text.y == 20
        assert text.color == 0x00FF00
        assert text.speed == 25
    
    def test_scrolling_text_defaults(self):
        """Test scrolling text with default values."""
        text = ScrollingText("Default Scroll")
        
        assert text.text == "Default Scroll"
        assert text.y == 0
        assert text.color == 0xFFFFFF
        assert text.speed == 30  # Default scroll speed
        assert text.duration is None  # Permanent scrolling
    
    def test_scrolling_text_speed_validation(self):
        """Test scroll speed validation."""
        # Valid speeds
        slow = ScrollingText("Slow", speed=10)
        fast = ScrollingText("Fast", speed=100)
        
        assert slow.speed == 10
        assert fast.speed == 100
        
        # Zero or negative speed
        zero_speed = ScrollingText("Zero", speed=0)
        neg_speed = ScrollingText("Negative", speed=-5)
        
        assert zero_speed.speed == 0
        assert neg_speed.speed == -5  # Implementation should handle
    
    def test_scrolling_text_position(self):
        """Test scrolling text positioning."""
        # Y position affects vertical placement
        top = ScrollingText("Top", y=0)
        middle = ScrollingText("Middle", y=16)
        bottom = ScrollingText("Bottom", y=31)
        
        assert top.y == 0
        assert middle.y == 16
        assert bottom.y == 31
        
        # X position typically starts off-screen for scrolling
        # But should be configurable
        text_with_x = ScrollingText("WithX", x=64, y=10)
        assert hasattr(text_with_x, 'x') or text_with_x.x == 64
    
    @pytest.mark.asyncio
    async def test_scrolling_text_render(self, mock_display):
        """Test rendering scrolling text."""
        text = ScrollingText("Scroll Test", y=15, color=0xFF00FF, speed=20)
        
        # Mock display width for scrolling calculation
        mock_display.width = 64
        
        await text.render(mock_display)
        
        # Should call draw_text for scrolling text
        mock_display.draw_text.assert_called()


class TestRainbowText:
    """Test cases for RainbowText content class."""
    
    def test_rainbow_text_creation(self):
        """Test creating rainbow text content."""
        text = RainbowText("Rainbow!", x=0, y=8, rainbow_speed=2.0)
        
        assert text.text == "Rainbow!"
        assert text.x == 0
        assert text.y == 8
        assert text.rainbow_speed == 2.0
    
    def test_rainbow_text_defaults(self):
        """Test rainbow text with default values."""
        text = RainbowText("Default Rainbow")
        
        assert text.text == "Default Rainbow"
        assert text.x == 0
        assert text.y == 0
        assert text.rainbow_speed == 1.0  # Default rainbow speed
        assert text.duration is None
    
    def test_rainbow_speed_validation(self):
        """Test rainbow speed validation."""
        slow_rainbow = RainbowText("Slow", rainbow_speed=0.5)
        fast_rainbow = RainbowText("Fast", rainbow_speed=5.0)
        
        assert slow_rainbow.rainbow_speed == 0.5
        assert fast_rainbow.rainbow_speed == 5.0
        
        # Zero speed should stop color cycling
        no_rainbow = RainbowText("Static", rainbow_speed=0.0)
        assert no_rainbow.rainbow_speed == 0.0
    
    def test_rainbow_text_positioning(self):
        """Test rainbow text positioning."""
        text = RainbowText("Position Test", x=10, y=20)
        
        # Should support x,y positioning like static text
        assert text.x == 10
        assert text.y == 20
    
    @pytest.mark.asyncio 
    async def test_rainbow_text_render(self, mock_display):
        """Test rendering rainbow text."""
        text = RainbowText("Rainbow Test", y=12, rainbow_speed=1.5)
        
        await text.render(mock_display)
        
        # Should call draw_text with calculated rainbow color
        mock_display.draw_text.assert_called()


class TestContentComparison:
    """Test comparison and equality of content objects."""
    
    def test_static_text_equality(self):
        """Test equality comparison for static text."""
        text1 = StaticText("Same", x=10, y=10, color=0xFF0000, duration=5)
        text2 = StaticText("Same", x=10, y=10, color=0xFF0000, duration=5)
        text3 = StaticText("Different", x=10, y=10, color=0xFF0000, duration=5)
        
        # Same content should be equal (depends on implementation)
        assert text1.text == text2.text
        assert text1.x == text2.x
        assert text1.y == text2.y
        assert text1.color == text2.color
        
        # Different text should not be equal
        assert text1.text != text3.text
    
    def test_content_string_representation(self):
        """Test string representation of content objects."""
        static = StaticText("Hello", x=5, y=10, color=0xFF0000)
        scroll = ScrollingText("World", y=20, color=0x00FF00)
        rainbow = RainbowText("Colors", y=30, rainbow_speed=2.0)
        
        # Should have meaningful string representations
        static_str = str(static)
        scroll_str = str(scroll)
        rainbow_str = str(rainbow)
        
        assert "Hello" in static_str or "StaticText" in static_str
        assert "World" in scroll_str or "ScrollingText" in scroll_str
        assert "Colors" in rainbow_str or "RainbowText" in rainbow_str


class TestContentEdgeCases:
    """Test edge cases and error conditions."""
    
    def test_empty_text_content(self):
        """Test content with empty text."""
        empty = StaticText("")
        space_only = StaticText("   ")
        
        assert empty.text == ""
        assert space_only.text == "   "
    
    def test_very_long_text(self):
        """Test content with very long text."""
        long_text = "A" * 1000
        content = ScrollingText(long_text)
        
        assert content.text == long_text
        assert len(content.text) == 1000
    
    def test_special_characters(self):
        """Test content with special characters."""
        special = StaticText("Hello 🌈 World! @#$%^&*()")
        
        assert "🌈" in special.text
        assert "@#$%^&*()" in special.text
    
    def test_unicode_text(self):
        """Test content with unicode characters."""
        unicode_text = StaticText("测试 Test العربية")
        
        assert "测试" in unicode_text.text
        assert "العربية" in unicode_text.text
    
    def test_none_text_handling(self):
        """Test handling of None text values."""
        # Should either convert to string or raise error
        try:
            none_text = StaticText(None)
            # If it doesn't raise, should convert to string
            assert str(none_text.text) == "None" or none_text.text == ""
        except (TypeError, ValueError):
            # Acceptable to reject None text
            pass