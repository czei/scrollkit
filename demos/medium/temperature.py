#!/usr/bin/env python3
"""ScrollKit demo (MEDIUM): live temperature from a public API.

Fetches the current temperature from open-meteo (https://open-meteo.com) — a
free, no-API-key public source — and scrolls it across the simulated LED matrix,
refreshing every 5 minutes.

Run on desktop:

    PYTHONPATH=src python demos/medium/temperature.py

Data source: open-meteo /v1/forecast (no API key required).
The same code runs on a MatrixPortal S3; there HttpClient uses adafruit_requests,
on desktop it uses urllib.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

import asyncio

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import ScrollingText
from scrollkit.network.http_client import HttpClient

# Berlin. Change latitude/longitude for your location. No API key needed.
URL = ("https://api.open-meteo.com/v1/forecast"
       "?latitude=52.52&longitude=13.41&current=temperature_2m")


class TemperatureApp(ScrollKitApp):
    """Refreshes a temperature reading every 5 minutes and scrolls it."""

    def __init__(self):
        super().__init__(enable_web=False, update_interval=300)
        self.http = HttpClient()
        self.text = "Fetching temperature..."

    async def create_display(self):
        try:
            from scrollkit.display.simulator import SimulatorDisplay
            return SimulatorDisplay(width=64, height=32)
        except ImportError:
            return await super().create_display()

    async def setup(self):
        # setup() runs after the display is initialized -> open the window here.
        if hasattr(self.display, "create_window"):
            await self.display.create_window("ScrollKit - Temperature (medium)")
        # Show a placeholder immediately; update_data() replaces it.
        self.content_queue.add(ScrollingText(self.text, y=12, color=0x00AAFF))
        await self.update_data()

    async def update_data(self):
        """Called every update_interval seconds by the data process.

        On CircuitPython this HTTP call blocks the event loop briefly; the
        display shows the previous frame until it returns (see FR-029).
        """
        try:
            resp = await self.http.get(URL)
            data = resp.json()
            temp = data["current"]["temperature_2m"]
            self.text = "Berlin: {} C".format(temp)
        except Exception as e:  # network/parse failure shouldn't kill the display
            self.text = "Temp unavailable"
            print("temperature fetch failed:", e)

        # Replace the queued content with the fresh reading.
        self.content_queue.clear()
        self.content_queue.add(ScrollingText(self.text, y=12, color=0xFFAA00))


if __name__ == "__main__":
    asyncio.run(TemperatureApp().run())
