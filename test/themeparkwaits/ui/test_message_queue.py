"""
Tests for the MessageQueue class.
"""
import asyncio
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.ui.message_queue import MessageQueue, REQUIRED_MESSAGE
from src.models.vacation import Vacation
from src.models.theme_park_list import ThemeParkList
from src.models.theme_park import ThemePark

class TestMessageQueue:
    def test_initialization(self):
        """Test that the message queue initializes correctly"""
        # Create a mock display
        mock_display = MagicMock()
        
        # Initialize message queue with default parameters
        mq = MessageQueue(mock_display)
        
        # Verify init state
        assert mq.display == mock_display
        assert mq.delay == 4  # Default delay
        assert mq.regenerate_flag is False  # Default regenerate flag
        assert mq.func_queue == []
        assert mq.param_queue == []
        assert mq.delay_queue == []
        assert mq.index == 0
        assert mq.has_completed_cycle is False  # Should start as False
        
        # Test custom parameters
        mq = MessageQueue(mock_display, delay_param=2, regen_flag=True)
        assert mq.delay == 2
        assert mq.regenerate_flag is True
    
    def test_init_method(self):
        """Test the init method that resets the queues"""
        # Create a mock display
        mock_display = MagicMock()
        
        # Initialize message queue
        mq = MessageQueue(mock_display)
        
        # Add some items to the queues
        mq.func_queue = [1, 2, 3]
        mq.param_queue = [4, 5, 6]
        mq.delay_queue = [7, 8, 9]
        mq.index = 10
        
        # Call init to reset the queues
        mq.init()
        
        # Verify the queues were reset
        assert mq.func_queue == []
        assert mq.param_queue == []
        assert mq.delay_queue == []
        assert mq.index == 0
    
    @pytest.mark.asyncio
    async def test_add_scroll_message(self):
        """Test adding a scrolling message to the queue"""
        # Create a mock display
        mock_display = MagicMock()
        
        # Initialize message queue
        mq = MessageQueue(mock_display)
        
        # Add a message with default delay
        await mq.add_scroll_message("Test message")
        
        # Verify the message was added to the queues
        assert len(mq.func_queue) == 1
        assert len(mq.param_queue) == 1
        assert len(mq.delay_queue) == 1
        assert mq.func_queue[0] == mock_display.show_scroll_message
        assert mq.param_queue[0] == "Test message"
        assert mq.delay_queue[0] == 2  # Default delay
        
        # Add a message with custom delay
        await mq.add_scroll_message("Another message", delay=5)
        
        # Verify the second message was added
        assert len(mq.func_queue) == 2
        assert len(mq.param_queue) == 2
        assert len(mq.delay_queue) == 2
        assert mq.func_queue[1] == mock_display.show_scroll_message
        assert mq.param_queue[1] == "Another message"
        assert mq.delay_queue[1] == 5  # Custom delay
    
    @pytest.mark.asyncio
    async def test_add_splash(self):
        """Test adding a splash screen to the queue"""
        # Create a mock display
        mock_display = MagicMock()
        
        # Initialize message queue
        mq = MessageQueue(mock_display)
        
        # Mock the logger
        with patch('src.ui.message_queue.logger') as mock_logger:
            # Add a splash screen with default duration
            await mq.add_splash()
            
            # Verify the splash was added to the queues
            assert len(mq.func_queue) == 1
            assert len(mq.param_queue) == 1
            assert len(mq.delay_queue) == 1
            assert mq.func_queue[0] == mock_display.show_splash
            assert mq.param_queue[0] == (10, False)  # Default duration and reveal_style
            assert mq.delay_queue[0] == 0  # No additional delay
            
            # Verify the log message
            mock_logger.debug.assert_called_once_with("Adding splash message to queue with duration=10, reveal_style=False")
            
            # Add a splash screen with custom duration
            await mq.add_splash(duration=2)
            
            # Verify the second splash was added
            assert len(mq.func_queue) == 2
            assert len(mq.param_queue) == 2
            assert len(mq.delay_queue) == 2
            assert mq.func_queue[1] == mock_display.show_splash
            assert mq.param_queue[1] == (2, False)  # Custom duration with default reveal_style
            assert mq.delay_queue[1] == 0  # No additional delay
    
    @pytest.mark.asyncio
    async def test_add_vacation(self):
        """Test adding vacation information to the queue"""
        # Create a mock display
        mock_display = MagicMock()
        
        # Initialize message queue
        mq = MessageQueue(mock_display)
        
        # Create a mock vacation with specific days_until values
        mock_vacation = MagicMock(spec=Vacation)
        mock_vacation.name = "Test Vacation"
        
        # Test unset vacation (should do nothing)
        mock_vacation.is_set.return_value = False
        await mq.add_vacation(mock_vacation)
        assert len(mq.func_queue) == 0  # Nothing should be added
        
        # Test many days until vacation
        mock_vacation.is_set.return_value = True
        mock_vacation.get_days_until.return_value = 10
        with patch.object(mq, 'add_scroll_message', new_callable=AsyncMock) as mock_add_scroll:
            await mq.add_vacation(mock_vacation)
            mock_add_scroll.assert_called_once_with("Vacation to Test Vacation in: 10 days", 0)
        
        # Test one day until vacation
        mock_vacation.get_days_until.return_value = 1
        with patch.object(mq, 'add_scroll_message', new_callable=AsyncMock) as mock_add_scroll:
            await mq.add_vacation(mock_vacation)
            mock_add_scroll.assert_called_once_with("Your vacation to Test Vacation is tomorrow!!!", 0)
        
        # Test vacation is today
        mock_vacation.get_days_until.return_value = 0
        with patch.object(mq, 'add_scroll_message', new_callable=AsyncMock) as mock_add_scroll:
            await mq.add_vacation(mock_vacation)
            mock_add_scroll.assert_called_once_with("Your vacation to Test Vacation is TODAY!!!!!!!!!!!!!", 0)
    
    @pytest.mark.asyncio
    async def test_add_required_message(self):
        """Test adding the required attribution message to the queue"""
        # Create a mock display
        mock_display = MagicMock()
        
        # Initialize message queue
        mq = MessageQueue(mock_display, delay_param=3)
        
        # Add the required message
        await mq.add_required_message("Test Park")
        
        # Verify the message was added to the queues
        assert len(mq.func_queue) == 1
        assert len(mq.param_queue) == 1
        assert len(mq.delay_queue) == 1
        assert mq.func_queue[0] == mock_display.show_scroll_message
        assert f"Wait times for Test Park provided by {REQUIRED_MESSAGE}" in mq.param_queue[0]
        assert mq.delay_queue[0] == 3  # Queue delay
    
    @pytest.mark.asyncio
    async def test_add_rides_closed_park(self):
        """Test adding ride information for a closed park"""
        # Create a mock display
        mock_display = MagicMock()
        
        # Initialize message queue
        mq = MessageQueue(mock_display)
        
        # Create a mock park that is closed
        mock_park = MagicMock(spec=ThemePark)
        mock_park.name = "Closed Park"
        mock_park.id = 1
        mock_park.is_open = False
        
        # Create a mock park list with the closed park
        mock_park_list = MagicMock(spec=ThemeParkList)
        mock_park_list.current_park = mock_park
        
        # Mock the logger
        with patch('src.ui.message_queue.logger') as mock_logger:
            # Add rides for the closed park
            await mq.add_rides(mock_park_list)
            
            # Verify the debug log - check that the expected call was made
            debug_calls = [call[0][0] for call in mock_logger.debug.call_args_list]
            assert "MessageQueue.add_rides() called for single park: Closed Park:1" in debug_calls
            
            # Verify a closed message was added to the queue
            assert len(mq.func_queue) == 1
            assert len(mq.param_queue) == 1
            assert len(mq.delay_queue) == 1
            assert mq.func_queue[0] == mock_display.show_scroll_message
            assert mq.param_queue[0] == "Closed Park is closed"
            assert mq.delay_queue[0] == 4  # Default delay
    
    @pytest.mark.asyncio
    async def test_add_rides_open_park(self):
        """Test adding ride information for an open park"""
        # Create a mock display
        mock_display = MagicMock()
        
        # Create mock settings manager that returns default sort settings
        mock_settings_manager = MagicMock()
        mock_settings_manager.get.side_effect = lambda key, default=None: default
        mock_display.settings_manager = mock_settings_manager
        
        # Initialize message queue
        mq = MessageQueue(mock_display)
        
        # Create mock rides
        mock_ride1 = MagicMock()
        mock_ride1.name = "Open Ride"
        mock_ride1.wait_time = 15
        mock_ride1.open_flag = True
        mock_ride1.is_open.return_value = True
        
        mock_ride2 = MagicMock()
        mock_ride2.name = "Closed Ride"
        mock_ride2.wait_time = 0
        mock_ride2.open_flag = False
        mock_ride2.is_open.return_value = False
        
        mock_ride3 = MagicMock()
        mock_ride3.name = "Meet Mickey Mouse"
        mock_ride3.wait_time = 30
        mock_ride3.open_flag = True
        mock_ride3.is_open.return_value = True
        
        # Create a mock park that is open
        mock_park = MagicMock(spec=ThemePark)
        mock_park.name = "Test Park"
        mock_park.id = 1
        mock_park.is_open = True
        mock_park.rides = [mock_ride1, mock_ride2, mock_ride3]
        
        # Create a mock park list with the open park
        mock_park_list = MagicMock(spec=ThemeParkList)
        mock_park_list.current_park = mock_park
        mock_park_list.skip_closed = False  # Show closed rides
        mock_park_list.skip_meet = False    # Show meet & greets
        
        # Mock asyncio.sleep to avoid waiting
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Add rides for the open park
            await mq.add_rides(mock_park_list)
            
            # With group_by_park=False (default), park name is NOT shown
            # With alphabetical sorting: "Closed Ride", "Meet Mickey Mouse", "Open Ride"
            
            # For closed ride: should add closed message and name
            assert mq.func_queue[0] == mock_display.show_ride_closed
            assert mq.param_queue[0] == "Closed"
            assert mq.func_queue[1] == mock_display.show_ride_name
            assert mq.param_queue[1] == "Closed Ride"
            
            # For meet & greet: should add wait time and name
            assert mq.func_queue[2] == mock_display.show_ride_wait_time
            assert mq.param_queue[2] == "30"
            assert mq.func_queue[3] == mock_display.show_ride_name
            assert mq.param_queue[3] == "Meet Mickey Mouse"
            
            # For open ride: should add wait time and name
            assert mq.func_queue[4] == mock_display.show_ride_wait_time
            assert mq.param_queue[4] == "15"
            assert mq.func_queue[5] == mock_display.show_ride_name
            assert mq.param_queue[5] == "Open Ride"
            
            # Regenerate flag should be set to false
            assert mq.regenerate_flag is False
    
    @pytest.mark.asyncio
    async def test_add_rides_skip_filters(self):
        """Test adding ride information with skip filters enabled"""
        # Create a mock display
        mock_display = MagicMock()
        
        # Create mock settings manager that returns default sort settings
        mock_settings_manager = MagicMock()
        mock_settings_manager.get.side_effect = lambda key, default=None: default
        mock_display.settings_manager = mock_settings_manager
        
        # Initialize message queue
        mq = MessageQueue(mock_display)
        
        # Create mock rides
        mock_ride1 = MagicMock()
        mock_ride1.name = "Open Ride"
        mock_ride1.wait_time = 15
        mock_ride1.open_flag = True
        mock_ride1.is_open.return_value = True
        
        mock_ride2 = MagicMock()
        mock_ride2.name = "Closed Ride"
        mock_ride2.wait_time = 0
        mock_ride2.open_flag = False
        mock_ride2.is_open.return_value = False
        
        mock_ride3 = MagicMock()
        mock_ride3.name = "Meet Mickey Mouse"
        mock_ride3.wait_time = 30
        mock_ride3.open_flag = True
        mock_ride3.is_open.return_value = True
        
        # Create a mock park that is open
        mock_park = MagicMock(spec=ThemePark)
        mock_park.name = "Test Park"
        mock_park.id = 1
        mock_park.is_open = True
        mock_park.rides = [mock_ride1, mock_ride2, mock_ride3]
        
        # Create a mock park list with the open park
        mock_park_list = MagicMock(spec=ThemeParkList)
        mock_park_list.current_park = mock_park
        mock_park_list.skip_closed = True   # Skip closed rides
        mock_park_list.skip_meet = True     # Skip meet & greets
        
        # Mock asyncio.sleep to avoid waiting
        with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
            # Add rides for the open park
            await mq.add_rides(mock_park_list)
            
            # With group_by_park=False (default), park name is NOT shown
            # For open ride: should add wait time and name
            assert mq.func_queue[0] == mock_display.show_ride_wait_time
            assert mq.param_queue[0] == "15"
            assert mq.func_queue[1] == mock_display.show_ride_name
            assert mq.param_queue[1] == "Open Ride"
            
            # Closed ride and meet & greet should be skipped (only 2 items total in the queue)
            assert len(mq.func_queue) == 2
    
    @pytest.mark.asyncio
    async def test_show(self):
        """Test showing the next message in the queue"""
        # Create a mock display
        mock_display = MagicMock()
        
        # Create mock display functions
        mock_display.show_splash = AsyncMock()
        mock_display.show_scroll_message = AsyncMock()
        
        # Initialize message queue
        mq = MessageQueue(mock_display, delay_param=2)
        
        # Add some items to the queue
        mq.func_queue = [mock_display.show_splash, mock_display.show_scroll_message]
        mq.param_queue = [3, "Test message"]
        mq.delay_queue = [0, 1]
        mq.index = 0
        
        # Mock asyncio.create_task and asyncio.sleep
        with patch('asyncio.create_task', side_effect=lambda x: x) as mock_create_task:
            with patch('asyncio.sleep', new_callable=AsyncMock) as mock_sleep:
                # Show the first message
                await mq.show()
                
                # Verify first function was called
                mock_display.show_splash.assert_called_once_with(3)
                mock_sleep.assert_called_once_with(0)
                assert mq.index == 1
                
                # Reset mocks
                mock_display.show_splash.reset_mock()
                mock_sleep.reset_mock()
                
                # Show the second message
                await mq.show()
                
                # Verify second function was called
                mock_display.show_scroll_message.assert_called_once_with("Test message")
                mock_sleep.assert_called_once_with(1)
                assert mq.index == 0  # Should wrap back to the beginning
                assert mq.has_completed_cycle is True  # Should mark cycle as complete
                
        # Test empty queue
        mq.func_queue = []
        mq.param_queue = []
        mq.delay_queue = []
        
        # Show should do nothing with an empty queue
        with patch('asyncio.create_task') as mock_create_task:
            await mq.show()
            mock_create_task.assert_not_called()