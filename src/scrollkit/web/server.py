"""SLDK Web Server

Unified web server that works on both CircuitPython and development environments.
Extracted from Theme Park API for the SLDK framework.
"""

from __future__ import annotations

try:
    from typing import Any, Dict, List, Optional
except ImportError:  # CircuitPython has no 'typing' module
    pass

try:
    import asyncio
except ImportError:
    import asyncio

from .adapters import create_server_adapter, IS_CIRCUITPYTHON, ServerAdapter
from .handlers import WebHandler, StaticFileHandler, APIHandler


class SLDKWebServer:
    """SLDK web server that works on both CircuitPython and development platforms."""

    app: Any
    socket_pool: Any
    static_dir: Optional[str]
    handler_class: type
    adapter: ServerAdapter
    _running: bool
    _host: Optional[str]
    _port: Optional[int]

    def __init__(
        self,
        app: Any = None,
        handler_class: Optional[type] = None,
        socket_pool: Any = None,
        static_dir: Optional[str] = None,
    ) -> None:
        """Initialize the SLDK web server.

        Args:
            app: SLDK application instance
            handler_class: Custom handler class (default: WebHandler)
            socket_pool: Socket pool (CircuitPython only)
            static_dir: Directory for static files
        """
        self.app = app
        self.socket_pool = socket_pool
        self.static_dir = static_dir

        if handler_class:
            self.handler_class = handler_class
        else:
            self.handler_class = self._create_composite_handler()

        self.adapter = create_server_adapter(
            self.handler_class,
            socket_pool=socket_pool,
            static_dir=static_dir,
        )

        self._running = False
        self._host = None
        self._port = None

    def _create_composite_handler(self) -> type:
        """Create a composite handler that combines multiple handler types.

        ``StaticFileHandler`` and ``APIHandler`` both already derive from
        ``WebHandler``, so listing ``WebHandler`` *first* is an illegal MRO (a
        base may not precede its own subclasses). It stays reachable through the
        other two — MRO: CompositeHandler -> StaticFileHandler -> APIHandler ->
        WebHandler -> object.
        """
        class CompositeHandler(StaticFileHandler, APIHandler):
            def __init__(self, adapter: ServerAdapter) -> None:
                WebHandler.__init__(self, adapter)
                StaticFileHandler.__init__(self, adapter)
                APIHandler.__init__(self, adapter)

        return CompositeHandler

    async def start(self, host: Optional[str] = None, port: Optional[int] = None) -> bool:
        """Start the web server.

        Args:
            host: Host to bind to (optional, platform-specific defaults)
            port: Port to bind to (optional, platform-specific defaults)

        Returns:
            bool: True if server started successfully
        """
        try:
            if IS_CIRCUITPYTHON:
                self._host = host or "0.0.0.0"
                self._port = port or 80
            else:
                self._host = host or "localhost"
                self._port = port or 8080

            print(f"Starting SLDK web server on {self._host}:{self._port}")

            success = self.adapter.start_server(self._host, self._port)
            if success:
                self._running = True
                print("SLDK web server started successfully")
            else:
                print("Failed to start SLDK web server")

            return success

        except Exception as e:
            print(f"Error starting SLDK web server: {e}")
            return False

    async def stop(self) -> None:
        """Stop the web server."""
        try:
            if self._running:
                print("Stopping SLDK web server")
                self.adapter.stop_server()
                self._running = False
                print("SLDK web server stopped")
        except Exception as e:
            print(f"Error stopping SLDK web server: {e}")

    @property
    def is_running(self) -> bool:
        """Check if the web server is running."""
        return self._running and getattr(self.adapter, 'is_running', False)

    async def handle_requests(self) -> None:
        """Handle incoming requests."""
        if self._running:
            await self.adapter.handle_requests()

    def get_server_url(self) -> str:
        """Get the server URL.

        Returns:
            str: Server URL
        """
        if IS_CIRCUITPYTHON and self.socket_pool:
            try:
                return f"http://{self._host}:{self._port}"
            except Exception:
                return f"http://{self._host}:{self._port}"
        else:
            return f"http://{self._host}:{self._port}"

    async def run_forever(self) -> None:
        """Run the web server forever (async version)."""
        while self._running:
            await self.handle_requests()
            await asyncio.sleep(0.1)


# Public name for the merged ScrollKit library. `SLDKWebServer` is retained as a
# backward-compatible alias for code/tests that still reference the old name.
ScrollKitWebServer = SLDKWebServer


