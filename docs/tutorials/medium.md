# Medium: Live Data with Periodic Refresh

Fetch the current temperature from a free, no-API-key public source
([open-meteo](https://open-meteo.com)) and scroll it, refreshing every 5 minutes.

Full source: [`demos/medium/temperature.py`](https://github.com/Czeiszperger/scrollkit/blob/main/demos/medium/temperature.py)

```python
import asyncio
from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import ScrollingText
from scrollkit.network.http_client import HttpClient

URL = ("https://api.open-meteo.com/v1/forecast"
       "?latitude=52.52&longitude=13.41&current=temperature_2m")


class TemperatureApp(ScrollKitApp):
    def __init__(self):
        super().__init__(enable_web=False, update_interval=300)
        self.http = HttpClient()
        self.text = "Fetching temperature..."

    async def setup(self):
        self.content_queue.add(ScrollingText(self.text, y=12, color=0x00AAFF))
        await self.update_data()

    async def update_data(self):
        try:
            resp = await self.http.get(URL)
            temp = resp.json()["current"]["temperature_2m"]
            self.text = "Berlin: {} C".format(temp)
        except Exception as e:
            self.text = "Temp unavailable"
            print("fetch failed:", e)

        self.content_queue.clear()
        self.content_queue.add(ScrollingText(self.text, y=12, color=0xFFAA00))
```

Run it:

```bash
PYTHONPATH=src python demos/medium/temperature.py
```

## What's new

- **`update_data()`** is the periodic data hook. The framework calls it every
  `update_interval` seconds (300 here) on its own async task — only if there's
  enough free RAM on the device.
- **`HttpClient`** abstracts the platform: on CircuitPython it uses
  `adafruit_requests`; on desktop it falls back to `urllib`. Same `await
  http.get(url)` call, same `.json()` response either way.
- We **`clear()`** the queue and add fresh content each refresh, so the display
  always shows the latest reading.

!!! warning "Blocking HTTP on CircuitPython"
    `adafruit_requests` is synchronous — the call blocks the event loop while it
    runs, so the scroll pauses briefly during a fetch. For a single small request
    that's fine. When you need *lots* of data, see the
    [chunked-fetch technique](hard.md) in the hard tutorial.

Next: [Hard — the full app](hard.md).
