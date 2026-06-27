"""
HTTP client for making API requests.
Supports both adafruit_requests (CircuitPython) and urllib (standard Python).
Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""
import json
import gc
from scrollkit.utils.error_handler import ErrorHandler

# Initialize logger
logger = ErrorHandler("error_log")

class BaseResponse:
    """Base class for all response types with common functionality"""

    def __init__(self, status_code=200, text="", content=None, headers=None):
        self.status_code = status_code
        self.text = text
        self.content = content if content is not None else text.encode('utf-8')
        # Response headers (e.g. for reading the 'Date' header as a time source).
        # The native adafruit_requests response already exposes .headers; these
        # wrappers carry it through so the same code works on desktop and device.
        self.headers = headers if headers is not None else {}
        self._json_cache = None
        self._read_position = 0

    def json(self):
        """Parse the response as JSON"""
        if self._json_cache is None:
            # An HTTP error body isn't JSON we failed to parse \u2014 surface the
            # status straight, rather than mislabeling it a JSON syntax error.
            if getattr(self, 'status_code', 200) >= 400:
                raise ValueError(f"HTTP error {self.status_code}: {self.text}")
            try:
                text_to_parse = self.text.strip()
                if text_to_parse.startswith('\ufeff'):
                    text_to_parse = text_to_parse[1:]
                if not text_to_parse:
                    self._json_cache = {}
                    return self._json_cache
                self._json_cache = json.loads(text_to_parse)
            except (ValueError, AttributeError) as e:
                logger.error(e, f"JSON parse error: {str(e)}")
                raise ValueError(f"syntax error in JSON: {str(e)}")
        return self._json_cache

    def close(self):
        pass

    def read(self, size=-1):
        if size == -1:
            result = self.content[self._read_position:]
            self._read_position = len(self.content)
        else:
            result = self.content[self._read_position:self._read_position + size]
            self._read_position += len(result)
        return result


class UrllibResponse(BaseResponse):
    """Wrapper for urllib responses to match adafruit_requests interface"""

    def __init__(self, urllib_response):
        content = urllib_response.read()
        try:
            text = content.decode('utf-8')
        except UnicodeDecodeError:
            text = ""
        try:
            hdrs = {k: v for k, v in urllib_response.getheaders()}
        except Exception:
            hdrs = {}
        super().__init__(urllib_response.status, text, content, headers=hdrs)


class MockResponse(BaseResponse):
    """Mock response for development mode testing"""


class HttpClient:
    """
    HTTP client supporting both CircuitPython (adafruit_requests) and
    standard Python (urllib). Supports a pluggable mock data provider
    for development without network access.
    """

    def __init__(self, session=None, mock_provider=None, timeout=10):
        """
        Initialize the HTTP client.

        Args:
            session: The underlying session (adafruit_requests.Session or None)
            mock_provider: Optional callable(url) -> MockResponse or None.
                           Called when no session is available and use_live_data is False.
            timeout: Per-request timeout in seconds. ``adafruit_requests`` is
                     synchronous, so without a timeout a hung socket blocks the
                     whole asyncio event loop forever (the display freezes). This
                     bounds connect/read so a flaky network raises instead of
                     wedging. Default 10s; keep it BELOW any hardware watchdog
                     timeout so a slow request doesn't trip a false reboot.
        """
        self.session = session
        self.use_live_data = True
        self.mock_provider = mock_provider
        self.timeout = timeout

        # Platform detection
        try:
            from scrollkit.display.display_factory import is_dev_mode
            dev_mode = is_dev_mode()
        except ImportError:
            dev_mode = False

        if dev_mode:
            self.using_adafruit = False
        else:
            try:
                import adafruit_requests
                self.adafruit_requests = adafruit_requests
                self.using_adafruit = True
            except ImportError:
                self.using_adafruit = False

        try:
            import urllib.request
            from urllib.error import URLError
            self.urllib = urllib.request
            self.URLError = URLError
        except ImportError:
            self.urllib = None
            self.URLError = None

    async def get(self, url, headers=None, max_retries=3):
        """
        Make a GET request with retries.

        Blocking note (CircuitPython): the underlying ``adafruit_requests`` is
        synchronous, so despite the ``await`` this call blocks the asyncio event
        loop until the response arrives — the display scroll pauses for the
        duration. This is not transparently async (spec FR-029). When fetching a
        lot of data, split it into several small requests and ``await
        asyncio.sleep(0)`` between them so the display renders between chunks
        (see the hard demo, ``demos/hard/crypto_dashboard.py``). On desktop the
        urllib path is used instead.

        Returns:
            A Response object (native adafruit_requests, UrllibResponse, or MockResponse)
        """
        if headers is None:
            headers = {"User-Agent": "Mozilla/5.0 (CircuitPython)"}

        retry_count = 0
        last_error = None

        # Check mock data provider
        if not self.session and not self.use_live_data and self.mock_provider:
            mock_resp = self.mock_provider(url)
            if mock_resp is not None:
                return mock_resp

        while retry_count < max_retries:
            try:
                if self.using_adafruit and self.session:
                    return await self._get_adafruit(url, headers, retry_count)
                else:
                    return self._get_urllib(url, headers)
            except Exception as outer_error:
                logger.error(outer_error, f"HTTP GET error (attempt {retry_count+1})")
                last_error = outer_error
                retry_count += 1
                import asyncio as _asyncio
                await _asyncio.sleep(0.5 + retry_count * 0.5)

        error_msg = str(last_error) if last_error else "Unknown error"
        logger.error(None, f"All {max_retries} GET attempts to {url} failed: {error_msg}")
        return MockResponse(status_code=500, text="{}")

    async def _get_adafruit(self, url, headers, retry_count):
        try:
            from adafruit_requests import OutOfRetries
            out_of_retries = OutOfRetries
        except ImportError:
            class OutOfRetries(Exception): pass
            out_of_retries = OutOfRetries

        try:
            resp = self.session.get(url, headers=headers, timeout=self.timeout)
            return resp
        except out_of_retries:
            logger.error(None, f"Socket failures (attempt {retry_count+1})")
            import asyncio as _asyncio
            await _asyncio.sleep(2 * (retry_count + 1))
            try:
                import socketpool
                import wifi
                import ssl
                import adafruit_requests
                pool = socketpool.SocketPool(wifi.radio)
                ssl_context = ssl.create_default_context()
                self.session = adafruit_requests.Session(pool, ssl_context)
                logger.info("Recreated HTTP session after OutOfRetries")
            except Exception:
                pass
            raise

    def _get_urllib(self, url, headers):
        if not self.urllib:
            return MockResponse(status_code=500, text="No HTTP client available")
        request = self.urllib.Request(url)
        for key, value in headers.items():
            request.add_header(key, value)
        with self.urllib.urlopen(request, timeout=self.timeout) as response:
            return UrllibResponse(response)

    async def post(self, url, data, headers=None):
        """Make a POST request."""
        if headers is None:
            headers = {
                "User-Agent": "Mozilla/5.0 (CircuitPython)",
                "Content-Type": "application/json"
            }
        if isinstance(data, dict):
            data = json.dumps(data)
        try:
            if self.using_adafruit and self.session:
                return self.session.post(url, data=data, headers=headers)
            else:
                request = self.urllib.Request(
                    url,
                    data=data.encode('utf-8') if isinstance(data, str) else data,
                    method="POST"
                )
                for key, value in headers.items():
                    request.add_header(key, value)
                with self.urllib.urlopen(request) as response:
                    return UrllibResponse(response)
        except Exception as e:
            logger.error(e, f"Error making POST request to {url}")
            return MockResponse(status_code=500, text=str(e))

    def set_use_live_data(self, use_live_data):
        """Set whether to use live data or mock data."""
        self.use_live_data = use_live_data
        logger.info(f"HTTP client: {'live' if use_live_data else 'mock'} data")

    def get_sync(self, url, headers=None, max_retries=3):
        """Synchronous wrapper for GET requests (CircuitPython compatible)."""
        gc.collect()
        if headers is None:
            headers = {"User-Agent": "Mozilla/5.0 (CircuitPython)"}

        retry_count = 0
        last_error = None

        while retry_count < max_retries:
            try:
                if self.using_adafruit and self.session:
                    gc.collect()
                    resp = None
                    try:
                        logger.debug(f"Sync GET: {url}")
                        resp = self.session.get(url, headers=headers, timeout=self.timeout)
                        return resp
                    except Exception:
                        if resp:
                            try:
                                resp.close()
                            except:
                                pass
                        raise
                elif self.urllib:
                    request = self.urllib.Request(url)
                    for key, value in headers.items():
                        request.add_header(key, value)
                    with self.urllib.urlopen(request, timeout=self.timeout) as response:
                        return UrllibResponse(response)
                else:
                    return MockResponse(status_code=500, text="No HTTP client available")
            except Exception as e:
                logger.error(e, f"Sync GET error (attempt {retry_count+1})")
                last_error = e
                retry_count += 1
                if retry_count < max_retries:
                    import time
                    gc.collect()
                    time.sleep(2 * retry_count)

        error_msg = str(last_error) if last_error else "Unknown error"
        logger.error(None, f"All {max_retries} sync GET attempts to {url} failed: {error_msg}")
        return MockResponse(status_code=500, text=f"Error: {error_msg}")