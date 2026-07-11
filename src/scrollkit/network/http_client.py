"""
HTTP client for making API requests.
Supports both adafruit_requests (CircuitPython) and urllib (standard Python).
Copyright (c) 2024-2026 Michael Czeiszperger
"""
import json
import gc

from scrollkit.exceptions import NetworkError


__all__ = ['HttpClient', 'BaseResponse', 'UrllibResponse', 'MockResponse']

def _logger():
    # Lazy: constructing ErrorHandler does a filesystem write-test, so it must
    # not run merely from importing this module. Its own __new__ singleton
    # guard makes repeat calls cheap.
    from scrollkit.utils.error_handler import ErrorHandler
    return ErrorHandler("error_log")

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
                _logger().error(e, f"JSON parse error: {str(e)}")
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

    def __init__(self, session=None, mock_provider=None, timeout=6,
                 session_rebuild_threshold=2):
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
                     wedging.

                     INVARIANT: HTTP timeout < watchdog timeout. A fetch that runs
                     the full timeout blocks the loop (and thus watchdog feeding)
                     for that long, so it must finish inside the watchdog window or
                     it triggers a false reset. Default 6s sits below the ESP32-S3
                     ~8s watchdog (see ScrollKitApp.watchdog_timeout).
            session_rebuild_threshold: After this many CONSECUTIVE failed requests
                     the session is torn down and recreated (fresh
                     ``SocketPool(wifi.radio)`` + ssl context). The dominant field
                     wedge is a session whose sockets/TLS state get stuck — a
                     read/connect timeout, mbedTLS/SSL error, ConnectionError or
                     OSError — after which EVERY fetch through that session fails
                     identically until the radio is re-initialised. None of those
                     are ``OutOfRetries``, so the old "rebuild only on OutOfRetries"
                     never fired and the box served stale data for days. Rebuilding
                     on any repeated failure clears it without a reboot. Default 2
                     (recover fast) but >1 so a single blip doesn't thrash the
                     pool. Device-only; a no-op on the desktop urllib path.
        """
        self.session = session
        self.use_live_data = True
        self.mock_provider = mock_provider
        self.timeout = timeout

        # --- resilience / diagnostics state ---------------------------------
        # Rebuild the wedged session after this many consecutive failures.
        self.session_rebuild_threshold = session_rebuild_threshold
        # Consecutive request failures since the last success OR rebuild (gates
        # the rebuild; reset to 0 on either).
        self._failures_since_rebuild = 0
        # The most recent request exception, surfaced so callers/diagnostics can
        # record WHY fetching failed. Cleared on the next success.
        self.last_error = None
        # time.monotonic() of the last successful request (None until one
        # succeeds) — drives a "seconds since last success" staleness signal.
        self._last_success_time = None

        # Platform detection
        try:
            from scrollkit.network.wifi_manager import is_dev_mode
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
            A socket-free Response object: a detached ``BaseResponse`` (device
            path; the native ``adafruit_requests`` response is read and closed so
            its socket returns to the pool), a ``UrllibResponse`` (desktop), or a
            ``MockResponse`` (from a mock provider). Callers never need to
            ``.close()`` it.

        Raises:
            NetworkError: after all ``max_retries`` attempts fail (each attempt
                still counts toward the consecutive-failure session rebuild).
                ``self.last_error`` retains the raw underlying exception for
                diagnostics (e.g. ``note_refresh_result``).
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

        # No HTTP client at all (no adafruit session, no urllib) is a permanent
        # configuration state, not a transient blip — fail fast instead of
        # burning the retry loop's backoff on it.
        if not (self.using_adafruit and self.session) and not self.urllib:
            raise NetworkError("No HTTP client available")

        while retry_count < max_retries:
            try:
                if self.using_adafruit and self.session:
                    resp = await self._get_adafruit(url, headers, retry_count)
                else:
                    resp = self._get_urllib(url, headers)
                self._note_success()
                return resp
            except Exception as outer_error:
                _logger().error(outer_error, f"HTTP GET error (attempt {retry_count+1})")
                last_error = outer_error
                # Count the failure and, on a repeated failure, rebuild the
                # (likely wedged) session so the NEXT retry uses a fresh socket
                # pool instead of hammering the stuck one forever.
                self._note_failure(outer_error)
                retry_count += 1
                import asyncio as _asyncio
                await _asyncio.sleep(0.5 + retry_count * 0.5)

        error_msg = str(last_error) if last_error else "Unknown error"
        _logger().error(None, f"All {max_retries} GET attempts to {url} failed: {error_msg}")
        # Raise a typed error so callers can catch scrollkit.exceptions.NetworkError
        # at the boundary. self.last_error still holds the RAW underlying exception
        # (set by _note_failure) so the app can record why the outage happened.
        # No `raise ... from` chaining: retaining the cause traceback fragments the
        # heap on CircuitPython.
        raise NetworkError("GET %s failed after %d attempts: %s"
                           % (url, max_retries, error_msg))

    @staticmethod
    def _detach_response(resp):
        """Copy a native ``adafruit_requests`` response into a socket-free
        ``BaseResponse`` so the native one (and its socket) can be closed.

        Reading ``.text`` pulls the whole body off the socket (the adafruit
        response caches it); the caller then closes the native response and the
        socket goes back to the ESP32-S3's ~4-socket pool. The returned
        ``BaseResponse`` owns no socket, so callers may keep or discard it freely.

        This mirrors the urllib path, which already detaches via
        ``UrllibResponse``. Without it, every SUCCESSFUL device fetch returned the
        live native response and nothing ever closed it (only failures were
        closed), so a socket leaked per fetch until the pool was exhausted and
        every subsequent ``session.get`` raised ``OSError 16 (EBUSY)`` — a
        permanent wedge a ``_rebuild_session`` could not clear, because the leaked
        sockets were owned by discarded, never-closed response objects.
        """
        status = getattr(resp, "status_code", 200)
        try:
            hdrs = dict(resp.headers)
        except Exception:
            hdrs = {}
        text = resp.text
        if not isinstance(text, str):
            # Real adafruit_requests returns str; guard odd providers/mocks.
            try:
                text = text.decode("utf-8")
            except Exception:
                text = ""
        return BaseResponse(status_code=status, text=text, headers=hdrs)

    async def _get_adafruit(self, url, headers, retry_count):
        """Issue one ``adafruit_requests`` GET and return a DETACHED response,
        always closing the native socket.

        The native response is read into a socket-free ``BaseResponse``
        (``_detach_response``) and the native one is closed in ``finally`` on BOTH
        success and failure — a socket leaked out of the ESP32-S3's ~4-socket pool
        is the dominant field wedge (it exhausts the pool, then every fetch raises
        ``OSError 16 EBUSY``). On any exception it propagates so ``get()``'s
        retry/rebuild logic runs. Session recreation is handled centrally by
        ``_note_failure()`` / ``_rebuild_session()``, NOT here, so EVERY repeated
        failure — read/connect timeout, mbedTLS/SSL error, ConnectionError,
        OSError, OutOfRetries — clears a wedged session, not just the rare
        ``OutOfRetries`` case.
        """
        resp = None
        try:
            resp = self.session.get(url, headers=headers, timeout=self.timeout)
            return self._detach_response(resp)
        finally:
            if resp is not None:
                try:
                    resp.close()
                except Exception:
                    pass

    def _note_success(self):
        """Record a successful request: clear the error + failure streak and
        stamp the last-success time (drives the staleness signal)."""
        self.last_error = None
        self._failures_since_rebuild = 0
        try:
            import time
            self._last_success_time = (
                time.monotonic() if hasattr(time, "monotonic") else None)
        except Exception:
            self._last_success_time = None

    def _note_failure(self, error):
        """Record a failed request and rebuild the session once the consecutive
        failure count crosses the threshold (the in-place wedge repair)."""
        self.last_error = error
        self._failures_since_rebuild += 1
        if (self.using_adafruit and self.session is not None
                and self._failures_since_rebuild >= self.session_rebuild_threshold):
            if self._rebuild_session():
                # Give the fresh session a clean slate so a transient blip after
                # a rebuild doesn't immediately rebuild again (thrash).
                self._failures_since_rebuild = 0

    def close_pooled_sockets(self):
        """Properly close every socket the current session's connection manager
        holds, releasing their NATIVE resources (each pooled TLS socket pins an
        mbedtls context — ~40 KB of the ESP32-S3's ~320 KB internal SRAM, which
        PSRAM cannot substitute for). Public so callers needing native headroom
        for a new TLS handshake (e.g. an OTA check to a second host) can make
        room through a supported API. The pool stays valid: the manager opens
        fresh sockets transparently on the next request.

        Returns True if a close-all ran. Never raises."""
        session = self.session
        if session is None:
            return False
        try:
            from adafruit_connection_manager import connection_manager_close_all
            pool = session._connection_manager._socket_pool
            connection_manager_close_all(socket_pool=pool)
            return True
        except Exception as e:
            _logger().error(e, "close_pooled_sockets failed")
            return False

    def _rebuild_session(self):
        """Tear down and recreate the adafruit_requests session.

        A fresh ``SocketPool(wifi.radio)`` + ssl context discards the wedged
        pool's stuck sockets/TLS state — the only way to clear the dominant field
        failure short of a reboot. Device-only (the imports exist on CircuitPython
        only); a no-op that returns False on desktop, where the urllib path never
        uses a session. Never raises into the caller.

        HYGIENE IS LOAD-BEARING: the old session's pooled sockets must be
        properly CLOSED before the replacement exists — dropping them to the GC
        does not promptly release their native mbedtls TLS contexts. With a
        rebuild threshold of 2, every pair of transient blips on a multi-day run
        orphaned another ~40 KB of internal SRAM, until TLS handshakes (data
        path AND the OTA check) died with mbedtls PK_ALLOC_FAILED / MemoryError.
        Found 2026-07-11 after a ~30 h soak left the field device in
        'STALE (network issues)'.
        """
        if not (self.using_adafruit and self.session is not None):
            return False
        # Release the wedged pool's native sockets/TLS contexts first — this is
        # both the leak fix and what frees room for the replacement context.
        self.close_pooled_sockets()
        try:
            import socketpool
            import wifi
            import ssl
            import adafruit_requests
            gc.collect()  # reclaim RAM before allocating a new pool/context
            pool = socketpool.SocketPool(wifi.radio)
            ssl_context = ssl.create_default_context()
            self.session = adafruit_requests.Session(pool, ssl_context)
            gc.collect()
            _logger().info("Recreated HTTP session after repeated failures")
            return True
        except Exception as e:
            _logger().error(e, "HTTP session rebuild failed")
            return False

    def seconds_since_last_success(self):
        """Seconds since the last successful request, or None if none yet.

        A staleness signal for the app: a large/growing value while requests keep
        failing means the displayed data is stale even though the box looks alive.
        """
        if self._last_success_time is None:
            return None
        try:
            import time
            if not hasattr(time, "monotonic"):
                return None
            return time.monotonic() - self._last_success_time
        except Exception:
            return None

    def _get_urllib(self, url, headers):
        if not self.urllib:
            # Raise (not return a synthesized 500): a returned failure here was
            # counted as a success by get() (which called _note_success on it).
            raise NetworkError("No HTTP client available")
        request = self.urllib.Request(url)
        for key, value in headers.items():
            request.add_header(key, value)
        with self.urllib.urlopen(request, timeout=self.timeout) as response:
            return UrllibResponse(response)

    async def post(self, url, data, headers=None):
        """Make a POST request.

        Mirrors ``get()``: on the device path the native ``adafruit_requests``
        response is read into a socket-free ``BaseResponse`` and CLOSED in a
        ``finally`` so its socket returns to the ~4-socket pool — a leaked POST
        socket wedges the device with ``OSError 16 (EBUSY)`` exactly like a leaked
        GET. A per-request ``timeout`` is passed (both paths) so a hung POST can't
        block the synchronous asyncio loop and trip the watchdog. POST is
        single-shot (no retry loop), but a failure is recorded via
        ``_note_failure`` so a wedged session still gets rebuilt on the next
        request, raises ``NetworkError``, and the cause is retained on
        ``last_error``.
        """
        if headers is None:
            headers = {
                "User-Agent": "Mozilla/5.0 (CircuitPython)",
                "Content-Type": "application/json"
            }
        if isinstance(data, dict):
            data = json.dumps(data)
        # Raise cleanly BEFORE the try so the "no client" NetworkError isn't
        # re-wrapped by the except below (and so the urllib branch never calls
        # None.Request(...) -> AttributeError when urllib is absent on device).
        if not (self.using_adafruit and self.session) and not self.urllib:
            raise NetworkError("No HTTP client available")
        try:
            if self.using_adafruit and self.session:
                resp = None
                try:
                    resp = self.session.post(url, data=data, headers=headers,
                                             timeout=self.timeout)
                    detached = self._detach_response(resp)
                    self._note_success()
                    return detached
                finally:
                    if resp is not None:
                        try:
                            resp.close()
                        except Exception:
                            pass
            else:
                request = self.urllib.Request(
                    url,
                    data=data.encode('utf-8') if isinstance(data, str) else data,
                    method="POST"
                )
                for key, value in headers.items():
                    request.add_header(key, value)
                with self.urllib.urlopen(request, timeout=self.timeout) as response:
                    # Keep last_error/last-success bookkeeping consistent with get().
                    self._note_success()
                    return UrllibResponse(response)
        except Exception as e:
            _logger().error(e, f"Error making POST request to {url}")
            self._note_failure(e)
            # self.last_error holds the raw cause (set by _note_failure). Plain
            # raise, no `from e` chaining (heap fragmentation on CircuitPython).
            raise NetworkError("POST %s failed: %s: %s" % (url, type(e).__name__, e))

    def set_use_live_data(self, use_live_data):
        """Set whether to use live data or mock data."""
        self.use_live_data = use_live_data
        _logger().info(f"HTTP client: {'live' if use_live_data else 'mock'} data")

    def get_sync(self, url, headers=None, max_retries=3):
        """Synchronous wrapper for GET requests (CircuitPython compatible)."""
        gc.collect()
        if headers is None:
            headers = {"User-Agent": "Mozilla/5.0 (CircuitPython)"}

        retry_count = 0
        last_error = None

        # Fail fast on a permanent no-client state instead of sleeping through
        # the retry backoff (blocking real time.sleep on the sync path).
        if not (self.using_adafruit and self.session) and not self.urllib:
            raise NetworkError("No HTTP client available")

        while retry_count < max_retries:
            try:
                if self.using_adafruit and self.session:
                    gc.collect()
                    resp = None
                    try:
                        _logger().debug(f"Sync GET: {url}")
                        resp = self.session.get(url, headers=headers, timeout=self.timeout)
                        # Detach BEFORE _note_success/return so the native socket
                        # is freed by the finally on the success path too — leaking
                        # it exhausts the ~4-socket pool (OSError 16 EBUSY).
                        detached = self._detach_response(resp)
                        self._note_success()
                        return detached
                    finally:
                        if resp is not None:
                            try:
                                resp.close()
                            except Exception:
                                pass
                elif self.urllib:
                    request = self.urllib.Request(url)
                    for key, value in headers.items():
                        request.add_header(key, value)
                    with self.urllib.urlopen(request, timeout=self.timeout) as response:
                        self._note_success()
                        return UrllibResponse(response)
                else:
                    raise NetworkError("No HTTP client available")
            except Exception as e:
                _logger().error(e, f"Sync GET error (attempt {retry_count+1})")
                last_error = e
                # Same repeated-failure session rebuild as the async path, so a
                # wedged session self-recovers whichever entry point the app uses.
                self._note_failure(e)
                retry_count += 1
                if retry_count < max_retries:
                    import time
                    gc.collect()
                    time.sleep(2 * retry_count)

        error_msg = str(last_error) if last_error else "Unknown error"
        _logger().error(None, f"All {max_retries} sync GET attempts to {url} failed: {error_msg}")
        # Raise a typed error at the boundary (self.last_error keeps the raw cause).
        raise NetworkError("sync GET %s failed after %d attempts: %s"
                           % (url, max_retries, error_msg))