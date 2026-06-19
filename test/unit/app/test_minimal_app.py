#!/usr/bin/env python3
"""
Unit tests for MinimalLEDApp
Tests the simplified API for SLDK applications.
"""

import unittest
from unittest.mock import Mock, MagicMock, patch
import time
import sys
import os

# Add the SLDK source to Python path for testing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../src'))

from scrollkit.app import MinimalLEDApp


class TestMinimalLEDApp(unittest.TestCase):
    """Test cases for MinimalLEDApp class."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Mock the display components
        self.mock_display = Mock()
        self.mock_memory_info = Mock(free=500*1024*1024, used=100*1024*1024)  # High memory by default
        
        # Patch imports that might not be available in test environment
        self.patches = [
            patch('scrollkit.app.minimal.CircuitPythonApp'),
            patch('scrollkit.app.minimal.StandardPythonApp'),
            patch('scrollkit.app.minimal.get_memory_info', return_value=self.mock_memory_info),
        ]
        
        for p in self.patches:
            p.start()
    
    def tearDown(self):
        """Clean up after tests."""
        for p in self.patches:
            p.stop()
    
    def test_minimal_app_initialization(self):
        """Test that MinimalLEDApp initializes correctly."""
        app = MinimalLEDApp()
        self.assertIsNotNone(app)
        self.assertIsNotNone(app.app)
    
    def test_show_text_basic(self):
        """Test basic text display."""
        app = MinimalLEDApp()
        app.app = Mock()
        app.app.display_static_text = Mock()
        
        app.show_text("Hello")
        app.app.display_static_text.assert_called_once()
        
    def test_show_text_with_color_tuple(self):
        """Test text display with RGB color tuple."""
        app = MinimalLEDApp()
        app.app = Mock()
        app.app.display_static_text = Mock()
        
        app.show_text("Red", color=(255, 0, 0))
        app.app.display_static_text.assert_called_with("Red", (255, 0, 0))
    
    def test_show_text_with_color_name(self):
        """Test text display with color name."""
        app = MinimalLEDApp()
        app.app = Mock()
        app.app.display_static_text = Mock()
        
        # Test standard color names
        color_map = {
            "red": (255, 0, 0),
            "green": (0, 255, 0),
            "blue": (0, 0, 255),
            "yellow": (255, 255, 0),
            "purple": (128, 0, 128),
            "cyan": (0, 255, 255),
            "white": (255, 255, 255),
            "orange": (255, 165, 0),
        }
        
        for name, rgb in color_map.items():
            app.show_text("Test", color=name)
            app.app.display_static_text.assert_called_with("Test", rgb)
    
    def test_scroll_text_basic(self):
        """Test basic text scrolling."""
        app = MinimalLEDApp()
        app.app = Mock()
        app.app.scroll_text = Mock()
        
        app.scroll_text("Long message")
        app.app.scroll_text.assert_called_once()
    
    def test_scroll_text_with_parameters(self):
        """Test text scrolling with custom parameters."""
        app = MinimalLEDApp()
        app.app = Mock()
        app.app.scroll_text = Mock()
        
        app.scroll_text("Message", color="green", delay=0.1)
        app.app.scroll_text.assert_called_with("Message", (0, 255, 0), 0.1)
    
    def test_clear_display(self):
        """Test display clearing."""
        app = MinimalLEDApp()
        app.app = Mock()
        app.app.clear = Mock()
        
        app.clear()
        app.app.clear.assert_called_once()
    
    def test_memory_auto_detection(self):
        """Test that memory is auto-detected on initialization."""
        # Test with low memory (CircuitPython-like)
        with patch('scrollkit.app.minimal.get_memory_info') as mock_mem:
            mock_mem.return_value = Mock(free=50*1024)  # 50KB free
            app = MinimalLEDApp()
            # Should create lightweight version
            self.assertIsNotNone(app)
        
        # Test with high memory (standard Python)
        with patch('scrollkit.app.minimal.get_memory_info') as mock_mem:
            mock_mem.return_value = Mock(free=500*1024*1024)  # 500MB free
            app = MinimalLEDApp()
            # Should create full-featured version
            self.assertIsNotNone(app)
    
    def test_convenience_functions_chaining(self):
        """Test that convenience functions can be chained."""
        app = MinimalLEDApp()
        app.app = Mock()
        app.app.display_static_text = Mock()
        app.app.scroll_text = Mock()
        app.app.clear = Mock()
        
        # Chain multiple operations
        app.clear()
        app.show_text("Hello", color="red")
        app.scroll_text("Scrolling", delay=0.05)
        app.clear()
        
        # Verify all were called
        self.assertEqual(app.app.clear.call_count, 2)
        self.assertEqual(app.app.display_static_text.call_count, 1)
        self.assertEqual(app.app.scroll_text.call_count, 1)
    
    def test_rainbow_color_special_case(self):
        """Test special 'rainbow' color handling."""
        app = MinimalLEDApp()
        app.app = Mock()
        app.app.rainbow_scroll_text = Mock()
        
        # Rainbow should trigger special behavior
        app.scroll_text("Rainbow text", color="rainbow")
        # Rainbow uses special rainbow_scroll_text method
        app.app.rainbow_scroll_text.assert_called_with("Rainbow text", 0.05)
    
    def test_invalid_color_handling(self):
        """Test handling of invalid color names."""
        app = MinimalLEDApp()
        app.app = Mock()
        app.app.display_static_text = Mock()
        
        # Invalid color should default to white
        app.show_text("Test", color="invalid_color")
        app.app.display_static_text.assert_called_with("Test", (255, 255, 255))
    
    def test_time_based_operations(self):
        """Test time-based display operations."""
        app = MinimalLEDApp()
        app.app = Mock()
        app.app.display_static_text = Mock()
        
        # Simulate clock display
        start = time.time()
        for i in range(3):
            app.show_text(f"{i}s", color="cyan")
            if i < 2:  # Don't sleep after last iteration
                time.sleep(0.1)
        
        # Should have taken at least 0.2 seconds
        elapsed = time.time() - start
        self.assertGreaterEqual(elapsed, 0.2)
        self.assertEqual(app.app.display_static_text.call_count, 3)


class TestSLDKTestingPatterns(unittest.TestCase):
    """Test patterns specific to SLDK testing."""
    
    def test_mock_hardware_pattern(self):
        """Test pattern for mocking hardware dependencies."""
        # Pattern 1: Mock at the app level
        app = MinimalLEDApp()
        app.app = Mock()
        
        # Can now test without hardware
        app.show_text("Test")
        self.assertTrue(app.app.display_static_text.called)
    
    def test_environment_detection_pattern(self):
        """Test pattern for environment detection."""
        # Pattern 2: Test environment detection
        with patch('sys.platform', 'linux'):
            # Should detect as Raspberry Pi or similar
            app = MinimalLEDApp()
            self.assertIsNotNone(app)
        
        # Mock CircuitPython environment
        mock_impl = Mock()
        mock_impl.name = 'circuitpython'
        with patch('sys.implementation', mock_impl):
            with patch('scrollkit.app.minimal.get_memory_info') as mock_mem:
                with patch('scrollkit.app.minimal.CircuitPythonApp') as mock_cp_app:
                    mock_mem.return_value = Mock(free=50*1024)  # Low memory for CircuitPython
                    # Should detect CircuitPython
                    app = MinimalLEDApp()
                    self.assertIsNotNone(app)
                    self.assertTrue(app.is_circuitpython)
                    # Verify CircuitPython app was created
                    mock_cp_app.assert_called_once()
    
    def test_display_simulation_pattern(self):
        """Test pattern for display simulation."""
        # Pattern 3: Capture display output for testing
        display_buffer = []
        
        app = MinimalLEDApp()
        app.app = Mock()
        app.app.display_static_text = lambda text, color: display_buffer.append((text, color))
        
        # Run display operations
        app.show_text("A", color="red")
        app.show_text("B", color="green")
        app.show_text("C", color="blue")
        
        # Verify display sequence
        self.assertEqual(len(display_buffer), 3)
        self.assertEqual(display_buffer[0], ("A", (255, 0, 0)))
        self.assertEqual(display_buffer[1], ("B", (0, 255, 0)))
        self.assertEqual(display_buffer[2], ("C", (0, 0, 255)))
    
    def test_async_pattern(self):
        """Test pattern for async operations."""
        # Pattern 4: Test async-compatible code
        app = MinimalLEDApp()
        app.app = Mock()
        
        # Simulate async environment
        async def async_display():
            app.show_text("Async", color="purple")
            return True
        
        # In real async environment, this would use asyncio.run()
        # For testing, we just verify the structure
        self.assertTrue(callable(async_display))


if __name__ == '__main__':
    unittest.main()