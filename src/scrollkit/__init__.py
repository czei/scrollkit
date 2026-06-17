"""ScrollKit - LED Matrix Display Framework for CircuitPython and Desktop.

A lightweight framework for building scrolling LED matrix applications
that work on both CircuitPython hardware and desktop simulators.
"""

__version__ = "0.1.0"

from scrollkit.display.display_interface import DisplayInterface
from scrollkit.display.display_factory import create_display, is_circuitpython, is_dev_mode
from scrollkit.display.message_queue import MessageQueue
from scrollkit.config.settings_manager import SettingsManager
from scrollkit.network.http_client import HttpClient
from scrollkit.utils.error_handler import ErrorHandler
from scrollkit.utils.timer import Timer

# GenericDisplay imports SLDK which may not be installed on desktop
try:
    from scrollkit.display.generic_display import GenericDisplay
except ImportError:
    GenericDisplay = None

__all__ = [
    'DisplayInterface',
    'GenericDisplay',
    'create_display',
    'is_circuitpython',
    'is_dev_mode',
    'MessageQueue',
    'SettingsManager',
    'HttpClient',
    'ErrorHandler',
    'Timer',
]
