#!/usr/bin/env python3
"""Regression tests for the CircuitPython-safe ``@route`` registry.

CircuitPython functions have no ``__dict__`` and cannot carry arbitrary attributes,
so route metadata must NOT be stored as a function attribute (``func._route_info``).
Instead it lives in a class-level ``_routes`` registry populated by
``RouteRegistryMixin.__init_subclass__``.

These tests pin that contract so the bug can't regress on CPython (where assigning
a function attribute silently works, which is why the original bug shipped):
  - no route metadata is stored on the function object;
  - decorated routes resolve via the class-level registry;
  - inherited / overridden / multiply-inherited routes all end up in the registry.
"""

import pytest

from scrollkit.web.adapters import route, _iter_routes, MockResponse, MockRequest
from scrollkit.web.handlers import WebHandler, StaticFileHandler, APIHandler


class TestNoFunctionAttribute:
    """The function object must stay pristine (CircuitPython has no __dict__)."""

    def test_library_routes_not_tagged_on_function(self):
        # The decorator must NOT set ``_route_info`` (or any attr) on the function.
        assert not hasattr(WebHandler.route_index, '_route_info')
        assert not hasattr(StaticFileHandler.route_css, '_route_info')
        assert not hasattr(StaticFileHandler.route_static, '_route_info')
        assert not hasattr(StaticFileHandler.route_favicon, '_route_info')
        assert not hasattr(APIHandler.route_api_status, '_route_info')

    def test_subclass_routes_not_tagged_on_function(self):
        class Handler(StaticFileHandler):
            @route("/")
            def route_index(self, request):
                return MockResponse("index")

            @route("/settings", methods=["GET", "POST"])
            def route_settings(self, request):
                return MockResponse("settings")

        assert not hasattr(Handler.route_index, '_route_info')
        assert not hasattr(Handler.route_settings, '_route_info')


class TestClassLevelRegistry:
    """Route metadata lives on the class, keyed by method name."""

    def test_base_registry_populated(self):
        assert WebHandler._routes == {
            'route_index': {'path': '/', 'methods': ['GET']},
        }

    def test_registry_keyed_by_method_name(self):
        assert StaticFileHandler._routes['route_css']['path'] == '/style.css'
        assert StaticFileHandler._routes['route_css']['methods'] == ['GET']

    def test_methods_list_preserved(self):
        class Handler(WebHandler):
            @route("/settings", methods=["GET", "POST"])
            def route_settings(self, request):
                return MockResponse("settings")

        assert Handler._routes['route_settings']['methods'] == ['GET', 'POST']


class TestInheritance:
    """Subclasses get the union of their own routes and their bases' routes."""

    def test_subclass_inherits_base_routes(self):
        # StaticFileHandler adds three routes on top of WebHandler's route_index.
        assert set(StaticFileHandler._routes) == {
            'route_index', 'route_static', 'route_css', 'route_favicon',
        }

    def test_subclass_adds_and_overrides(self):
        class ConfigHandler(StaticFileHandler):
            @route("/")  # overrides the inherited route_index (still path '/')
            def route_index(self, request):
                return MockResponse("config-index")

            @route("/settings", methods=["GET", "POST"])
            def route_settings(self, request):
                return MockResponse("settings")

            @route("/update", methods=["POST"])
            def route_update(self, request):
                return MockResponse("update")

        assert set(ConfigHandler._routes) == {
            'route_index', 'route_static', 'route_css', 'route_favicon',
            'route_settings', 'route_update',
        }
        # The override keeps path '/', and the added routes carry their methods.
        assert ConfigHandler._routes['route_index']['path'] == '/'
        assert ConfigHandler._routes['route_settings']['methods'] == ['GET', 'POST']
        assert ConfigHandler._routes['route_update']['methods'] == ['POST']

    def test_multiple_inheritance_keeps_all_routes(self):
        # A handler inheriting from two route-bearing bases must keep routes from
        # BOTH, not just the first in the MRO.
        class Composite(StaticFileHandler, APIHandler):
            pass

        assert 'route_css' in Composite._routes          # from StaticFileHandler
        assert 'route_api_status' in Composite._routes    # from APIHandler
        assert 'route_index' in Composite._routes          # from common WebHandler base


class TestDispatchResolves:
    """Routes still resolve through the dispatch helper on CPython."""

    def _make_handler(self):
        class ConfigHandler(StaticFileHandler):
            @route("/")
            def route_index(self, request):
                return MockResponse("INDEX")

            @route("/settings", methods=["GET", "POST"])
            def route_settings(self, request):
                return MockResponse("SETTINGS:" + request.method)

        # __new__ avoids needing a real adapter for __init__.
        return ConfigHandler.__new__(ConfigHandler)

    def test_iter_routes_yields_registry_entries(self):
        handler = self._make_handler()
        names = {name for name, _ in _iter_routes(handler)}
        assert names == set(type(handler)._routes)

    def test_decorated_routes_dispatch(self):
        handler = self._make_handler()

        class _StubAdapter:
            def parse_query_params(self, query):
                return {}

            def parse_form_data(self, body):
                return {}

        adapter = _StubAdapter()

        def resolve(method, path):
            """Return the bound method for (method, path), or None — mirrors the
            dispatch loop in the server adapters without executing the body."""
            for name, info in _iter_routes(handler):
                if path == info['path'] and method in info.get('methods', ['GET']):
                    return getattr(handler, name)
            return None

        def dispatch(method, path):
            bound = resolve(method, path)
            if bound is None:
                return None
            return bound(MockRequest(method, path, '', None, adapter))

        # Own routes execute and return the expected body.
        assert dispatch('GET', '/').body == 'INDEX'
        assert dispatch('POST', '/settings').body == 'SETTINGS:POST'
        # Inherited route from StaticFileHandler still resolves to a callable
        # (don't execute its file-serving body — no real adapter/static dir here).
        assert callable(resolve('GET', '/style.css'))
        # Unknown path does not resolve.
        assert resolve('GET', '/nope') is None