class SLDKWebApplication:
    """Web application framework for SLDK.

    Provides a more structured way to build web applications
    with multiple handlers and middleware.
    """

    sldk_app: Any
    handlers: List[type]
    middleware: List[Any]
    _routes: Dict[str, Dict[str, Any]]

    def __init__(self, sldk_app: Any = None) -> None:
        """Initialize web application.

        Args:
            sldk_app: Parent SLDK application instance
        """
        self.sldk_app = sldk_app
        self.handlers = []
        self.middleware = []
        self._routes = {}

    def add_handler(self, handler_class: type) -> None:
        """Add a handler class to the application.

        Args:
            handler_class: Handler class to add
        """
        self.handlers.append(handler_class)

    def add_middleware(self, middleware_func: Any) -> None:
        """Add middleware to the application.

        Args:
            middleware_func: Middleware function
        """
        self.middleware.append(middleware_func)

    def route(self, path: str, methods: Optional[List[str]] = None) -> Any:
        """Decorator to add routes to the application.

        Args:
            path: URL path
            methods: List of HTTP methods
        """
        def decorator(func: Any) -> Any:
            if methods is None:
                route_methods = ['GET']
            else:
                route_methods = methods

            self._routes[path] = {
                'function': func,
                'methods': route_methods,
            }
            return func
        return decorator

    def create_server(
        self,
        socket_pool: Any = None,
        static_dir: Optional[str] = None,
    ) -> SLDKWebServer:
        """Create a web server for this application.

        Args:
            socket_pool: Socket pool (CircuitPython only)
            static_dir: Directory for static files

        Returns:
            SLDKWebServer instance
        """
        app = self
        handler_classes = self.handlers or [WebHandler, StaticFileHandler, APIHandler]

        # Build the route registry once from the programmatic routes registered via
        # SLDKWebApplication.route(). Each path maps to a generated ``route_*`` method
        # name; the metadata lives in the class-level ``_routes`` registry (never on
        # the function object — CircuitPython functions have no __dict__).
        app_routes: Dict[str, Dict[str, Any]] = {}
        app_funcs: Dict[str, Any] = {}
        for path, route_info in app._routes.items():
            route_name = f"route_{path.replace('/', '_').replace('<', '').replace('>', '').strip('_')}"
            app_routes[route_name] = {'path': path, 'methods': route_info['methods']}
            app_funcs[route_name] = route_info['function']

        class ApplicationHandler(*handler_classes):  # type: ignore
            def __init__(self, adapter: ServerAdapter) -> None:
                for handler_class in handler_classes:
                    handler_class.__init__(self, adapter)

                # Bind the programmatic route functions as instance attributes so
                # ``getattr(handler, route_name)`` returns the original ``(request)``
                # callable (not a method bound to ``self``), matching the dispatch
                # contract used by the server adapters.
                for route_name, func in app_funcs.items():
                    setattr(self, route_name, func)

        # Merge the programmatic routes into the class-level registry that
        # RouteRegistryMixin built from any inherited ``@route`` methods.
        merged_routes = dict(getattr(ApplicationHandler, '_routes', {}))
        merged_routes.update(app_routes)
        ApplicationHandler._routes = merged_routes

        return SLDKWebServer(
            app=self.sldk_app,
            handler_class=ApplicationHandler,
            socket_pool=socket_pool,
            static_dir=static_dir,
        )


def create_web_server(
    app: Any = None,
    handler_class: Optional[type] = None,
    socket_pool: Any = None,
    static_dir: Optional[str] = None,
) -> SLDKWebServer:
    """Create an SLDK web server instance.

    Args:
        app: SLDK application instance
        handler_class: Custom handler class
        socket_pool: Socket pool (CircuitPython only)
        static_dir: Directory for static files

    Returns:
        SLDKWebServer instance
    """
    return SLDKWebServer(
        app=app,
        handler_class=handler_class,
        socket_pool=socket_pool,
        static_dir=static_dir,
    )


async def start_web_server(
    app: Any = None,
    handler_class: Optional[type] = None,
    socket_pool: Any = None,
    static_dir: Optional[str] = None,
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> Optional[SLDKWebServer]:
    """Start an SLDK web server.

    Args:
        app: SLDK application instance
        handler_class: Custom handler class
        socket_pool: Socket pool (CircuitPython only)
        static_dir: Directory for static files
        host: Host to bind to
        port: Port to bind to

    Returns:
        SLDKWebServer instance if successful, None otherwise
    """
    server = create_web_server(app, handler_class, socket_pool, static_dir)
    if await server.start(host, port):
        return server
    else:
        return None