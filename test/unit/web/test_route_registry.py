#!/usr/bin/env python3
"""Regression tests for the CircuitPython-safe ``@route`` registry.

Two distinct CircuitPython limitations broke ``@route`` on-device, and NEITHER is
catchable by this CPython simulator suite at runtime — CPython tolerates both — so
the grep-guard (``TestSourceHasNoCircuitPythonTraps``) is the real safety net:

  1. CircuitPython plain functions have no ``__dict__`` — ``func._route_info = ...``
     raised ``can't set attribute``. Fixed by moving metadata to a class-level
     ``_routes`` registry populated by ``RouteRegistryMixin.__init_subclass__``.
  2. CircuitPython plain functions do not even expose ``func.__name__`` — reading it
     raised ``'function' object has no attribute '__name__'``. Fixed by wrapping the
     function in a ``_RouteMarker`` instance and deriving the method name from the
     class-namespace key instead of from the function.

These tests pin that contract:
  - the decorator returns a ``_RouteMarker`` and never mutates / inspects the function;
  - no route metadata is stored on the function object;
  - decorated routes resolve via the class-level registry;
  - inherited / overridden / multiply-inherited routes all end up in the registry;
  - the source contains no ``func.__name__`` read nor function-attribute assignment.
"""

import os
import re

import pytest

from scrollkit.web import adapters as adapters_mod
from scrollkit.web.adapters import (
    route, _iter_routes, _RouteMarker, MockResponse, MockRequest,
)
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


class TestMarkerNeverTouchesFunction:
    """The decorator must wrap, not inspect or mutate, the function.

    CircuitPython functions expose neither ``__dict__`` (can't set attributes) nor
    ``__name__`` (can't read it), so the decorator must do neither.
    """

    def test_decorator_returns_marker_not_function(self):
        def handler(self, request):
            return MockResponse("x")

        marker = route("/x", methods=["GET"])(handler)
        assert isinstance(marker, _RouteMarker)
        assert marker.func is handler
        assert marker.path == "/x"
        assert marker.methods == ["GET"]

    def test_class_attribute_is_real_function_after_construction(self):
        # The marker is consumed by __init_subclass__ and replaced by the function.
        assert not isinstance(getattr(WebHandler, "route_index"), _RouteMarker)
        assert callable(WebHandler.route_index)

    def test_method_name_comes_from_namespace_not_func_name(self):
        # Simulate a CircuitPython function: no ``__name__`` AND attribute-assignment
        # raises. If the machinery read ``func.__name__`` or set a func attribute,
        # registering this would raise. It must not.
        class _CpyFunc:
            __slots__ = ("_f",)  # no __dict__, so no arbitrary attributes

            def __init__(self, f):
                object.__setattr__(self, "_f", f)

            def __call__(self, *a, **k):
                return self._f(*a, **k)

            def __getattr__(self, name):  # __name__ etc. are absent
                raise AttributeError(name)

            def __setattr__(self, name, value):
                raise AttributeError("can't set attribute %r" % name)

        cpy = _CpyFunc(lambda self, request: MockResponse("CPY"))
        with pytest.raises(AttributeError):
            cpy.__name__  # confirm the stub really lacks __name__

        class Handler(WebHandler):
            route_cpy = route("/cpy")(cpy)

        assert "route_cpy" in Handler._routes
        assert Handler._routes["route_cpy"]["path"] == "/cpy"
        # name is the namespace key, not derived from the (absent) func __name__
        assert callable(getattr(Handler, "route_cpy"))


class TestSourceHasNoCircuitPythonTraps:
    """Grep-guard: the CPython suite can't catch these at runtime, so lint the source.

    Both failures (no ``__dict__``, no ``__name__``) shipped because CPython silently
    tolerates the offending pattern. This static check fails the build on the simulator
    if either trap is reintroduced into the route machinery.
    """

    def test_no_func_attribute_assignment_in_route_machinery(self):
        source = self._route_source()
        # e.g. ``func._route_info = ...`` / ``func.anything = ...`` — illegal on CP.
        offenders = re.findall(r"^\s*func\.[A-Za-z_]\w*\s*=", source, re.MULTILINE)
        assert not offenders, ("function-attribute assignment in route machinery: %r"
                               % offenders)

    def test_no_dunder_name_read_in_route_machinery(self):
        source = self._route_source_code_only()
        # ``func.__name__`` (or any ``.__name__`` read) is unavailable on CircuitPython.
        assert "__name__" not in source, (
            "route machinery reads __name__, which CircuitPython functions lack")

    # --- helpers ---------------------------------------------------------------
    def _route_source(self) -> str:
        path = adapters_mod.__file__
        with open(path, "r") as fh:
            return fh.read()

    def _route_source_code_only(self) -> str:
        """adapters.py source with comments and docstrings stripped.

        The fix's own comments legitimately *mention* ``__name__`` to explain why it
        is avoided; only executable code must be free of it.
        """
        raw = self._route_source()
        lines = []
        for line in raw.splitlines():
            code = line.split("#", 1)[0]  # drop line comments
            lines.append(code)
        code = "\n".join(lines)
        # Strip triple-quoted docstrings/strings.
        code = re.sub(r'"""[\s\S]*?"""', "", code)
        code = re.sub(r"'''[\s\S]*?'''", "", code)
        return code
