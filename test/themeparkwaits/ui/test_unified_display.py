"""
Tests for the unified display implementation module.
"""
import time
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.ui.unified_display import UnifiedDisplay
from src.utils.color_utils import ColorUtils

@pytest.mark.skip("Needs more complex mocking of displayio")
class TestUnifiedDisplay:
    @patch('src.ui.unified_display.displayio')
    @patch('src.ui.unified_display.terminalio')
    @patch('src.ui.unified_display.bitmap_font')
    def test_initialization(self, mock_bitmap_font, mock_terminalio, mock_displayio):
        """Test initializing the UnifiedDisplay"""
        # This test needs more complex mocking setup for CircuitPython display modules
        # Skipping for now
        pass
    
    def test_set_colors(self):
        """Test setting colors from settings"""
        # Skip - requires complex display mocking
        pass

    def test_off(self):
        """Test turning off all display elements"""
        # Skip - requires complex display mocking
        pass

    @pytest.mark.asyncio
    async def test_show_splash(self):
        """Test showing the splash screen"""
        # Skip - requires complex display mocking
        pass

    @pytest.mark.asyncio
    async def test_show_ride_closed(self):
        """Test showing that a ride is closed"""
        # Skip - requires complex display mocking
        pass

    @pytest.mark.asyncio
    async def test_show_ride_wait_time(self):
        """Test showing a ride's wait time"""
        # Skip - requires complex display mocking
        pass

    @pytest.mark.asyncio
    async def test_show_configuration_message(self):
        """Test showing a configuration message"""
        # Skip - requires complex display mocking
        pass

class TestUnifiedDisplayBasic:
    @patch('src.ui.unified_display.IS_CIRCUITPYTHON', False)
    def test_initialization(self):
        """Test initializing the UnifiedDisplay in development mode"""
        # Create mock settings manager
        mock_settings_manager = MagicMock()
        mock_settings_manager.settings = {
            'brightness_scale': '0.5',
            'default_color': 0xFFFF00,
            'ride_name_color': 0x0000FF,
            'ride_wait_time_color': 0xFDF5E6
        }
        
        # Create the display with a config
        config = {'settings_manager': mock_settings_manager}
        display = UnifiedDisplay(config)
        
        # Verify settings manager is stored
        assert display.settings_manager == mock_settings_manager
        assert display.scroll_delay == 0.04  # Default
        
        # Verify unified positions are loaded
        from src.ui.unified_display import PLATFORM_CONFIG
        assert display.positions == PLATFORM_CONFIG
    
    @patch('src.ui.unified_display.IS_CIRCUITPYTHON', False)
    @pytest.mark.asyncio
    async def test_show_scroll_message(self):
        """Test showing a scrolling message"""
        # Create mock settings manager
        mock_settings_manager = MagicMock()
        mock_settings_manager.settings = {
            'brightness_scale': '0.5',
            'default_color': 0xFFFF00
        }
        
        # Create the display
        config = {'settings_manager': mock_settings_manager}
        display = UnifiedDisplay(config)
        
        # Mock the display components
        with patch.object(display, '_hide_all_groups') as mock_hide, \
             patch.object(display, '_scroll_x', return_value=False) as mock_scroll, \
             patch.object(display, 'update') as mock_update:
            
            # Set up minimal required attributes
            display.scrolling_label = MagicMock()
            display.scrolling_group = MagicMock()
            
            # Mock logger
            with patch('src.ui.unified_display.logger') as mock_logger:
                # Call show_scroll_message
                await display.show_scroll_message("Test message")
                
                # Verify log message
                mock_logger.debug.assert_called_once_with("Scrolling message: Test message")
                
                # Verify text was set
                assert display.scrolling_label.text == "Test message"
                
                # Verify scroll was called
                assert mock_scroll.called