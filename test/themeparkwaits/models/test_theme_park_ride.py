"""
Tests for the ThemeParkRide model class.
"""
import pytest
from src.models.theme_park_ride import ThemeParkRide


class TestThemeParkRide:
    def test_initialization(self):
        """Test initialization with parameters"""
        ride = ThemeParkRide("Space Mountain", 138, 10, True)
        assert ride.name == "Space Mountain"
        assert ride.id == 138
        assert ride.wait_time == 10
        assert ride.open_flag is True

    def test_is_open_true(self):
        """Test is_open returns True when open and has wait time"""
        ride = ThemeParkRide("Space Mountain", 138, 10, True)
        assert ride.is_open() is True

    def test_is_open_false_with_zero_wait(self):
        """Test is_open returns False when open but zero wait time"""
        ride = ThemeParkRide("Space Mountain", 138, 0, True)
        assert ride.is_open() is False

    def test_is_open_false_when_closed(self):
        """Test is_open returns False when closed"""
        ride = ThemeParkRide("Space Mountain", 138, 10, False)
        assert ride.is_open() is False

    def test_is_open_false_when_closed_and_zero_wait(self):
        """Test is_open returns False when closed and zero wait time"""
        ride = ThemeParkRide("Space Mountain", 138, 0, False)
        assert ride.is_open() is False