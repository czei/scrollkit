"""
Tests for the Vacation model class.
"""
import pytest
from unittest.mock import patch, MagicMock, PropertyMock

from src.models.vacation import Vacation


class TestVacation:
    def test_initialization(self):
        """Test initialization with default and custom parameters"""
        # Default initialization
        vacation = Vacation()
        assert vacation.name == ""
        assert vacation.year == 0
        assert vacation.month == 0
        assert vacation.day == 0
        assert not vacation.is_set()
        
        # Custom initialization
        vacation = Vacation("Disney World", 2023, 12, 25)
        assert vacation.name == "Disney World"
        assert vacation.year == 2023
        assert vacation.month == 12
        assert vacation.day == 25
        assert vacation.is_set()
    
    def test_is_set(self):
        """Test is_set method under various conditions"""
        # Not set - default values
        vacation = Vacation()
        assert not vacation.is_set()
        
        # Not set - missing name
        vacation = Vacation("", 2023, 12, 25)
        assert not vacation.is_set()
        
        # Not set - invalid year (must be > 1999)
        vacation = Vacation("Disney World", 1999, 12, 25)
        assert not vacation.is_set()
        
        # Not set - invalid month
        vacation = Vacation("Disney World", 2023, 0, 25)
        assert not vacation.is_set()
        
        # Not set - invalid day
        vacation = Vacation("Disney World", 2023, 12, 0)
        assert not vacation.is_set()
        
        # Properly set
        vacation = Vacation("Disney World", 2023, 12, 25)
        assert vacation.is_set()
    
    def test_parse(self):
        """Test parsing URL parameters"""
        # Mock the url_decode function
        with patch('src.models.vacation.url_decode', side_effect=lambda x: x.replace('%20', ' ')):
            vacation = Vacation()
            
            # Parse complete parameters
            vacation.parse("Name=Disney%20World&Year=2023&Month=12&Day=25")
            assert vacation.name == "Disney World"
            assert vacation.year == 2023
            assert vacation.month == 12
            assert vacation.day == 25
            
            # Parse partial parameters
            vacation = Vacation()
            vacation.parse("Name=Epcot&Year=2024")
            assert vacation.name == "Epcot"
            assert vacation.year == 2024
            assert vacation.month == 0  # Unchanged
            assert vacation.day == 0    # Unchanged
    
    @patch('src.models.vacation.datetime')
    def test_get_days_until(self, mock_datetime_module):
        """Test calculating days until vacation"""
        # Create vacation object
        vacation = Vacation("Disney World", 2023, 12, 25)
        
        # Set up mock datetime
        mock_today = MagicMock()
        mock_today.year = 2023
        mock_today.month = 12
        mock_today.day = 20
        
        mock_future = MagicMock()
        mock_future.__sub__ = MagicMock()
        
        mock_diff = MagicMock()
        mock_diff.days = 5
        mock_future.__sub__.return_value = mock_diff
        
        # Configure the mocks
        mock_datetime_module.now.return_value = mock_today
        mock_datetime_module.return_value = mock_future
        
        # Call the method
        days_until = vacation.get_days_until()
        
        # Verify results
        assert days_until == 6  # 5 days + 1 for inclusive counting
        mock_datetime_module.now.assert_called_once()
        mock_datetime_module.assert_called_once_with(2023, 12, 25)
        mock_future.__sub__.assert_called_once_with(mock_today)
    
    def test_store_settings(self):
        """Test storing vacation settings"""
        vacation = Vacation("Disney World", 2023, 12, 25)
        
        # Create mock settings manager
        mock_sm = MagicMock()
        mock_sm.settings = {}
        
        # Store settings
        vacation.store_settings(mock_sm)
        
        # Verify settings were stored correctly
        assert mock_sm.settings["next_visit"] == "Disney World"
        assert mock_sm.settings["next_visit_year"] == 2023
        assert mock_sm.settings["next_visit_month"] == 12
        assert mock_sm.settings["next_visit_day"] == 25
    
    def test_load_settings(self):
        """Test loading vacation settings"""
        vacation = Vacation()
        
        # Create mock settings manager
        mock_sm = MagicMock()
        
        # Set up keys method
        mock_keys = ["next_visit", "next_visit_year", "next_visit_month", "next_visit_day"]
        mock_sm.settings.keys.return_value = mock_keys
        
        # Set up get method
        mock_sm.settings.get = MagicMock(side_effect=lambda key: {
            "next_visit": "Disney World",
            "next_visit_year": 2023,
            "next_visit_month": 12,
            "next_visit_day": 25
        }.get(key))
        
        # Patch the "in" operator for settings dictionary
        mock_sm.settings.__contains__ = MagicMock(side_effect=lambda key: key in mock_keys)
        
        # Load settings
        vacation.load_settings(mock_sm)
        
        # Verify settings were loaded correctly
        assert vacation.name == "Disney World"
        assert vacation.year == 2023
        assert vacation.month == 12
        assert vacation.day == 25
        
        # Test with partial settings
        vacation = Vacation()
        
        # Set up keys method with partial settings
        mock_keys = ["next_visit", "next_visit_year"]
        mock_sm.settings.keys.return_value = mock_keys
        
        # Set up get method for partial settings
        mock_sm.settings.get = MagicMock(side_effect=lambda key: {
            "next_visit": "Epcot",
            "next_visit_year": 2024
        }.get(key))
        
        # Patch the "in" operator for settings dictionary
        mock_sm.settings.__contains__ = MagicMock(side_effect=lambda key: key in mock_keys)
        
        # Load settings
        vacation.load_settings(mock_sm)
        
        # Verify only available settings were loaded
        assert vacation.name == "Epcot"
        assert vacation.year == 2024
        assert vacation.month == 0  # Unchanged
        assert vacation.day == 0    # Unchanged