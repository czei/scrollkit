"""
Helper utilities for testing CircuitPython code.

This module provides common testing patterns and utilities to make
testing CircuitPython code easier in a standard Python environment.
"""
import os
import json
import tempfile
from unittest.mock import MagicMock, patch
from functools import wraps

def with_temp_file(content=None):
    """
    Decorator that creates a temporary file for the duration of a test.
    
    Args:
        content: Optional string content to write to the file
        
    The decorated test function receives the temp file path as an argument.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                file_path = temp_file.name
                if content is not None:
                    temp_file.write(content.encode('utf-8'))
            
            try:
                # Add the file_path to the function arguments
                return func(*args, file_path=file_path, **kwargs)
            finally:
                # Clean up the temporary file
                if os.path.exists(file_path):
                    os.remove(file_path)
        
        return wrapper
    return decorator

def with_temp_json(data):
    """
    Decorator that creates a temporary JSON file for the duration of a test.
    
    Args:
        data: Dict or list to serialize as JSON
        
    The decorated test function receives the temp file path as an argument.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                file_path = temp_file.name
                json_content = json.dumps(data, indent=2)
                temp_file.write(json_content.encode('utf-8'))
            
            try:
                # Add the file_path to the function arguments
                return func(*args, json_path=file_path, **kwargs)
            finally:
                # Clean up the temporary file
                if os.path.exists(file_path):
                    os.remove(file_path)
        
        return wrapper
    return decorator

class MockMatrixPortal:
    """
    Mock for the MatrixPortal class that provides the common functionality
    used in tests without requiring the actual hardware.
    """
    def __init__(self, width=64, height=32, bit_depth=4, rotation=0):
        self.display = MagicMock()
        self.display.width = width
        self.display.height = height
        self.graphics = MagicMock()
        self.network = MagicMock()
        
        # Set up mocked methods
        self.set_background = MagicMock()
        self.add_text = MagicMock()
        self.scroll_text = MagicMock()
        self.set_text = MagicMock()
        self.set_text_color = MagicMock()

class MockHardwareContext:
    """
    Context manager that sets up a full hardware mock environment
    for testing code that assumes hardware is present.
    """
    def __init__(self):
        self.patches = []
    
    def __enter__(self):
        # Create mock instances for common hardware
        self.matrix = MockMatrixPortal()
        
        # Patch common hardware-related imports
        hw_modules = {
            'board': MagicMock(),
            'displayio': MagicMock(),
            'terminalio': MagicMock(),
            'storage': MagicMock(),
            'adafruit_matrixportal.matrix.Matrix': MagicMock(return_value=self.matrix),
            'wifi': MagicMock(),
            'socketpool': MagicMock(),
            'rtc': MagicMock(),
            'digitalio': MagicMock(),
        }
        
        # Apply all the patches
        for mod_name, mock_obj in hw_modules.items():
            patcher = patch(mod_name, mock_obj)
            self.patches.append(patcher)
            patcher.start()
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Stop all the patches
        for patcher in self.patches:
            patcher.stop()
        
        # Clear the patches list
        self.patches = []

def mock_network_response(status_code=200, content=''):
    """
    Creates a mock HTTP response object for testing network code.
    """
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.content = content.encode('utf-8') if isinstance(content, str) else content
    mock_response.text = content if isinstance(content, str) else content.decode('utf-8')
    
    def mock_json():
        if isinstance(content, str):
            return json.loads(content)
        return json.loads(content.decode('utf-8'))
    
    mock_response.json = mock_json
    return mock_response