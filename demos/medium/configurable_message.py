#!/usr/bin/env python3
"""ScrollKit demo (MEDIUM): browser-configurable scrolling message.

Demonstrates the auto-generating settings web UI.  The base class pre-registers
``brightness_scale``, ``scroll_speed``, and ``default_color``; the app adds one
more: ``message``.  Saving the form in the browser calls ``on_settings_changed()``
and the display updates immediately — no restart needed.

Run on desktop:

    PYTHONPATH=src python demos/medium/configurable_message.py

Then open http://localhost:8080 in a browser.

On hardware the web server listens on port 80; open http://<device-ip>/ from any
device on the same network.  No extra code is needed — the base class wires
everything up automatically once ``define()`` has been called.
"""

import sys
import os

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    import _demo_support as _support
except (AttributeError, ImportError):
    _support = None

import asyncio

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import ScrollingText


class ConfigurableMessageApp(ScrollKitApp):
    """Scrolling message app with browser-editable settings."""

    def __init__(self):
        super().__init__(enable_web=True, update_interval=3600)
        # Base already registers: brightness_scale, scroll_speed, default_color.
        # Add one app-specific setting:
        self.settings.define("message", "Hello ScrollKit", label="Message")

    async def create_display(self):
        if _support is not None:
            return _support.simulator_display(getattr(self, "opts", None))
        try:
            from scrollkit.display.simulator import SimulatorDisplay
            return SimulatorDisplay(width=64, height=32)
        except ImportError:
            return await super().create_display()

    async def setup(self):
        if hasattr(self.display, "create_window"):
            await self.display.create_window("ScrollKit - Configurable Message (medium)")
        self._rebuild()

    def _rebuild(self):
        """Rebuild display content from current settings."""
        msg = self.settings.get("message", "Hello ScrollKit")
        self.content_queue.clear()
        self.content_queue.add(ScrollingText(msg, y=12))  # color + speed from library settings

    def on_settings_changed(self):
        """Rebuild display immediately after the browser saves new settings."""
        self._rebuild()


if __name__ == "__main__":
    if _support is not None:
        _support.main(ConfigurableMessageApp(),
                      "ScrollKit configurable-message demo (medium)")
    else:
        asyncio.run(ConfigurableMessageApp().run())
