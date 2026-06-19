"""
Unit tests for system utilities (NTP time setting with multi-server failover).
Copyright 2024 3DUPFitters LLC

These deliberately do NOT hit a real NTP server. A single live NTP query is
exactly the unreliable thing the library now guards against (dead/slow pool
members, and networks that block UDP/123 entirely), so we mock the NTP client
and assert the *resilience*: failover to the next server, and an honest False
when every server is unreachable.
"""
import unittest
from unittest.mock import MagicMock, patch
import asyncio
import sys
import time


class TestSystemUtils(unittest.TestCase):
    """Test cases for system utilities"""

    def setUp(self):
        """Set up test fixtures"""
        # Mock only the hardware modules, not the NTP module
        self.mock_rtc = MagicMock()
        self.mock_microcontroller = MagicMock()

        self.mock_rtc_instance = MagicMock()
        self.mock_rtc.RTC.return_value = self.mock_rtc_instance

        sys.modules['rtc'] = self.mock_rtc
        sys.modules['microcontroller'] = self.mock_microcontroller

    def tearDown(self):
        """Clean up after tests"""
        for module in ['rtc', 'microcontroller']:
            if module in sys.modules:
                del sys.modules[module]

    @patch('scrollkit.utils.system_utils.HAS_NTP', True)
    @patch('scrollkit.utils.system_utils.HAS_HARDWARE', True)
    @patch('scrollkit.utils.error_handler.ErrorHandler')
    async def test_ntp_fails_over_to_next_server(self, mock_error_handler):
        """First server times out; failover to the next server succeeds.

        This is the field-failure mode (a dead/blocked NTP server). The library
        must survive it instead of giving up on the first bad server.
        """
        try:
            import adafruit_ntp  # noqa: F401
        except ImportError:
            self.skipTest("adafruit_ntp module not available")
        from scrollkit.utils.system_utils import set_system_clock_ntp

        mock_logger = MagicMock()
        mock_error_handler.return_value = mock_logger
        pool = MagicMock()  # MagicMock has getaddrinfo via auto-attribute

        good_time = time.struct_time((2025, 6, 15, 12, 30, 0, 6, 166, -1))
        good_ntp = MagicMock()
        good_ntp.datetime = good_time

        attempts = []

        def ntp_factory(socketpool, server=None, **kwargs):
            attempts.append(server)
            if len(attempts) == 1:
                raise OSError("ETIMEDOUT")   # first server times out
            return good_ntp                  # next server responds

        with patch('adafruit_ntp.NTP', side_effect=ntp_factory):
            result = await set_system_clock_ntp(pool)

        self.assertTrue(result)
        self.assertEqual(len(attempts), 2)                  # failed over once
        self.assertEqual(attempts[0], "time.cloudflare.com")
        self.assertEqual(attempts[1], "time.google.com")
        info = " ".join(str(c) for c in mock_logger.info.call_args_list)
        self.assertIn("System clock set to", info)

    @patch('scrollkit.utils.system_utils.HAS_NTP', True)
    @patch('scrollkit.utils.system_utils.HAS_HARDWARE', True)
    @patch('scrollkit.utils.error_handler.ErrorHandler')
    async def test_ntp_returns_false_when_all_servers_fail(self, mock_error_handler):
        """Every server fails (e.g. UDP/123 blocked) -> tries them all, returns
        False. set_system_clock() then falls back to an HTTP time source."""
        try:
            import adafruit_ntp  # noqa: F401
        except ImportError:
            self.skipTest("adafruit_ntp module not available")
        from scrollkit.utils.system_utils import (
            set_system_clock_ntp, DEFAULT_NTP_SERVERS)

        mock_logger = MagicMock()
        mock_error_handler.return_value = mock_logger
        pool = MagicMock()

        attempts = []

        def ntp_factory(socketpool, server=None, **kwargs):
            attempts.append(server)
            raise OSError("ETIMEDOUT")

        with patch('adafruit_ntp.NTP', side_effect=ntp_factory):
            result = await set_system_clock_ntp(pool)

        self.assertFalse(result)
        self.assertEqual(len(attempts), len(DEFAULT_NTP_SERVERS))  # tried every one
        self.assertTrue(mock_logger.error.called)

    @patch('scrollkit.utils.system_utils.HAS_NTP', True)
    @patch('scrollkit.utils.system_utils.HAS_HARDWARE', True)
    @patch('scrollkit.utils.error_handler.ErrorHandler')
    async def test_ntp_respects_custom_server_list(self, mock_error_handler):
        """A caller-supplied server list is used in order."""
        try:
            import adafruit_ntp  # noqa: F401
        except ImportError:
            self.skipTest("adafruit_ntp module not available")
        from scrollkit.utils.system_utils import set_system_clock_ntp

        mock_logger = MagicMock()
        mock_error_handler.return_value = mock_logger
        pool = MagicMock()

        good_ntp = MagicMock()
        good_ntp.datetime = time.struct_time((2025, 1, 1, 0, 0, 0, 2, 1, -1))
        attempts = []

        def ntp_factory(socketpool, server=None, **kwargs):
            attempts.append(server)
            return good_ntp

        with patch('adafruit_ntp.NTP', side_effect=ntp_factory):
            result = await set_system_clock_ntp(pool, servers=["my.ntp.example"])

        self.assertTrue(result)
        self.assertEqual(attempts, ["my.ntp.example"])

    @patch('scrollkit.utils.system_utils.HAS_NTP', False)
    @patch('scrollkit.utils.system_utils.HAS_HARDWARE', True)
    @patch('scrollkit.utils.error_handler.ErrorHandler')
    async def test_set_system_clock_ntp_no_ntp_module(self, mock_error_handler):
        """Returns False when the NTP module isn't available."""
        from scrollkit.utils.system_utils import set_system_clock_ntp
        mock_logger = MagicMock()
        mock_error_handler.return_value = mock_logger

        result = await set_system_clock_ntp(MagicMock())

        self.assertFalse(result)
        mock_logger.info.assert_called_once_with(
            "NTP module not available or hardware not supported")

    @patch('scrollkit.utils.system_utils.HAS_NTP', True)
    @patch('scrollkit.utils.system_utils.HAS_HARDWARE', False)
    @patch('scrollkit.utils.error_handler.ErrorHandler')
    async def test_set_system_clock_ntp_no_hardware(self, mock_error_handler):
        """Returns False when hardware (rtc) isn't available."""
        from scrollkit.utils.system_utils import set_system_clock_ntp
        mock_logger = MagicMock()
        mock_error_handler.return_value = mock_logger

        result = await set_system_clock_ntp(MagicMock())

        self.assertFalse(result)
        mock_logger.info.assert_called_once_with(
            "NTP module not available or hardware not supported")

    @patch('scrollkit.utils.system_utils.HAS_NTP', True)
    @patch('scrollkit.utils.system_utils.HAS_HARDWARE', True)
    @patch('scrollkit.utils.error_handler.ErrorHandler')
    async def test_set_system_clock_ntp_invalid_socket_pool(self, mock_error_handler):
        """Returns False (with a clear error) for a None socket pool."""
        from scrollkit.utils.system_utils import set_system_clock_ntp
        mock_logger = MagicMock()
        mock_error_handler.return_value = mock_logger

        result = await set_system_clock_ntp(None)

        self.assertFalse(result)
        mock_logger.error.assert_called_once_with(
            None,
            "Invalid socket pool provided for NTP, socket pool must have getaddrinfo")

    @patch('scrollkit.utils.system_utils.HAS_NTP', True)
    @patch('scrollkit.utils.system_utils.HAS_HARDWARE', True)
    @patch('scrollkit.utils.error_handler.ErrorHandler')
    async def test_set_system_clock_ntp_no_getaddrinfo(self, mock_error_handler):
        """Returns False for a socket pool missing getaddrinfo."""
        from scrollkit.utils.system_utils import set_system_clock_ntp
        mock_logger = MagicMock()
        mock_error_handler.return_value = mock_logger

        mock_socket_pool = MagicMock()
        del mock_socket_pool.getaddrinfo

        result = await set_system_clock_ntp(mock_socket_pool)

        self.assertFalse(result)
        mock_logger.error.assert_called_once_with(
            None,
            "Invalid socket pool provided for NTP, socket pool must have getaddrinfo")

    def test_parse_http_date(self):
        """The RFC-1123 Date-header parser handles real and malformed input."""
        from scrollkit.utils.system_utils import _parse_http_date
        self.assertEqual(_parse_http_date("Wed, 21 Oct 2025 07:28:00 GMT"),
                         (2025, 10, 21, 7, 28, 0))
        self.assertIsNone(_parse_http_date("garbage"))
        self.assertIsNone(_parse_http_date("Wed, 21 Zzz 2025 07:28:00 GMT"))

    @patch('scrollkit.utils.system_utils.HAS_HARDWARE', True)
    @patch('scrollkit.utils.error_handler.ErrorHandler')
    async def test_falls_back_to_http_date_when_ntp_unavailable(self, mock_error_handler):
        """No socket pool (NTP path skipped, as when UDP/123 is blocked) -> set
        the clock from the HTTP Date header. The key field-survival case."""
        from scrollkit.utils.system_utils import set_system_clock
        mock_error_handler.return_value = MagicMock()

        class _Resp:
            headers = {"Date": "Wed, 21 Oct 2025 07:28:00 GMT"}

        class _Http:
            async def get(self, url):
                return _Resp()

        result = await set_system_clock(_Http(), socket_pool=None, tz_offset=-5)
        self.assertIsNotNone(result)
        self.assertEqual(result[0], 2025)   # year from the Date header
        self.assertEqual(result[1], 10)     # month

    @patch('scrollkit.utils.system_utils.HAS_HARDWARE', True)
    @patch('scrollkit.utils.error_handler.ErrorHandler')
    async def test_set_system_clock_returns_none_when_all_sources_fail(self, mock_error_handler):
        """No NTP and no usable HTTP Date header -> None (honest failure, logged)."""
        from scrollkit.utils.system_utils import set_system_clock
        mock_error_handler.return_value = MagicMock()

        class _Resp:
            headers = {}      # no Date header

        class _Http:
            async def get(self, url):
                return _Resp()

        result = await set_system_clock(_Http(), socket_pool=None)
        self.assertIsNone(result)


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
