"""SLDK Web Framework."""

from __future__ import annotations

from typing import List

from .server import SLDKWebServer
from .handlers import WebHandler, StaticFileHandler, APIHandler
from .adapters import route, ServerAdapter, create_server_adapter
from .templates import HTMLBuilder, TemplateEngine
from .forms import FormBuilder

__all__: List[str] = [
    'SLDKWebServer',
    'WebHandler',
    'StaticFileHandler',
    'APIHandler',
    'route',
    'ServerAdapter',
    'create_server_adapter',
    'HTMLBuilder',
    'TemplateEngine',
    'FormBuilder'
]