"""Server adapters for different platforms (CircuitPython and Development).

Provides a common interface while handling platform-specific HTTP server implementations.
Extracted from Theme Park API for SLDK web framework.
"""

from __future__ import annotations

import sys
try:
    from typing import Any, Dict, List, Optional, Union
except ImportError:  # CircuitPython has no 'typing' module
    pass

try:
    import asyncio
except ImportError:
    import asyncio

from ..exceptions import WebServerError

# Platform detection
IS_CIRCUITPYTHON = hasattr(sys, 'implementation') and sys.implementation.name == 'circuitpython'


class ServerAdapter:
    """Base class for server adapters.

    Note: Using duck typing instead of ABC since CircuitPython doesn't have abc module.
    """

    def start_server(self, host: str, port: int) -> bool:
        """Start the HTTP server.

        Args:
            host: Host address to bind to
            port: Port number to bind to

        Returns:
            bool: True if started successfully
        """
        raise NotImplementedError("Subclass must implement start_server()")

    def stop_server(self) -> None:
        """Stop the HTTP server."""
        raise NotImplementedError("Subclass must implement stop_server()")

    def parse_query_params(self, query_string: Optional[str]) -> Dict[str, str]:
        """Parse query parameters from URL.

        Args:
            query_string: Raw query string

        Returns:
            dict: Parsed parameters
        """
        raise NotImplementedError("Subclass must implement parse_query_params()")

    def parse_form_data(self, request_body: Optional[str]) -> Dict[str, str]:
        """Parse form data from POST request.

        Args:
            request_body: Raw request body

        Returns:
            dict: Parsed form data
        """
        raise NotImplementedError("Subclass must implement parse_form_data()")

    def url_decode(self, text: Optional[str]) -> Optional[str]:
        """Decode URL-encoded text (CircuitPython compatible).

        Args:
            text: URL-encoded text

        Returns:
            str: Decoded text
        """
        if not text:
            return text

        text = text.replace('%20', ' ')
        text = text.replace('%21', '!')
        text = text.replace('%22', '"')
        text = text.replace('%23', '#')
        text = text.replace('%24', '$')
        text = text.replace('%25', '%')
        text = text.replace('%26', '&')
        text = text.replace('%27', "'")
        text = text.replace('%28', '(')
        text = text.replace('%29', ')')
        text = text.replace('%2A', '*')
        text = text.replace('%2B', '+')
        text = text.replace('%2C', ',')
        text = text.replace('%2D', '-')
        text = text.replace('%2E', '.')
        text = text.replace('%2F', '/')
        text = text.replace('%3A', ':')
        text = text.replace('%3B', ';')
        text = text.replace('%3C', '<')
        text = text.replace('%3D', '=')
        text = text.replace('%3E', '>')
        text = text.replace('%3F', '?')
        text = text.replace('%40', '@')
        text = text.replace('+', ' ')

        return text


