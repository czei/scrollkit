# ScrollKit Quickstart

## Prerequisites

```bash
pip install pygame  # required for desktop simulator
cd "ScrollKit Library"
```

---

## Tutorial 1: Hello World (Easy)

Create `demos/easy/hello_world.py`:

```python
import asyncio
import sys
sys.path.insert(0, 'src')

from scrollkit.app.minimal import MinimalLEDApp

app = MinimalLEDApp()
app.scroll_text("Hello, World!", color=(0, 255, 128))
```

Run it:
```bash
PYTHONPATH=src python demos/easy/hello_world.py
```

A pygame window opens showing "Hello, World!" scrolling across a 64×32 LED matrix.

---

## Tutorial 2: Live Public Data with Periodic Refresh (Medium)

Fetches the current temperature from **open-meteo** (no API key required) and scrolls it across the display, refreshing every 5 minutes.

Create `demos/medium/temperature.py`:

```python
import asyncio
import sys
sys.path.insert(0, 'src')

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import ScrollingText
from scrollkit.display.strategy import Priority
from scrollkit.network.http_client import HttpClient

# Berlin; change latitude/longitude for your location. No API key needed.
URL = ("https://api.open-meteo.com/v1/forecast"
       "?latitude=52.52&longitude=13.41&current=temperature_2m")

class TemperatureApp(ScrollKitApp):
    def __init__(self):
        super().__init__(update_interval=300.0, enable_web=False)
        self.http = HttpClient()
        self.text = "Loading temperature..."

    async def update_data(self):
        # On CircuitPython this HTTP call blocks the loop — the framework
        # shows the last frame until it returns. See FR-029.
        resp = await self.http.get(URL)
        data = resp.json()
        temp = data["current"]["temperature_2m"]
        self.text = "Berlin: {} C".format(temp)

    async def prepare_display_content(self):
        return ScrollingText(self.text, color=(0, 200, 255), priority=Priority.NORMAL)

if __name__ == "__main__":
    asyncio.run(TemperatureApp().run())
```

Run it:
```bash
PYTHONPATH=src python demos/medium/temperature.py
```

The display scrolls the current temperature and refreshes every 5 minutes. The exact same code runs on the MatrixPortal S3 — `HttpClient` uses `adafruit_requests` there and `urllib`/`requests` on desktop.

---

## Tutorial 3: Full App with Web Config, Effects, and OTA (Hard)

Create `demos/hard/full_app.py`:

```python
import asyncio
import sys
sys.path.insert(0, 'src')

from scrollkit.app.base import ScrollKitApp
from scrollkit.config.settings_manager import SettingsManager
from scrollkit.display.content import ScrollingText, StaticText
from scrollkit.display.strategy import Priority
from scrollkit.effects.effects import EffectsEngine
from scrollkit.network.http_client import HttpClient
from scrollkit.ota.client import OTAClient

GITHUB_MANIFEST_URL = "https://raw.githubusercontent.com/myorg/myapp/releases"

# A "bunch of stocks" — here, crypto tickers from CoinGecko (no API key required).
COINS = ["bitcoin", "ethereum", "solana", "cardano", "dogecoin",
         "polkadot", "litecoin", "chainlink", "stellar", "monero"]
CHUNK_SIZE = 3  # fetch only a few per request so each blocking call stays short

class FullApp(ScrollKitApp):
    def __init__(self):
        super().__init__(update_interval=300.0, enable_web=True)
        self.settings = SettingsManager(
            filename="settings.json",
            defaults={"message": "Welcome!", "color": "green"}
        )
        self.ota = OTAClient(
            update_server_url=GITHUB_MANIFEST_URL,
            current_version="1.0.0"
        )
        self.http = HttpClient()
        self.effects = EffectsEngine(self.display)
        self.messages = []

    async def setup(self):
        # Check for OTA updates on startup
        has_update, result = self.ota.check_for_updates()
        if has_update:
            print(f"Update available: {result.version}")
            self.ota.download_update(result)
            self.ota.apply_update()  # reboots on CircuitPython

    async def update_data(self):
        # Fetch a bunch of prices WITHOUT locking the screen.
        # adafruit_requests is synchronous: ONE big request that returns all 10
        # prices would block the display loop for the entire transfer, freezing
        # the scroll. Instead we break the work into sizable chunks — each chunk
        # is one SHORT blocking call — and yield between chunks so the display
        # renders a frame. Slower overall, but the scroll never locks up.
        prices = {}
        for i in range(0, len(COINS), CHUNK_SIZE):
            chunk = COINS[i:i + CHUNK_SIZE]
            url = ("https://api.coingecko.com/api/v3/simple/price"
                   "?ids=" + ",".join(chunk) + "&vs_currencies=usd")
            resp = await self.http.get(url)   # short blocking call (a few items)
            prices.update(resp.json())
            await asyncio.sleep(0)            # let the display render a frame
        self.messages = ["{}: ${}".format(c, prices.get(c, {}).get("usd", "?"))
                         for c in COINS]

    async def prepare_display_content(self):
        if not self.messages:
            return StaticText("Loading...")

        # Rotate through messages
        text = self.messages[0]
        self.messages = self.messages[1:] + [self.messages[0]]

        # Play a random transition effect between messages
        await self.effects.play_transition("fade")

        color_name = self.settings.get("color", "white")
        color_map = {"green": (0, 255, 0), "white": (255, 255, 255), "red": (255, 0, 0)}
        color = color_map.get(color_name, (255, 255, 255))

        return ScrollingText(text, color=color, priority=Priority.NORMAL)

if __name__ == "__main__":
    asyncio.run(FullApp().run())
```

Run it:
```bash
PYTHONPATH=src python demos/hard/full_app.py
```

- Open `http://localhost:8080` in a browser to see the configuration interface.
- Changing the `message` or `color` setting takes effect on the next content cycle.
- The app checks GitHub for OTA updates at startup.
- Effects (fade transition) play between messages.
- Prices are fetched in chunks of 3 with `await asyncio.sleep(0)` between chunks, so the display keeps scrolling smoothly instead of freezing during the network calls. This is the key workaround for CircuitPython's blocking HTTP library: many short requests beat one long one when a scroll has to stay alive.

---

## Running on CircuitPython Hardware

1. Connect your MatrixPortal S3 via USB.
2. Copy `src/` to the CIRCUITPY drive (or run `make copy_to_circuitpy`).
3. Edit `settings.json` with your WiFi credentials.
4. The same app code runs unchanged.

`UnifiedDisplay` auto-detects the runtime: it uses the real `displayio` hardware backend on CircuitPython and the pygame simulator on desktop — no `if/else` needed in your app code.

---

## Package Map

| What you want | Import |
|--------------|--------|
| Simple text display | `from scrollkit.app.minimal import MinimalLEDApp` |
| Full async app framework | `from scrollkit.app.base import ScrollKitApp` |
| Display directly | `from scrollkit.display.unified import UnifiedDisplay` |
| Content types | `from scrollkit.display.content import StaticText, ScrollingText` |
| Priority levels | `from scrollkit.display.strategy import Priority` |
| Effects engine | `from scrollkit.effects.effects import EffectsEngine` |
| Web server | `from scrollkit.web.server import ScrollKitWebServer` |
| OTA updates | `from scrollkit.ota.client import OTAClient` |
| Settings persistence | `from scrollkit.config.settings_manager import SettingsManager` |
| WiFi management | `from scrollkit.network.wifi_manager import WiFiManager` |
| HTTP client | `from scrollkit.network.http_client import HttpClient` |
| Error logging | `from scrollkit.utils.error_handler import ErrorHandler` |
