"""SLDK - Scrolling LED Development Kit.

A flexible framework for LED matrix displays with progressive complexity.
"""

__version__ = "0.5.0"

# Progressive API - start simple, grow complex
from .app.minimal import MinimalLEDApp
from .app.base import SLDKApp

# Content classes for advanced usage
from .display.content import ScrollingText, StaticText

# Exception hierarchy
from .exceptions import (
    SLDKError, DisplayError, ContentError, ConfigurationError,
    NetworkError, WebServerError, OTAError, DeploymentError,
    SimulatorError, ResourceNotFoundError, UpdateError, ValidationError,
)

__all__ = [
    'MinimalLEDApp',
    'SLDKApp', 
    'ScrollingText',
    'StaticText',
    'SLDKError',
    'DisplayError',
    'ContentError',
    'ConfigurationError',
    'NetworkError',
    'WebServerError',
    'OTAError',
    'DeploymentError',
    'SimulatorError',
    'ResourceNotFoundError',
    'UpdateError',
    'ValidationError',
]