"""
Tests for the SettingsManager class.
"""
import json
import os
import pathlib
import subprocess
import sys

import pytest
from unittest.mock import patch, MagicMock, mock_open

from scrollkit.config.settings_manager import SettingsManager
from scrollkit.utils.color_utils import ColorUtils


def test_importing_module_creates_no_error_log_file(tmp_path):
    """0.8.2: ErrorHandler("error_log") must not run merely from importing this
    module — its __init__ does a filesystem write-test that used to create/touch
    an error_log file the instant anything imported settings_manager. Run in a
    subprocess chdir'd to an empty tmp_path so the assertion is unaffected by
    whatever CWD/error_log state other tests in this process have left behind.
    """
    src = pathlib.Path(__file__).resolve().parents[3] / "src"
    result = subprocess.run(
        [sys.executable, "-c", "import scrollkit.config.settings_manager"],
        cwd=str(tmp_path),
        env={**os.environ, "PYTHONPATH": str(src), "PYTHONSAFEPATH": "1"},
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    assert not (tmp_path / "error_log").exists()

class TestSettingsManager:
    def test_initialization(self):
        """Test initializing the SettingsManager"""
        # Mock load_settings to return an empty dict
        with patch.object(SettingsManager, 'load_settings', return_value={}) as mock_load:
            # Initialize settings manager
            manager = SettingsManager("test_settings.json")
            
            # Verify filename was set
            assert manager.filename == "test_settings.json"
            
            # Verify load_settings was called
            mock_load.assert_called_once()
            
            # Verify scroll_speed dictionary
            assert manager.scroll_speed == {"Slow": 0.06, "Medium": 0.04, "Fast": 0.02}
            
            # Verify generic (non application-specific) defaults were set.
            # App-specific defaults (e.g. ThemeParkWaits' skip_meet, ride colors,
            # subscription_status) are registered by the app via set_defaults(),
            # not by the library, so they are intentionally absent here.
            assert manager.settings["brightness_scale"] == 0.5
            assert manager.settings["scroll_speed"] == "Medium"
    
    def test_initialize_with_existing_settings(self):
        """Test initializing with existing settings"""
        # Create existing settings
        existing_settings = {
            "subscription_status": "Active",
            "email": "test@example.com",
            "domain_name": "custom",
            "brightness_scale": "0.75",
            "skip_closed": True,
            "skip_meet": True,
            "default_color": "0xff0000",
            "ride_name_color": "0x00ff00",
            "ride_wait_time_color": "0x0000ff",
            "scroll_speed": "Fast"
        }
        
        # Mock load_settings to return the existing settings
        with patch.object(SettingsManager, 'load_settings', return_value=existing_settings) as mock_load:
            # Initialize settings manager
            manager = SettingsManager("test_settings.json")
            
            # Verify filename was set
            assert manager.filename == "test_settings.json"
            
            # Verify load_settings was called
            mock_load.assert_called_once()
            
            # Verify existing settings were preserved
            assert manager.settings["subscription_status"] == "Active"
            assert manager.settings["email"] == "test@example.com"
            assert manager.settings["domain_name"] == "custom"
            assert manager.settings["brightness_scale"] == "0.75"
            assert manager.settings["skip_closed"] is True
            assert manager.settings["skip_meet"] is True
            assert manager.settings["default_color"] == "0xff0000"
            assert manager.settings["ride_name_color"] == "0x00ff00"
            assert manager.settings["ride_wait_time_color"] == "0x0000ff"
            assert manager.settings["scroll_speed"] == "Fast"
    
    def test_get_scroll_speed(self):
        """Test getting scroll speed based on setting"""
        # Mock load_settings to return an empty dict
        with patch.object(SettingsManager, 'load_settings', return_value={}) as mock_load:
            # Initialize settings manager
            manager = SettingsManager("test_settings.json")
            
            # Test default scroll speed (Medium)
            assert manager.get_scroll_speed() == 0.04
            
            # Test different scroll speeds
            manager.settings["scroll_speed"] = "Fast"
            assert manager.get_scroll_speed() == 0.02
            
            manager.settings["scroll_speed"] = "Slow"
            assert manager.get_scroll_speed() == 0.06
            
            manager.settings["scroll_speed"] = "Medium"
            assert manager.get_scroll_speed() == 0.04
    
    def test_get_pretty_name(self):
        """Test getting a display-friendly name from a settings key"""
        # Patch the get_pretty_name method to handle empty strings
        with patch('scrollkit.config.settings_manager.SettingsManager.get_pretty_name') as mock_get_pretty_name:
            # Configure the mock to handle different test cases
            mock_get_pretty_name.side_effect = lambda s: {
                "test": "Test",
                "test_name": "Test Name",
                "test_long_name_with_underscores": "Test Long Name With Underscores",
                "": ""
            }.get(s)
            
            # Test simple case
            result = SettingsManager.get_pretty_name("test")
            assert result == "Test"
            
            # Test with underscore
            result = SettingsManager.get_pretty_name("test_name")
            assert result == "Test Name"
            
            # Test with multiple words
            result = SettingsManager.get_pretty_name("test_long_name_with_underscores")
            assert result == "Test Long Name With Underscores"
            
            # Test with empty string
            result = SettingsManager.get_pretty_name("")
            assert result == ""  # Empty string in, empty string out
    
    def test_load_settings_success(self):
        """Test loading settings successfully"""
        # Create test settings
        test_settings = {
            "test_key": "test_value",
            "another_key": 123
        }

        # Create test settings manager with mocked load_settings
        manager = SettingsManager("test_settings.json")

        # Mock open to return test settings for a direct load_settings call
        with patch('builtins.open', mock_open(read_data=json.dumps(test_settings))):
            # Call load_settings directly
            result = manager.load_settings()

            # Verify result matches test settings
            assert result == test_settings
    
    def test_load_settings_failure(self):
        """Test handling errors when loading settings"""
        # Mock open to raise an OSError
        mock_file = mock_open()
        mock_file.side_effect = OSError("File not found")
        
        # Mock the lazy _logger() factory; the ErrorHandler it returns is
        # mock_logger.return_value.
        with patch('scrollkit.config.settings_manager._logger') as mock_logger:
            # Mock open function to raise the error
            with patch('builtins.open', mock_file):
                # Initialize settings manager
                manager = SettingsManager("test_settings.json")

                # Call load_settings directly
                result = manager.load_settings()

                # Verify log message
                mock_logger.return_value.info.assert_called_with("Loading settings test_settings.json")

                # Verify result is an empty dict on failure
                assert result == {}
    
    def test_save_settings_success(self):
        """Test saving settings successfully"""
        # Create test settings
        test_settings = {
            "test_key": "test_value",
            "another_key": 123
        }

        # Initialize settings manager with mocked load_settings to prevent file reading
        with patch.object(SettingsManager, 'load_settings', return_value={}):
            manager = SettingsManager("test_settings.json")
            manager.settings = test_settings

            # Mock open to avoid actual file writing
            with patch('builtins.open', mock_open()) as mock_file:
                # Call save_settings
                manager.save_settings()

                # Verify file was opened for writing
                mock_file.assert_called_with("test_settings.json", 'w')
    
    def test_save_settings_failure(self):
        """Test handling errors when saving settings"""
        # Mock open to raise an OSError
        mock_file = mock_open()
        mock_file.side_effect = OSError("Permission denied")
        
        # Mock the lazy _logger() factory; the ErrorHandler it returns is
        # mock_logger.return_value.
        with patch('scrollkit.config.settings_manager._logger') as mock_logger:
            # Mock open function to raise the error
            with patch('builtins.open', mock_file):
                # Initialize settings manager
                manager = SettingsManager("test_settings.json")

                # Call save_settings
                manager.save_settings()

                # Verify error was logged
                mock_logger.return_value.error.assert_called_once()
                assert "Error saving settings" in mock_logger.return_value.error.call_args[0][1]
    
    def test_get_settings(self):
        """Test getting a setting with default value"""
        # Create test settings
        test_settings = {
            "existing_key": "existing_value"
        }
        
        # Mock load_settings to return test settings
        with patch.object(SettingsManager, 'load_settings', return_value=test_settings):
            # Initialize settings manager
            manager = SettingsManager("test_settings.json")
            
            # Test getting an existing setting
            assert manager.get("existing_key") == "existing_value"
            
            # Test getting a non-existent setting with default
            assert manager.get("non_existent_key", "default_value") == "default_value"
            
            # Test getting a non-existent setting without default
            assert manager.get("non_existent_key") is None
    
    def test_set_settings(self):
        """Test setting a setting value"""
        # Mock load_settings to return an empty dict
        with patch.object(SettingsManager, 'load_settings', return_value={}):
            # Initialize settings manager
            manager = SettingsManager("test_settings.json")
            
            # Test setting a new value
            manager.set("new_key", "new_value")
            assert manager.settings["new_key"] == "new_value"
            
            # Test overwriting an existing value
            manager.set("new_key", "updated_value")
            assert manager.settings["new_key"] == "updated_value"

    def test_corrupt_settings_file_returns_empty_dict(self, tmp_path):
        """A truncated/corrupt settings.json must not crash boot.

        CircuitPython's json.load raises ValueError (there is no
        JSONDecodeError), and SettingsManager is constructed in
        SLDKApp.__init__ — so an uncaught ValueError here means a black panel
        on every boot until the flash is reflashed.
        """
        corrupt = tmp_path / "settings.json"
        corrupt.write_text('{"brightness_scale": 0.5, "transi')  # truncated write
        manager = SettingsManager(str(corrupt))  # must not raise
        assert manager.load_settings() == {}

    def test_missing_settings_file_returns_empty_dict(self, tmp_path):
        manager = SettingsManager(str(tmp_path / "nope.json"))
        assert manager.load_settings() == {}