if IS_CIRCUITPYTHON:
    class CircuitPythonAdapter(ServerAdapter):
        """Server adapter for CircuitPython using adafruit_httpserver."""

        handler_class: type
        socket_pool: Any
        static_dir: str
        server: Any
        _running: bool

        def __init__(
            self,
            handler_class: type,
            socket_pool: Any = None,
            static_dir: str = "/www",
        ) -> None:
            """Initialize CircuitPython adapter.

            Args:
                handler_class: Handler class with route methods
                socket_pool: Socket pool for networking
                static_dir: Directory for static files
            """
            self.handler_class = handler_class
            self.socket_pool = socket_pool
            self.static_dir = static_dir
            self.server = None
            self._running = False

        def start_server(self, host: str = "0.0.0.0", port: int = 80) -> bool:
            """Start the CircuitPython HTTP server."""
            try:
                from adafruit_httpserver import HTTPServer, HTTPRoute, HTTPResponse

                if not self.socket_pool:
                    print("Error: Socket pool required for CircuitPython adapter")
                    return False

                self.server = HTTPServer(self.socket_pool, self.static_dir)
                self._setup_routes()
                self.server.start(host, port)
                self._running = True
                print(f"CircuitPython web server started on {host}:{port}")

                return True

            except WebServerError:
                raise
            except Exception as e:
                print(f"Failed to start CircuitPython web server: {e}")
                return False

        def stop_server(self) -> None:
            """Stop the CircuitPython HTTP server."""
            if self.server:
                try:
                    self.server.stop()
                    self._running = False
                    print("CircuitPython web server stopped")
                except Exception as e:
                    print(f"Error stopping CircuitPython web server: {e}")

        @property
        def is_running(self) -> bool:
            """Check if server is running."""
            return self._running

        async def handle_requests(self) -> None:
            """Handle incoming requests (CircuitPython)."""
            if self.server:
                await asyncio.sleep(0.1)

        def _setup_routes(self) -> None:
            """Set up HTTP routes from handler class."""
            from adafruit_httpserver import HTTPRoute, HTTPResponse

            handler = self.handler_class(self)

            for attr_name, route_info in _iter_routes(handler):
                method = getattr(handler, attr_name)
                if not callable(method):
                    continue
                path = route_info['path']
                methods = route_info.get('methods', ['GET'])

                for http_method in methods:
                    @self.server.route(path, methods=[http_method])
                    def route_handler(request: Any, method: Any = method) -> Any:
                        return method(request)

        def parse_query_params(self, query_string: Optional[str]) -> Dict[str, str]:
            """Parse query parameters from URL."""
            params: Dict[str, str] = {}
            if not query_string:
                return params

            try:
                for pair in query_string.split('&'):
                    if '=' in pair:
                        key, value = pair.split('=', 1)
                        key = self.url_decode(key)
                        value = self.url_decode(value)
                        params[key] = value
            except Exception as e:
                print(f"Error parsing query parameters: {e}")

            return params

        def parse_form_data(self, request_body: Optional[Union[str, bytes]]) -> Dict[str, str]:
            """Parse form data from POST request."""
            if not request_body:
                return {}

            if isinstance(request_body, bytes):
                try:
                    request_body = request_body.decode('utf-8')
                except UnicodeDecodeError:
                    print("Failed to decode form data")
                    return {}

            return self.parse_query_params(request_body)

