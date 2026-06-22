"""SLDK exception hierarchy.

All exceptions are plain Exception subclasses for CircuitPython compatibility.
Use specific exception types to enable precise error handling.
"""


class SLDKError(Exception):
    """Base exception for all SLDK errors."""


class DisplayError(SLDKError):
    """Display-related errors (initialization, rendering, hardware)."""


class ContentError(SLDKError):
    """Content-related errors (invalid data, rendering failures)."""


class ConfigurationError(SLDKError):
    """Configuration and settings errors."""


class NetworkError(SLDKError):
    """Network connectivity and request errors."""


class WebServerError(SLDKError):
    """Web server errors (startup, routing, request handling)."""


class OTAError(SLDKError):
    """OTA update errors."""


class DeploymentError(SLDKError):
    """Deployment and packaging errors."""


class SimulatorError(SLDKError):
    """Simulator-related errors."""


class FeasibilityError(SLDKError):
    """A modeled frame busts the device time or RAM budget under strict mode.

    Raised only by the desktop simulator's ``PerformanceManager`` when strict
    hardware simulation is enabled and a frame's modeled cost exceeds the
    per-frame budget (steady-state median or the single-frame transient ceiling)
    or modeled peak RAM exceeds the device's usable RAM. Never raised on
    CircuitPython, where the timing model is a no-op. Defined here (not in the
    simulator) so the harness, tests, and callers can import it without pulling
    in the simulator.
    """


class ResourceNotFoundError(SLDKError):
    """Resource not found (files, configuration, devices)."""


class UpdateError(SLDKError):
    """Update process errors."""


class ValidationError(SLDKError):
    """Data validation errors."""