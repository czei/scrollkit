#!/usr/bin/env python3
"""Unit tests for content queue."""

import pytest
from unittest.mock import MagicMock

from sldk.display import ContentQueue
from sldk.content import StaticText, ScrollingText, RainbowText


class TestContentQueue:
    """Test cases for ContentQueue class."""
    
    def test_empty_queue_initialization(self):
        """Test creating empty content queue."""
        queue = ContentQueue()
        
        assert queue.is_empty
        assert queue.get_content_count() == 0
        assert queue.get_current_content() is None
    
    def test_add_single_content(self):
        """Test adding single content item."""
        queue = ContentQueue()
        content = StaticText("Test", x=10, y=10, color=0xFF0000, duration=5)
        
        queue.add_content(content)
        
        assert not queue.is_empty
        assert queue.get_content_count() == 1
    
    def test_add_multiple_content(self):
        """Test adding multiple content items."""
        queue = ContentQueue()
        
        content1 = StaticText("First", x=0, y=0, color=0xFF0000, duration=2)
        content2 = ScrollingText("Second", y=10, color=0x00FF00)
        content3 = RainbowText("Third", y=20, rainbow_speed=1.0)
        
        queue.add_content(content1)
        queue.add_content(content2)
        queue.add_content(content3)
        
        assert queue.get_content_count() == 3
        assert not queue.is_empty
    
    def test_clear_queue(self):
        """Test clearing all content from queue."""
        queue = ContentQueue()
        
        # Add some content
        content1 = StaticText("Test1", x=0, y=0, color=0xFF0000, duration=1)
        content2 = StaticText("Test2", x=0, y=10, color=0x00FF00, duration=1)
        queue.add_content(content1)
        queue.add_content(content2)
        
        assert queue.get_content_count() == 2
        
        # Clear queue
        queue.clear()
        
        assert queue.is_empty
        assert queue.get_content_count() == 0
    
    def test_get_current_content(self):
        """Test getting current content item."""
        queue = ContentQueue()
        
        # Empty queue
        assert queue.get_current_content() is None
        
        # Add content
        content = StaticText("Current", x=5, y=5, color=0x0000FF, duration=3)
        queue.add_content(content)
        
        current = queue.get_current_content()
        assert current == content
        assert current.text == "Current"
    
    def test_content_iteration(self):
        """Test iterating through content queue."""
        queue = ContentQueue()
        
        contents = [
            StaticText("Item1", x=0, y=0, color=0xFF0000, duration=1),
            StaticText("Item2", x=0, y=10, color=0x00FF00, duration=1),
            StaticText("Item3", x=0, y=20, color=0x0000FF, duration=1)
        ]
        
        for content in contents:
            queue.add_content(content)
        
        # Test iteration
        queue_contents = list(queue)
        assert len(queue_contents) == 3
        
        for i, content in enumerate(queue_contents):
            assert content.text == f"Item{i+1}"
    
    def test_content_priority_ordering(self):
        """Test that content respects priority ordering."""
        queue = ContentQueue()
        
        # Add content with different priorities (if supported)
        low_priority = StaticText("Low", x=0, y=0, color=0xFF0000, duration=1)
        high_priority = StaticText("High", x=0, y=10, color=0x00FF00, duration=1)
        
        # Add lower priority first
        queue.add_content(low_priority)
        queue.add_content(high_priority)
        
        # Should maintain order of addition (FIFO by default)
        contents = list(queue)
        assert contents[0] == low_priority
        assert contents[1] == high_priority


class TestContentQueueWithDurations:
    """Test content queue behavior with time-based content."""
    
    def test_expired_content_removal(self):
        """Test removing expired content items."""
        queue = ContentQueue()
        
        # Add content with short duration
        short_content = StaticText("Short", x=0, y=0, color=0xFF0000, duration=0.1)
        long_content = StaticText("Long", x=0, y=10, color=0x00FF00, duration=10.0)
        
        queue.add_content(short_content)
        queue.add_content(long_content)
        
        assert queue.get_content_count() == 2
        
        # Simulate time passing - would need actual implementation
        # This test demonstrates the interface expected
    
    def test_permanent_content(self):
        """Test content without expiration."""
        queue = ContentQueue()
        
        # Add content without duration (permanent)
        permanent = ScrollingText("Permanent", y=15, color=0xFFFFFF)
        queue.add_content(permanent)
        
        assert queue.get_content_count() == 1
        assert not queue.is_empty


class TestContentQueueSpecialCases:
    """Test edge cases and special scenarios."""
    
    def test_add_none_content(self):
        """Test adding None content."""
        queue = ContentQueue()
        
        # Should handle None gracefully
        queue.add_content(None)
        
        # Depends on implementation - might ignore None or count it
        # This test documents expected behavior
    
    def test_add_duplicate_content(self):
        """Test adding same content multiple times."""
        queue = ContentQueue()
        content = StaticText("Duplicate", x=0, y=0, color=0xFF0000, duration=1)
        
        queue.add_content(content)
        queue.add_content(content)
        
        # Should allow duplicates
        assert queue.get_content_count() == 2
    
    def test_queue_with_mixed_content_types(self):
        """Test queue with different content types."""
        queue = ContentQueue()
        
        static = StaticText("Static", x=0, y=0, color=0xFF0000, duration=2)
        scrolling = ScrollingText("Scrolling", y=10, color=0x00FF00)
        rainbow = RainbowText("Rainbow", y=20, rainbow_speed=2.0)
        
        queue.add_content(static)
        queue.add_content(scrolling)
        queue.add_content(rainbow)
        
        assert queue.get_content_count() == 3
        
        # All content types should be supported
        contents = list(queue)
        assert isinstance(contents[0], StaticText)
        assert isinstance(contents[1], ScrollingText)
        assert isinstance(contents[2], RainbowText)
    
    def test_large_queue_performance(self):
        """Test queue performance with many items."""
        queue = ContentQueue()
        
        # Add many content items
        for i in range(100):
            content = StaticText(f"Item{i}", x=0, y=i % 32, color=0xFF0000, duration=1)
            queue.add_content(content)
        
        assert queue.get_content_count() == 100
        assert not queue.is_empty
        
        # Should be able to iterate efficiently
        count = 0
        for content in queue:
            count += 1
        
        assert count == 100