else:
    import threading
    from http.server import HTTPServer, BaseHTTPRequestHandler
    from urllib.parse import parse_qs, urlparse

    class DevelopmentAdapter(ServerAdapter):
        """Server adapter for development using Python's http.server."""

        handler_class: type
        static_dir: str
        server: Any
        server_thread: Any
        _running: bool

        def __init__(self, handler_class: type, static_dir: str = "./www") -> None:
            """Initialize development adapter.

            Args:
                handler_class: Handler class with route methods
                static_dir: Directory for static files
            """
            self.handler_class = handler_class
            self.static_dir = static_dir
            self.server = None
            self.server_thread = None
            self._running = False

        def start_server(self, host: str = "localhost", port: int = 8080) -> bool:
            """Start the development HTTP server."""
            try:
                adapter = self
                handler_instance = self.handler_class(self)

                class SLDKRequestHandler(BaseHTTPRequestHandler):
                    def log_message(self, format: str, *args: Any) -> None:
                        """Override to use print for logging."""
                        print(f"HTTP: {format % args}")

                    def do_GET(self) -> None:
                        """Handle GET requests."""
                        try:
                            parsed_url = urlparse(self.path)
                            path = parsed_url.path
                            query = parsed_url.query

                            response = self._handle_route('GET', path, query, None)
                            if response:
                                self._send_response_obj(response)
                            else:
                                self._send_response(404, "text/plain", "Not Found")

                        except Exception as e:
                            print(f"Error handling GET request: {e}")
                            self._send_response(500, "text/plain", "Internal Server Error")

                    def do_POST(self) -> None:
                        """Handle POST requests."""
                        try:
                            parsed_url = urlparse(self.path)
                            path = parsed_url.path
                            query = parsed_url.query

                            content_length = int(self.headers.get('Content-Length', 0))
                            post_data = self.rfile.read(content_length).decode('utf-8')

                            response = self._handle_route('POST', path, query, post_data)
                            if response:
                                self._send_response_obj(response)
                            else:
                                self._send_response(404, "text/plain", "Not Found")

                        except Exception as e:
                            print(f"Error handling POST request: {e}")
                            self._send_response(500, "text/plain", "Internal Server Error")

                    def _handle_route(
                        self, method: str, path: str, query: str, body: Optional[str]
                    ) -> Any:
                        """Handle route matching and execution."""
                        for attr_name, route_info in _iter_routes(handler_instance):
                            route_method = getattr(handler_instance, attr_name)
                            if not callable(route_method):
                                continue
                            route_path = route_info['path']
                            route_methods = route_info.get('methods', ['GET'])

                            if path == route_path and method in route_methods:
                                request = MockRequest(method, path, query, body, adapter)
                                return route_method(request)

                        return None

                    def _send_response_obj(self, response: Any) -> None:
                        """Send response object."""
                        status = getattr(response, 'status', 200)
                        content_type = getattr(response, 'content_type', 'text/html')
                        body = getattr(response, 'body', '')

                        self._send_response(status, content_type, body)

                    def _send_response(
                        self, status: int, content_type: str, content: Union[str, bytes]
                    ) -> None:
                        """Send HTTP response."""
                        self.send_response(status)
                        self.send_header('Content-type', content_type)
                        self.end_headers()

                        if isinstance(content, str):
                            self.wfile.write(content.encode('utf-8'))
                        else:
                            self.wfile.write(content)

                self.server = HTTPServer((host, port), SLDKRequestHandler)
                self.server_thread = threading.Thread(target=self.server.serve_forever)
                self.server_thread.daemon = True
                self.server_thread.start()
                self._running = True

                print(f"Development web server started on http://{host}:{port}")
                return True

            except Exception as e:
                print(f"Failed to start development web server: {e}")
                return False

        def stop_server(self) -> None:
            """Stop the development HTTP server."""
            if self.server:
                try:
                    self.server.shutdown()
                    self.server.server_close()
                    if self.server_thread:
                        self.server_thread.join(timeout=5)
                    self._running = False
                    print("Development web server stopped")
                except Exception as e:
                    print(f"Error stopping development web server: {e}")

        @property
        def is_running(self) -> bool:
            """Check if server is running."""
            return self._running

        async def handle_requests(self) -> None:
            """Handle incoming requests (Development)."""
            await asyncio.sleep(0.1)

        def parse_query_params(self, query_string: Optional[str]) -> Dict[str, str]:
            """Parse query parameters from URL."""
            if not query_string:
                return {}

            try:
                parsed = parse_qs(query_string, keep_blank_values=True)
                params: Dict[str, str] = {}
                for key, values in parsed.items():
                    params[key] = values[0] if values else ""
                return params
            except Exception as e:
                print(f"Error parsing query parameters: {e}")
                return {}

        def parse_form_data(self, request_body: Optional[str]) -> Dict[str, str]:
            """Parse form data from POST request."""
            return self.parse_query_params(request_body)


class MockRequest:
    """Mock request object for development adapter."""

    method: str
    path: str
    query: str
    body: Optional[str]
    adapter: ServerAdapter
    query_params: Dict[str, str]
    form_data: Dict[str, str]

    def __init__(
        self,
        method: str,
        path: str,
        query: str,
        body: Optional[str],
        adapter: ServerAdapter,
    ) -> None:
        self.method = method
        self.path = path
        self.query = query
        self.body = body
        self.adapter = adapter

        self.query_params = adapter.parse_query_params(query)

        if method == 'POST' and body:
            self.form_data = adapter.parse_form_data(body)
        else:
            self.form_data = {}


class MockResponse:
    """Mock response object for both adapters."""

    body: Union[str, bytes]
    status: int
    content_type: str

    def __init__(
        self,
        body: Union[str, bytes],
        status: int = 200,
        content_type: str = "text/html",
    ) -> None:
        self.body = body
        self.status = status
        self.content_type = content_type


class _RouteMarker:
    """Holder the ``@route`` decorator leaves in the class namespace.

    Two CircuitPython constraints drive this design (neither is catchable by the
    CPython simulator suite — see the grep-guard regression test):

      1. CircuitPython plain functions have no ``__dict__`` — you cannot set an
         attribute on them (the original ``func._route_info = ...`` bug). Marker
         *instances* allow attributes, so we wrap the function in one.
      2. CircuitPython plain functions do not even expose ``func.__name__`` (it is
         omitted to save RAM). So the method name is NEVER read off the function;
         ``RouteRegistryMixin`` derives it from the class-namespace key instead and
         then restores the real function with ``setattr``.
    """

    def __init__(self, func: Any, path: str, methods: List[str]) -> None:
        self.func = func
        self.path = path
        self.methods = methods


