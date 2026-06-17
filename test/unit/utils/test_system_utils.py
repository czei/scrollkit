"""
Unit tests for system utilities.
Copyright 2024 3DUPFitters LLC
"""
import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import sys
import socket
import time
from datetime import datetime


class TestSystemUtils(unittest.TestCase):
    """Test cases for system utilities"""
    
    def setUp(self):
        """Set up test fixtures"""
        # Mock only the hardware modules, not the NTP module
        self.mock_rtc = MagicMock()
        self.mock_microcontroller = MagicMock()
        
        # Create mock RTC class
        self.mock_rtc_instance = MagicMock()
        self.mock_rtc.RTC.return_value = self.mock_rtc_instance
        
        # Patch modules before import
        sys.modules['rtc'] = self.mock_rtc
        sys.modules['microcontroller'] = self.mock_microcontroller
        
    def tearDown(self):
        """Clean up after tests"""
        # Remove mocked modules
        for module in ['rtc', 'microcontroller']:
            if module in sys.modules:
                del sys.modules[module]
                
    @patch('src.utils.system_utils.HAS_NTP', True)
    @patch('src.utils.system_utils.HAS_HARDWARE', True)
    @patch('scrollkit.utils.error_handler.ErrorHandler')
    async def test_set_system_clock_ntp_with_live_server(self, mock_error_handler):
        """Test NTP time synchronization with real NTP server"""
        # Import adafruit_ntp if available, otherwise skip test
        try:
            import adafruit_ntp
        except ImportError:
            self.skipTest("adafruit_ntp module not available")
            
        # Import after mocking hardware
        from src.utils.system_utils import set_system_clock_ntp
        
        # Mock logger
        mock_logger = MagicMock()
        mock_error_handler.return_value = mock_logger
        
        # Create a real socket pool for NTP
        # This simulates what would be available on CircuitPython hardware
        class MockSocketPool:
            # Socket constants needed by adafruit_ntp
            AF_INET = socket.AF_INET
            SOCK_DGRAM = socket.SOCK_DGRAM
            IPPROTO_UDP = socket.IPPROTO_UDP
            
            def getaddrinfo(self, host, port, *args, **kwargs):
                """Minimal getaddrinfo implementation for NTP"""
                return socket.getaddrinfo(host, port, *args, **kwargs)
                
            def socket(self, *args, **kwargs):
                """Create a real socket"""
                return socket.socket(*args, **kwargs)
        
        mock_socket_pool = MockSocketPool()
        
        # Test with default timezone
        result = await set_system_clock_ntp(mock_socket_pool)
        
        # Assertions
        self.assertTrue(result)
        
        # Verify RTC was set with a reasonable time
        # The datetime is set via assignment, so we need to check the mock call
        self.assertTrue(hasattr(self.mock_rtc_instance, 'datetime'))
        
        # Get the call arguments
        # Since it's a property assignment, we need to check differently
        # The mock will have recorded the assignment
        calls = [str(call) for call in mock_logger.info.call_args_list]
        datetime_set_call = None
        for call in calls:
            if "System clock set to" in call:
                # Extract the datetime tuple from the log message
                import re
                match = re.search(r'System clock set to \(([\d, -]+)\)', call)
                if match:
                    datetime_str = match.group(1)
                    datetime_parts = [int(x.strip()) for x in datetime_str.split(',')]
                    datetime_set_call = tuple(datetime_parts)
                    break
        
        self.assertIsNotNone(datetime_set_call)
        self.assertEqual(len(datetime_set_call), 9)
        
        # Verify year is reasonable (between 2020 and 2030)
        year = datetime_set_call[0]
        self.assertGreaterEqual(year, 2020)
        self.assertLessEqual(year, 2030)
        
        # Verify month (1-12)
        month = datetime_set_call[1]
        self.assertGreaterEqual(month, 1)
        self.assertLessEqual(month, 12)
        
        # Verify day (1-31)
        day = datetime_set_call[2]
        self.assertGreaterEqual(day, 1)
        self.assertLessEqual(day, 31)
        
        # Verify hour (0-23)
        hour = datetime_set_call[3]
        self.assertGreaterEqual(hour, 0)
        self.assertLessEqual(hour, 23)
        
        # Verify logging
        mock_logger.info.assert_any_call("Creating NTP client with server pool.ntp.org and tz_offset -5")
        mock_logger.info.assert_any_call("Getting time from NTP server")
        # Check that system clock was set
        info_calls = [call[0][0] for call in mock_logger.info.call_args_list]
        self.assertTrue(any("System clock set to" in str(call) for call in info_calls))
        
    @patch('src.utils.system_utils.HAS_NTP', True)
    @patch('src.utils.system_utils.HAS_HARDWARE', True)
    @patch('scrollkit.utils.error_handler.ErrorHandler')
    async def test_set_system_clock_ntp_different_servers(self, mock_error_handler):
        """Test NTP with different NTP servers"""
        try:
            import adafruit_ntp
        except ImportError:
            self.skipTest("adafruit_ntp module not available")
            
        from src.utils.system_utils import set_system_clock_ntp
        
        mock_logger = MagicMock()
        mock_error_handler.return_value = mock_logger
        
        class MockSocketPool:
            # Socket constants needed by adafruit_ntp
            AF_INET = socket.AF_INET
            SOCK_DGRAM = socket.SOCK_DGRAM
            IPPROTO_UDP = socket.IPPROTO_UDP
            
            def getaddrinfo(self, host, port, *args, **kwargs):
                return socket.getaddrinfo(host, port, *args, **kwargs)
                
            def socket(self, *args, **kwargs):
                return socket.socket(*args, **kwargs)
        
        mock_socket_pool = MockSocketPool()
        
        # Test with different timezone offsets
        for tz_offset in [-8, -5, 0, 8]:
            # Reset mocks
            self.mock_rtc_instance.reset_mock()
            mock_logger.reset_mock()
            
            result = await set_system_clock_ntp(mock_socket_pool, tz_offset=tz_offset)
            
            self.assertTrue(result, f"Failed with timezone offset {tz_offset}")
            
            # Verify RTC was set
            self.assertIsNotNone(self.mock_rtc_instance.datetime)
            
            # Verify logging shows correct timezone
            mock_logger.info.assert_any_call(f"Creating NTP client with server pool.ntp.org and tz_offset {tz_offset}")
            
    @patch('src.utils.system_utils.HAS_NTP', False)
    @patch('src.utils.system_utils.HAS_HARDWARE', True)
    @patch('scrollkit.utils.error_handler.ErrorHandler')
    async def test_set_system_clock_ntp_no_ntp_module(self, mock_error_handler):
        """Test when NTP module is not available"""
        from src.utils.system_utils import set_system_clock_ntp
        
        mock_logger = MagicMock()
        mock_error_handler.return_value = mock_logger
        
        mock_socket_pool = MagicMock()
        
        result = await set_system_clock_ntp(mock_socket_pool)
        
        self.assertFalse(result)
        mock_logger.info.assert_called_once_with("NTP module not available or hardware not supported")
        
    @patch('src.utils.system_utils.HAS_NTP', True)
    @patch('src.utils.system_utils.HAS_HARDWARE', False)
    @patch('scrollkit.utils.error_handler.ErrorHandler')
    async def test_set_system_clock_ntp_no_hardware(self, mock_error_handler):
        """Test when hardware is not available"""
        from src.utils.system_utils import set_system_clock_ntp
        
        mock_logger = MagicMock()
        mock_error_handler.return_value = mock_logger
        
        mock_socket_pool = MagicMock()
        
        result = await set_system_clock_ntp(mock_socket_pool)
        
        self.assertFalse(result)
        mock_logger.info.assert_called_once_with("NTP module not available or hardware not supported")
        
    @patch('src.utils.system_utils.HAS_NTP', True)
    @patch('src.utils.system_utils.HAS_HARDWARE', True)
    @patch('scrollkit.utils.error_handler.ErrorHandler')
    async def test_set_system_clock_ntp_invalid_socket_pool(self, mock_error_handler):
        """Test with invalid socket pool"""
        from src.utils.system_utils import set_system_clock_ntp
        
        mock_logger = MagicMock()
        mock_error_handler.return_value = mock_logger
        
        # Test with None socket pool
        result = await set_system_clock_ntp(None)
        
        self.assertFalse(result)
        mock_logger.error.assert_called_once_with(
            None, 
            "Invalid socket pool provided for NTP, socket pool must have getaddrinfo"
        )
        
    @patch('src.utils.system_utils.HAS_NTP', True)
    @patch('src.utils.system_utils.HAS_HARDWARE', True)
    @patch('scrollkit.utils.error_handler.ErrorHandler')
    async def test_set_system_clock_ntp_no_getaddrinfo(self, mock_error_handler):
        """Test with socket pool missing getaddrinfo"""
        from src.utils.system_utils import set_system_clock_ntp
        
        mock_logger = MagicMock()
        mock_error_handler.return_value = mock_logger
        
        # Socket pool without getaddrinfo
        mock_socket_pool = MagicMock()
        del mock_socket_pool.getaddrinfo
        
        result = await set_system_clock_ntp(mock_socket_pool)
        
        self.assertFalse(result)
        mock_logger.error.assert_called_once_with(
            None, 
            "Invalid socket pool provided for NTP, socket pool must have getaddrinfo"
        )
        
    @patch('src.utils.system_utils.HAS_NTP', True)
    @patch('src.utils.system_utils.HAS_HARDWARE', True)
    @patch('scrollkit.utils.error_handler.ErrorHandler')
    async def test_set_system_clock_ntp_network_timeout(self, mock_error_handler):
        """Test NTP with network issues (unreachable server)"""
        try:
            import adafruit_ntp
        except ImportError:
            self.skipTest("adafruit_ntp module not available")
            
        from src.utils.system_utils import set_system_clock_ntp
        
        mock_logger = MagicMock()
        mock_error_handler.return_value = mock_logger
        
        # Create socket pool that will fail to connect
        class FailingSocketPool:
            def getaddrinfo(self, host, port, *args, **kwargs):
                # Simulate DNS resolution working but connection failing
                return [(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP, '', ('0.0.0.0', 123))]
                
            def socket(self, *args, **kwargs):
                # Return a socket that will timeout
                sock = socket.socket(*args, **kwargs)
                sock.settimeout(0.1)  # Very short timeout to simulate failure
                return sock
        
        mock_socket_pool = FailingSocketPool()
        
        # Temporarily patch the NTP server to use an invalid address
        with patch('adafruit_ntp.NTP') as mock_ntp_class:
            mock_ntp_class.side_effect = Exception("Network timeout")
            
            result = await set_system_clock_ntp(mock_socket_pool)
            
            self.assertFalse(result)
            mock_logger.error.assert_called_once()
            error_call = mock_logger.error.call_args
            self.assertIsInstance(error_call[0][0], Exception)
            self.assertEqual(error_call[0][1], "Error setting time via NTP")
        

def run_async_test(coro):
    """Helper to run async tests"""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


# Convert async test methods to sync for unittest
for attr_name in dir(TestSystemUtils):
    attr = getattr(TestSystemUtils, attr_name)
    if asyncio.iscoroutinefunction(attr) and attr_name.startswith('test_'):
        wrapped = lambda self, coro=attr: run_async_test(coro(self))
        wrapped.__name__ = attr_name
        setattr(TestSystemUtils, attr_name, wrapped)


if __name__ == '__main__':
    unittest.main()