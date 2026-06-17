#!/usr/bin/env python3
"""PyTest configuration and fixtures for SLDK test suite."""

import pytest
import sys
import os
from unittest.mock import MagicMock, patch

# Add src to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))


@pytest.fixture
def mock_hardware():
    """Mock CircuitPython hardware components."""
    mocks = {}
    
    # Mock displayio components
    mocks['displayio'] = MagicMock()
    mocks['displayio.Display'] = MagicMock()
    mocks['displayio.Group'] = MagicMock()
    mocks['displayio.Bitmap'] = MagicMock()
    mocks['displayio.Palette'] = MagicMock()
    mocks['displayio.TileGrid'] = MagicMock()
    
    # Mock adafruit components
    mocks['adafruit_matrixportal'] = MagicMock()
    mocks['adafruit_display_text'] = MagicMock()
    mocks['board'] = MagicMock()
    mocks['busio'] = MagicMock()
    mocks['digitalio'] = MagicMock()
    
    # Mock neopixel
    mocks['neopixel'] = MagicMock()
    
    return mocks


@pytest.fixture 
def mock_circuitpython_imports(mock_hardware):
    """Mock all CircuitPython-specific imports."""
    with patch.dict('sys.modules', mock_hardware):
        yield mock_hardware


@pytest.fixture
def sample_display_config():
    """Sample display configuration for testing."""
    return {
        'width': 64,
        'height': 32,
        'brightness': 0.8,
        'auto_brightness': True,
        'rotation': 0
    }


@pytest.fixture
def sample_web_config():
    """Sample web server configuration for testing."""
    return {
        'host': '0.0.0.0',
        'port': 8080,
        'enable_cors': True,
        'debug': False,
        'static_path': '/static'
    }


@pytest.fixture
def sample_content_data():
    """Sample content for testing display content."""
    return {
        'static_text': {
            'text': 'Hello World',
            'x': 10,
            'y': 15,
            'color': 0xFF0000,
            'duration': 5.0
        },
        'scrolling_text': {
            'text': 'This is scrolling text',
            'y': 20,
            'color': 0x00FF00,
            'speed': 30
        },
        'rainbow_text': {
            'text': 'Rainbow!',
            'y': 8,
            'rainbow_speed': 2.0
        }
    }


@pytest.fixture
def mock_display():
    """Mock display interface for testing."""
    from unittest.mock import AsyncMock
    
    display = MagicMock()
    display.width = 64
    display.height = 32
    display.brightness = 0.8
    
    # Make async methods actually async
    display.initialize = AsyncMock()
    display.clear = AsyncMock()
    display.set_pixel = AsyncMock()
    display.render = AsyncMock()
    display.show = AsyncMock()
    display.draw_text = AsyncMock()
    display.scroll_text = AsyncMock()
    display.fill = AsyncMock()
    
    return display


@pytest.fixture
def mock_web_request():
    """Mock web request for testing handlers."""
    request = MagicMock()
    request.method = 'GET'
    request.path = '/'
    request.query_params = {}
    request.headers = {'User-Agent': 'Test'}
    request.body = b''
    
    return request


@pytest.fixture
def sample_template_context():
    """Sample template context for testing."""
    return {
        'title': 'SLDK Test Page',
        'user': {'name': 'Test User', 'logged_in': True},
        'items': ['apple', 'banana', 'cherry'],
        'count': 42,
        'settings': {
            'brightness': 80,
            'auto_update': True,
            'theme': 'dark'
        }
    }


@pytest.fixture
def effects_test_data():
    """Test data for effects system."""
    return {
        'sparkle_config': {
            'intensity': 5,
            'color': 0xFFFFFF,
            'duration': 10.0
        },
        'rainbow_config': {
            'speed': 2.0,
            'saturation': 1.0,
            'brightness': 0.8
        },
        'particle_config': {
            'max_particles': 10,
            'spawn_rate': 0.3,
            'lifetime': 3.0
        }
    }


@pytest.fixture
def mock_time():
    """Mock time functions for deterministic testing."""
    import time
    with patch('time.time') as mock_time_func:
        mock_time_func.return_value = 1000.0
        with patch('time.monotonic') as mock_monotonic:
            mock_monotonic.return_value = 1000.0
            yield {'time': mock_time_func, 'monotonic': mock_monotonic}


class MockAsyncContext:
    """Helper for testing async context managers."""
    
    def __init__(self, return_value=None):
        self.return_value = return_value
        
    async def __aenter__(self):
        return self.return_value
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


@pytest.fixture
def mock_async_context():
    """Factory for creating mock async context managers."""
    return MockAsyncContext


# Test data constants
TEST_FONTS = {
    'small': {'width': 4, 'height': 6},
    'medium': {'width': 6, 'height': 8}, 
    'large': {'width': 8, 'height': 12}
}

TEST_COLORS = {
    'red': 0xFF0000,
    'green': 0x00FF00,
    'blue': 0x0000FF,
    'white': 0xFFFFFF,
    'black': 0x000000,
    'yellow': 0xFFFF00,
    'cyan': 0x00FFFF,
    'magenta': 0xFF00FF
}

TEST_MATRIX_SIZES = [
    (32, 16),  # Small matrix
    (64, 32),  # Standard matrix
    (128, 64), # Large matrix
]