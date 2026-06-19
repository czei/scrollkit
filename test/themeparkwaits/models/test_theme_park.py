"""
Tests for the ThemePark model class.
"""
import pytest
from src.models.theme_park import ThemePark

class TestThemePark:
    def test_initialization(self):
        """Test that ThemePark can be initialized with no args"""
        park = ThemePark()
        assert isinstance(park, ThemePark)
    
    def test_initialization_with_data(self, magic_kingdom_data):
        """Test initialization with data from fixture"""
        park = ThemePark(magic_kingdom_data, "Disney Magic Kingdom", 6)
        assert park.name == "Disney Magic Kingdom"
        assert park.id == 6
        assert len(park.rides) > 0
    
    def test_get_wait_time(self, magic_kingdom_data):
        """Test getting wait time for a ride"""
        park = ThemePark(magic_kingdom_data, "Disney Magic Kingdom")
        wait_time = park.get_wait_time('Haunted Mansion')
        assert wait_time == 15
        
        # Also test a ride that's closed
        wait_time = park.get_wait_time('Liberty Square Riverboat')
        assert wait_time == 0
    
    def test_is_ride_open(self, magic_kingdom_data):
        """Test checking if a ride is open"""
        park = ThemePark(magic_kingdom_data, "Disney Magic Kingdom")
        assert park.is_ride_open('Haunted Mansion') is True
        assert park.is_ride_open('Liberty Square Riverboat') is False
    
    def test_get_ride_sequence(self, magic_kingdom_data):
        """Test getting rides in sequence"""
        park = ThemePark(magic_kingdom_data, "Disney Magic Kingdom", 6)
        # First ride should be "A Pirate's Adventure"
        assert park.get_current_ride_name() == "A Pirate's Adventure ~ Treasures of the Seven Seas"
        # Next ride should be "Jungle Cruise"
        assert park.get_next_ride_name() == "Jungle Cruise"
        # Current ride wait time should be 5 minutes
        assert park.get_current_ride_time() == 5
    
    def test_closed_park(self, closed_park_data):
        """Test a park that is closed"""
        park = ThemePark(closed_park_data, "Tokyo Disneyland", 274)
        assert park.is_open is False
        assert len(park.rides) > 10