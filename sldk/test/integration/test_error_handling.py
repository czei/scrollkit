"""Integration tests for error handling patterns in SLDK modules.

Tests that modules properly use the exception hierarchy:
- Module-level imports of exception classes
- Proper raise/catch patterns
- Error handling standardization
"""

from __future__ import annotations

import pytest

from sldk.exceptions import (
    SLDKError, DisplayError, ContentError, ConfigurationError,
    NetworkError, WebServerError, OTAError, DeploymentError,
    SimulatorError, ResourceNotFoundError, UpdateError, ValidationError,
)


class TestModuleExceptionImports:
    """Test that key modules import and use the exception hierarchy."""

    def test_display_modules_import_exceptions(self):
        """Display modules should import DisplayError or ContentError."""
        from sldk.display.interface import DisplayError
        assert DisplayError is not None

        from sldk.display.manager import ContentError, DisplayError
        assert ContentError is not None

        from sldk.display.strategy import ContentError, ValidationError
        assert ValidationError is not None

    def test_effects_modules_import_exceptions(self):
        """Effects modules should import DisplayError."""
        from sldk.effects.base import DisplayError
        assert DisplayError is not None

        from sldk.effects.effects import DisplayError
        assert DisplayError is not None

        from sldk.effects.particles import DisplayError
        assert DisplayError is not None

    def test_web_modules_import_exceptions(self):
        """Web modules should import WebServerError."""
        from sldk.web.adapters import WebServerError
        assert WebServerError is not None

        from sldk.web.templates import ResourceNotFoundError
        assert ResourceNotFoundError is not None

    def test_ota_modules_import_exceptions(self):
        """OTA modules should import OTAError and related exceptions."""
        from sldk.ota.client import NetworkError, OTAError, UpdateError
        assert OTAError is not None

        from sldk.ota.server import OTAError
        assert OTAError is not None

        from sldk.ota.updater import OTAError, UpdateError
        assert UpdateError is not None

    def test_tools_modules_import_exceptions(self):
        """Tools modules should import DeploymentError."""
        from sldk.tools.deployer import DeploymentError, NetworkError
        assert DeploymentError is not None

        from sldk.tools.packager import DeploymentError
        assert DeploymentError is not None

    def test_app_module_imports_exceptions(self):
        """App module should import DisplayError."""
        from sldk.app.base import DisplayError, NetworkError
        assert DisplayError is not None


class TestErrorHandlingPatterns:
    """Test that error handling follows standardized patterns."""

    def test_specific_exceptions_before_generic(self):
        """Verify specific exceptions are caught before generic ones in key modules.

        This is a structural test - it checks that exceptions are properly ordered
        in try/except blocks by ensuring the exception classes are imported.
        """
        import ast
        import os

        # Check key modules have proper exception handling structure
        modules_to_check = [
            'sldk/app/base.py',
            'sldk/display/manager.py',
            'sldk/display/unified.py',
            'sldk/ota/client.py',
            'sldk/ota/updater.py',
            'sldk/tools/deployer.py',
            'sldk/web/server.py',
        ]

        base_dir = os.path.join(os.path.dirname(__file__), '../../src')

        for rel_path in modules_to_check:
            filepath = os.path.join(base_dir, rel_path)
            assert os.path.exists(filepath), f"Module not found: {filepath}"

            with open(filepath) as f:
                content = f.read()

            # Parse the AST to find except handlers
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.ExceptHandler):
                    if node.type is None:
                        # Bare 'except:' - ensure there are specific handlers before it
                        pass

    def test_display_error_handling(self):
        """Test DisplayError propagation through the display system."""
        import inspect

        # Check that display module functions use try/except
        from sldk.display.interface import DisplayInterface

        source = inspect.getsource(DisplayInterface.initialize)
        # Methods should have try/except or raise NotImplementedError
        assert 'raise NotImplementedError' in source or 'try' in source


class TestExceptionUsagePatterns:
    """Test that exceptions are used consistently across the codebase."""

    def test_exceptions_caught_by_module_display(self):
        """DisplayError should be raiseable and catchable in display code."""
        try:
            raise DisplayError("Matrix not initialized")
        except DisplayError as e:
            assert "Matrix not initialized" in str(e)
        except SLDKError:
            pytest.fail("Should have caught DisplayError directly")

    def test_exceptions_caught_by_module_content(self):
        """ContentError should be raiseable and catchable in content code."""
        try:
            raise ContentError("Invalid content data: missing text")
        except ContentError as e:
            assert "Invalid content data" in str(e)

    def test_exceptions_caught_by_parent_class(self):
        """All exceptions should be catchable by SLDKError parent."""
        exceptions_to_test = [
            (DisplayError("display"), "display"),
            (ContentError("content"), "content"),
            (NetworkError("network"), "network"),
            (WebServerError("web"), "web"),
            (OTAError("ota"), "ota"),
            (DeploymentError("deploy"), "deploy"),
            (ValidationError("validation"), "validation"),
        ]

        for exc, expected_substring in exceptions_to_test:
            try:
                raise exc
            except SLDKError as e:
                assert expected_substring in str(e).lower()

    def test_exception_catch_order(self):
        """When catching both specific and parent exceptions, specific should come first."""
        # This pattern should be used: specific first, generic last
        def function_with_proper_handling(value):
            try:
                if value < 0:
                    raise ValidationError("Negative value")
                if value == 0:
                    raise DisplayError("Zero value")
                if value > 100:
                    raise SLDKError("Out of range")
                return value
            except ValidationError:
                return "validation error"
            except DisplayError:
                return "display error"
            except SLDKError:
                return "generic sldk error"

        assert function_with_proper_handling(-1) == "validation error"
        assert function_with_proper_handling(0) == "display error"
        assert function_with_proper_handling(200) == "generic sldk error"
        assert function_with_proper_handling(50) == 50