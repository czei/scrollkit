"""
Tests for the MessageQueue sorting functionality.
"""
import pytest
from unittest.mock import MagicMock, AsyncMock
from src.ui.message_queue import MessageQueue
from src.models.theme_park_ride import ThemeParkRide
from src.models.theme_park import ThemePark


class TestMessageQueueSorting:
    """Test the sorting functionality in MessageQueue"""
    
    def setup_method(self):
        """Set up test fixtures"""
        # Create mock display
        self.mock_display = MagicMock()
        self.mock_display.show_scroll_message = AsyncMock()
        self.mock_display.show_ride_wait_time = AsyncMock()
        self.mock_display.show_ride_closed = AsyncMock()
        self.mock_display.show_ride_name = AsyncMock()
        
        # Create mock settings manager
        self.mock_settings_manager = MagicMock()
        self.mock_display.settings_manager = self.mock_settings_manager
        
        # Create message queue
        self.message_queue = MessageQueue(self.mock_display, delay_param=0)
        
        # Create test rides
        self.rides = [
            ThemeParkRide("Space Mountain", 1, 60, True),
            ThemeParkRide("Big Thunder Mountain", 2, 30, True),
            ThemeParkRide("Pirates of the Caribbean", 3, 15, True),
            ThemeParkRide("Haunted Mansion", 4, 45, True),
            ThemeParkRide("Matterhorn", 5, 0, False),  # Closed ride
            ThemeParkRide("Meet Mickey", 6, 20, True),  # Meet & greet
        ]
        
        # Create test park using MagicMock
        self.park = MagicMock(spec=ThemePark)
        self.park.id = 1
        self.park.name = "Test Park"
        self.park.rides = self.rides
        self.park.is_open = True
    
    def test_sort_rides_alphabetical(self):
        """Test alphabetical sorting"""
        rides_with_parks = [(ride, self.park) for ride in self.rides]
        sorted_rides = self.message_queue._sort_rides(rides_with_parks, "alphabetical")
        
        # Extract ride names
        sorted_names = [ride[0].name for ride in sorted_rides]
        expected_names = [
            "Big Thunder Mountain",
            "Haunted Mansion", 
            "Matterhorn",
            "Meet Mickey",
            "Pirates of the Caribbean",
            "Space Mountain"
        ]
        assert sorted_names == expected_names
    
    def test_sort_rides_max_wait(self):
        """Test sorting by longest wait time first"""
        rides_with_parks = [(ride, self.park) for ride in self.rides]
        sorted_rides = self.message_queue._sort_rides(rides_with_parks, "max_wait")
        
        # Extract wait times (closed rides should be 0)
        wait_times = [ride[0].wait_time if ride[0].is_open() else 0 for ride in sorted_rides]
        expected_times = [60, 45, 30, 20, 15, 0]  # Descending order
        assert wait_times == expected_times
    
    def test_sort_rides_min_wait(self):
        """Test sorting by shortest wait time first"""
        rides_with_parks = [(ride, self.park) for ride in self.rides]
        sorted_rides = self.message_queue._sort_rides(rides_with_parks, "min_wait")
        
        # Extract wait times (closed rides should be 0)
        wait_times = [ride[0].wait_time if ride[0].is_open() else 0 for ride in sorted_rides]
        expected_times = [0, 15, 20, 30, 45, 60]  # Ascending order
        assert wait_times == expected_times
    
    def test_sort_rides_unknown_mode(self):
        """Test that unknown sort mode defaults to alphabetical"""
        rides_with_parks = [(ride, self.park) for ride in self.rides]
        sorted_rides = self.message_queue._sort_rides(rides_with_parks, "invalid_mode")
        
        # Should default to alphabetical
        sorted_names = [ride[0].name for ride in sorted_rides]
        assert sorted_names[0] == "Big Thunder Mountain"
        assert sorted_names[-1] == "Space Mountain"
    
    @pytest.mark.asyncio
    async def test_add_rides_group_by_park(self):
        """Test add_rides with group_by_park enabled"""
        # Set up multiple parks
        park1 = MagicMock(spec=ThemePark)
        park1.id = 1
        park1.name = "Park 1"
        park1.rides = self.rides[:3]
        park1.is_open = True
        
        park2 = MagicMock(spec=ThemePark)
        park2.id = 2
        park2.name = "Park 2"
        park2.rides = self.rides[3:]
        park2.is_open = True
        
        # Create mock park list
        mock_park_list = MagicMock()
        mock_park_list.selected_parks = [park1, park2]
        mock_park_list.skip_meet = False
        mock_park_list.skip_closed = False
        
        # Configure settings
        self.mock_settings_manager.get.side_effect = lambda key, default=None: {
            "sort_mode": "alphabetical",
            "group_by_park": True
        }.get(key, default)
        
        # Add rides
        await self.message_queue.add_rides(mock_park_list)
        
        # Verify parks are processed separately
        # Each park should have its name announced
        param_queue = self.message_queue.param_queue
        assert "Park 1 wait times..." in param_queue
        assert "Park 2 wait times..." in param_queue
        
        # Find the indices of park announcements
        park1_idx = param_queue.index("Park 1 wait times...")
        park2_idx = param_queue.index("Park 2 wait times...")
        
        # Verify that Park 2 rides come after Park 1 rides
        assert park2_idx > park1_idx
    
    @pytest.mark.asyncio
    async def test_add_rides_combined_sorting(self):
        """Test add_rides with group_by_park disabled (combined sorting)"""
        # Set up multiple parks
        park1 = MagicMock(spec=ThemePark)
        park1.id = 1
        park1.name = "Park 1"
        park1.rides = [self.rides[0], self.rides[2]]  # Space Mountain (60), Pirates (15)
        park1.is_open = True
        
        park2 = MagicMock(spec=ThemePark)
        park2.id = 2
        park2.name = "Park 2"
        park2.rides = [self.rides[1], self.rides[3]]  # Big Thunder (30), Haunted Mansion (45)
        park2.is_open = True
        
        # Create mock park list
        mock_park_list = MagicMock()
        mock_park_list.selected_parks = [park1, park2]
        mock_park_list.skip_meet = False
        mock_park_list.skip_closed = False
        
        # Configure settings for max wait sorting without grouping
        self.mock_settings_manager.get.side_effect = lambda key, default=None: {
            "sort_mode": "max_wait",
            "group_by_park": False
        }.get(key, default)
        
        # Add rides
        await self.message_queue.add_rides(mock_park_list)
        
        # Extract ride names from the queue
        ride_names = []
        for i, func in enumerate(self.message_queue.func_queue):
            if func == self.mock_display.show_ride_name:
                ride_names.append(self.message_queue.param_queue[i])
        
        # Should be sorted by wait time descending across all parks
        expected_order = ["Space Mountain", "Haunted Mansion", "Big Thunder Mountain", "Pirates of the Caribbean"]
        assert ride_names == expected_order
    
    @pytest.mark.asyncio
    async def test_add_rides_with_filters(self):
        """Test that filtering works with sorting"""
        # Create mock park list
        mock_park_list = MagicMock()
        mock_park_list.selected_parks = [self.park]
        mock_park_list.skip_meet = True  # Skip meet & greets
        mock_park_list.skip_closed = True  # Skip closed rides
        
        # Configure settings
        self.mock_settings_manager.get.side_effect = lambda key, default=None: {
            "sort_mode": "alphabetical",
            "group_by_park": False
        }.get(key, default)
        
        # Add rides
        await self.message_queue.add_rides(mock_park_list)
        
        # Extract ride names from the queue
        ride_names = []
        for i, func in enumerate(self.message_queue.func_queue):
            if func == self.mock_display.show_ride_name:
                ride_names.append(self.message_queue.param_queue[i])
        
        # Should not include "Meet Mickey" or "Matterhorn" (closed)
        assert "Meet Mickey" not in ride_names
        assert "Matterhorn" not in ride_names
        
        # Should be alphabetically sorted
        expected_order = ["Big Thunder Mountain", "Haunted Mansion", "Pirates of the Caribbean", "Space Mountain"]
        assert ride_names == expected_order