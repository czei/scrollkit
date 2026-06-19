"""
Tests for the error handling utility.
"""
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock

from scrollkit.utils.error_handler import ErrorHandler
from test.helpers import with_temp_file

class TestErrorHandler:
    def test_initialization(self):
        """Test basic initialization"""
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            log_path = temp_file.name

        try:
            # Mock the storage module
            with patch('scrollkit.utils.error_handler.storage') as mock_storage:
                # Set up the mock to report writable filesystem
                mock_mount = MagicMock()
                mock_mount.readonly = False
                mock_storage.getmount.return_value = mock_mount

                handler = ErrorHandler(log_path)
                assert handler.fileName == log_path
                # Should be writable as we mocked it
                assert not handler.is_readonly
        finally:
            if os.path.exists(log_path):
                os.remove(log_path)
    
    @patch('scrollkit.utils.error_handler.storage')
    def test_readonly_filesystem_detection(self, mock_storage):
        """Test detection of read-only filesystem"""
        # Setup mock for read-only filesystem
        mock_mount = MagicMock()
        mock_mount.readonly = True
        mock_storage.getmount.return_value = mock_mount
        
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            log_path = temp_file.name
            
        try:
            with patch('builtins.print') as mock_print:
                handler = ErrorHandler(log_path)
                assert handler.is_readonly
                
                # Verify initialization message
                mock_print.assert_any_call("ErrorHandler initialized - read-only filesystem")
        finally:
            if os.path.exists(log_path):
                os.remove(log_path)
    
    def test_logging_messages(self):
        """Test logging messages to file"""
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            file_path = temp_file.name

        try:
            # Mock the storage module
            with patch('scrollkit.utils.error_handler.storage') as mock_storage:
                # Set up the mock to report writable filesystem
                mock_mount = MagicMock()
                mock_mount.readonly = False
                mock_storage.getmount.return_value = mock_mount

                # Create handler in development mode to test debug logging
                handler = ErrorHandler(file_path, mode=ErrorHandler.DEVELOPMENT)
                handler.info("Test info message")
                handler.debug("Test debug message")

                with open(file_path, 'r') as f:
                    content = f.read()
                    assert "Test info message" in content
                    assert "Test debug message" in content
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
    
    def test_error_logging(self):
        """Test logging error with stack trace"""
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            file_path = temp_file.name

        try:
            # Mock the storage module
            with patch('scrollkit.utils.error_handler.storage') as mock_storage:
                # Set up the mock to report writable filesystem
                mock_mount = MagicMock()
                mock_mount.readonly = False
                mock_storage.getmount.return_value = mock_mount

                handler = ErrorHandler(file_path)

                try:
                    # Generate a test exception
                    raise ValueError("Test error")
                except ValueError as e:
                    handler.error(e, "Error description")

                with open(file_path, 'r') as f:
                    content = f.read()
                    assert "Error description:Test error" in content
                    assert "stack trace:" in content
                    assert "ValueError" in content
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
    
    def test_filter_non_ascii(self):
        """Test filtering non-ASCII characters"""
        assert ErrorHandler.filter_non_ascii("Normal ASCII text") == "Normal ASCII text"
        assert ErrorHandler.filter_non_ascii("Text with emoji 😊") == "Text with emoji "
        assert ErrorHandler.filter_non_ascii("Special characters: ñáéíóú") == "Special characters: "
        assert ErrorHandler.filter_non_ascii(None) == ""
    
    @patch('builtins.open')
    def test_readonly_filesystem_write_fallback(self, mock_open):
        """Test fallback to console when filesystem is read-only"""
        # Force a write error to simulate read-only filesystem
        mock_open.side_effect = OSError("Read-only filesystem")
        
        with patch('builtins.print') as mock_print:
            handler = ErrorHandler("/nonexistent/path/error.log")
            # Should detect read-only state due to OSError
            assert handler.is_readonly
            
            # Log some messages
            handler.info("Test info message")
            handler.debug("Test debug message")
            
            # Verify they were printed to console
            mock_print.assert_any_call("Test info message")
            mock_print.assert_any_call("Test debug message")
    
    def test_development_production_modes(self):
        """Test that debug messages are only written to file in development mode"""
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            file_path = temp_file.name

        try:
            # Mock the storage module
            with patch('scrollkit.utils.error_handler.storage') as mock_storage:
                # Set up the mock to report writable filesystem
                mock_mount = MagicMock()
                mock_mount.readonly = False
                mock_storage.getmount.return_value = mock_mount

                # Test production mode (default)
                handler_prod = ErrorHandler(file_path, mode=ErrorHandler.PRODUCTION)
                handler_prod.info("Production info message")
                handler_prod.debug("Production debug message")
                handler_prod.error(None, "Production error message")

                with open(file_path, 'r') as f:
                    content = f.read()
                    assert "Production info message" in content
                    assert "Production debug message" not in content  # Debug not written in production
                    assert "Production error message" in content

                # Clear the file
                with open(file_path, 'w') as f:
                    f.write("")

                # Test development mode
                handler_dev = ErrorHandler(file_path + "_dev", mode=ErrorHandler.DEVELOPMENT)
                handler_dev.info("Development info message")
                handler_dev.debug("Development debug message")
                handler_dev.error(None, "Development error message")

                with open(file_path + "_dev", 'r') as f:
                    content = f.read()
                    assert "Development info message" in content
                    assert "Development debug message" in content  # Debug IS written in development
                    assert "Development error message" in content

        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
            if os.path.exists(file_path + "_dev"):
                os.remove(file_path + "_dev")
    
    def test_global_mode_setting(self):
        """Test setting global mode"""
        # Store original mode
        original_mode = ErrorHandler.get_mode()
        
        try:
            # Test setting development mode
            ErrorHandler.set_mode(ErrorHandler.DEVELOPMENT)
            assert ErrorHandler.get_mode() == ErrorHandler.DEVELOPMENT
            
            # Test setting production mode
            ErrorHandler.set_mode(ErrorHandler.PRODUCTION)
            assert ErrorHandler.get_mode() == ErrorHandler.PRODUCTION
            
            # Test invalid mode
            with pytest.raises(ValueError) as exc_info:
                ErrorHandler.set_mode("invalid_mode")
            assert "Invalid mode" in str(exc_info.value)
            
        finally:
            # Restore original mode
            ErrorHandler.set_mode(original_mode)