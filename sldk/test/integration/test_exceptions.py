"""Integration tests for SLDK exception hierarchy.

Tests that the exception hierarchy works correctly across the entire framework.
"""

from __future__ import annotations

import pytest

from sldk.exceptions import (
    SLDKError,
    DisplayError,
    ContentError,
    ConfigurationError,
    NetworkError,
    WebServerError,
    OTAError,
    DeploymentError,
    SimulatorError,
    ResourceNotFoundError,
    UpdateError,
    ValidationError,
)


class TestExceptionHierarchy:
    """Test that all exceptions form a proper hierarchy."""

    def test_all_exceptions_are_sldk_errors(self):
        """All custom exceptions should subclass SLDKError."""
        exceptions = [
            DisplayError,
            ContentError,
            ConfigurationError,
            NetworkError,
            WebServerError,
            OTAError,
            DeploymentError,
            SimulatorError,
            ResourceNotFoundError,
            UpdateError,
            ValidationError,
        ]
        for exc in exceptions:
            assert issubclass(exc, SLDKError), f"{exc.__name__} does not subclass SLDKError"

    def test_all_exceptions_are_exceptions(self):
        """SLDKError and all subclasses should be Exception subclasses."""
        exceptions = [
            SLDKError,
            DisplayError,
            ContentError,
            ConfigurationError,
            NetworkError,
            WebServerError,
            OTAError,
            DeploymentError,
            SimulatorError,
            ResourceNotFoundError,
            UpdateError,
            ValidationError,
        ]
        for exc in exceptions:
            assert issubclass(exc, Exception), f"{exc.__name__} does not subclass Exception"

    def test_exceptions_can_be_raised_and_caught(self):
        """All exceptions should work in try/except blocks."""
        for exc_type, msg in [
            (SLDKError, "base error"),
            (DisplayError, "display failed"),
            (ContentError, "bad content"),
            (ConfigurationError, "bad config"),
            (NetworkError, "network down"),
            (WebServerError, "server error"),
            (OTAError, "ota failed"),
            (DeploymentError, "deploy failed"),
            (SimulatorError, "sim error"),
            (ResourceNotFoundError, "not found"),
            (UpdateError, "update failed"),
            (ValidationError, "invalid"),
        ]:
            try:
                raise exc_type(msg)
            except SLDKError as e:
                assert str(e) == msg
                assert isinstance(e, exc_type)

    def test_catch_parent_catches_child(self):
        """Catching SLDKError should catch all child exceptions."""
        for exc_type in [DisplayError, ContentError, NetworkError, OTAError]:
            try:
                raise exc_type("test")
            except SLDKError:
                pass  # Should not raise

    def test_exceptions_carry_args(self):
        """Exceptions should pass through args correctly."""
        error = SLDKError("message", 42, {"key": "value"})
        assert error.args == ("message", 42, {"key": "value"})

    def test_catch_generic_exception(self):
        """All SLDK errors should be catchable as generic Exception."""
        try:
            raise DisplayError("hardware failure")
        except Exception as e:
            assert isinstance(e, DisplayError)
            assert str(e) == "hardware failure"


class TestPackageExports:
    """Test that exceptions are properly exported from the package."""

    def test_exceptions_exported_from_package(self):
        """All exception classes should be importable from sldk."""
        from sldk import (
            SLDKError, DisplayError, ContentError, ConfigurationError,
            NetworkError, WebServerError, OTAError, DeploymentError,
            SimulatorError, ResourceNotFoundError, UpdateError, ValidationError,
        )
        assert SLDKError is not None
        assert DisplayError is not None
        assert ContentError is not None
        assert ConfigurationError is not None
        assert NetworkError is not None

    def test_module_import_via_init(self):
        """The exceptions module should be importable directly."""
        import sldk.exceptions
        assert hasattr(sldk.exceptions, 'SLDKError')
        assert hasattr(sldk.exceptions, 'DisplayError')
        assert hasattr(sldk.exceptions, 'ContentError')