def route(path: str, methods: Optional[List[str]] = None) -> Any:
    """Decorator to mark methods as route handlers.

    Returns a ``_RouteMarker`` instance (NOT the function) wrapping the route
    metadata. The enclosing handler class (via ``RouteRegistryMixin``) reads the
    marker, records the route under the namespace name, and restores the real
    function. The function object is never mutated and ``func.__name__`` is never
    read — both are unavailable on CircuitPython.

    Args:
        path: URL path to handle
        methods: List of HTTP methods (default: ['GET'])
    """
    if methods is None:
        methods = ['GET']

    def decorator(func: Any) -> Any:
        return _RouteMarker(func, path, list(methods))
    return decorator


class RouteRegistryMixin:
    """Collects ``@route``-decorated methods into a class-level ``_routes`` registry.

    Handler base classes inherit this mixin so route metadata lives on the class
    (keyed by method name) rather than on the function object — the CircuitPython-safe
    equivalent of the old ``func._route_info`` attribute.

    ``_routes`` maps ``method_name -> {'path': str, 'methods': List[str]}``. Each
    subclass inherits its bases' routes (merged across the full MRO so multiple
    inheritance keeps every base's routes) and adds/overrides its own.
    """

    _routes: Dict[str, Dict[str, Any]] = {}

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)

        # Merge inherited routes across the whole MRO (reverse order so that
        # more-derived bases override less-derived ones, and so multiple
        # inheritance keeps routes from every base, not just the first).
        merged: Dict[str, Dict[str, Any]] = {}
        for base in reversed(cls.__mro__[1:]):
            base_routes = getattr(base, '_routes_own', None)
            if base_routes:
                merged.update(base_routes)

        # Scan this class's namespace for routes the decorator just left behind.
        # The method NAME comes from the namespace key (``dir(cls)`` + getattr —
        # matching dispatch, since CircuitPython's ``cls.__dict__`` is unreliable),
        # NOT from ``func.__name__`` (unavailable on CircuitPython). Each marker is
        # replaced by its real function so dispatch can ``getattr(handler, name)()``.
        own: Dict[str, Dict[str, Any]] = {}
        for name in dir(cls):
            value = getattr(cls, name, None)
            if isinstance(value, _RouteMarker):
                own[name] = {'path': value.path, 'methods': value.methods}
                setattr(cls, name, value.func)

        merged.update(own)

        # ``_routes_own`` records only the routes declared directly on this class so
        # subclasses can re-merge precisely; ``_routes`` is the full effective set.
        cls._routes_own = own
        cls._routes = merged


def _iter_routes(handler: Any) -> Any:
    """Yield ``(method_name, route_info)`` for every route on ``handler``'s class.

    Reads the class-level ``_routes`` registry populated by ``RouteRegistryMixin``
    (CircuitPython-safe — no function attributes). Falls back to scanning ``route_*``
    methods for a legacy ``_route_info`` function attribute so handlers that don't
    derive from the mixin still dispatch on CPython.
    """
    routes = getattr(type(handler), '_routes', None)
    if routes:
        for fname, info in routes.items():
            yield fname, info
        return

    # Legacy fallback (function-attribute metadata). Not reachable on CircuitPython.
    for attr_name in dir(handler):
        if attr_name.startswith('route_'):
            method = getattr(handler, attr_name)
            info = getattr(method, '_route_info', None)
            if callable(method) and info is not None:
                yield attr_name, info


def create_server_adapter(
    handler_class: type,
    socket_pool: Any = None,
    static_dir: Optional[str] = None,
) -> ServerAdapter:
    """Factory function to create the appropriate server adapter.

    Args:
        handler_class: Handler class with route methods
        socket_pool: Socket pool (CircuitPython only)
        static_dir: Directory for static files

    Returns:
        ServerAdapter instance
    """
    if static_dir is None:
        static_dir = "/www" if IS_CIRCUITPYTHON else "./www"

    if IS_CIRCUITPYTHON:
        return CircuitPythonAdapter(handler_class, socket_pool, static_dir)
    else:
        return DevelopmentAdapter(handler_class, static_dir)