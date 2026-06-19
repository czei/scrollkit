#!/usr/bin/env python3
"""ScrollKit demo (HARD): an animated, multi-row live dashboard.

This is the showpiece. It fills the whole 64x32 matrix with a dashboard that
*looks* alive — an animated rainbow intro, then four rows updating at once:

    Row 0 : CRYPTO LIVE   (a flowing, per-letter rainbow title)
    Row 1 : Berlin 21C    (live temperature, colored cold->hot)
    Row 2 : ^ BTC 64000   (a rotating coin, green/up or red/down)
    Row 3 : <-- scrolling ticker of every coin's price -->

Under the hood it also shows the library's depth:
  - TWO public, no-API-key data sources (CoinGecko prices + open-meteo weather)
  - the CHUNKED-FETCH workaround for CircuitPython's blocking HTTP library
  - the effects engine (rainbow color helper)
  - a configuration web server (enable_web=True)
  - an OTA update check at startup

Run on desktop:

    PYTHONPATH=src python demos/hard/crypto_dashboard.py

Data sources: CoinGecko /simple/price and open-meteo /v1/forecast (no API key).
"""

import sys
import os

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
except AttributeError:
    pass  # CircuitPython has no os.path; scrollkit is already on the path (/lib)

import asyncio

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import DisplayContent
from scrollkit.effects.effects import EffectsEngine
from scrollkit.network.http_client import HttpClient
from scrollkit.ota.client import OTAClient

COINS = ["bitcoin", "ethereum", "solana", "cardano", "dogecoin",
         "polkadot", "litecoin", "chainlink", "stellar", "monero"]
SYMBOLS = {"bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL", "cardano": "ADA",
           "dogecoin": "DOGE", "polkadot": "DOT", "litecoin": "LTC",
           "chainlink": "LINK", "stellar": "XLM", "monero": "XMR"}
CHUNK_SIZE = 3  # fetch only a few per request so each blocking call stays short

WEATHER_URL = ("https://api.open-meteo.com/v1/forecast"
               "?latitude=52.52&longitude=13.41&current=temperature_2m")
PRICE_URL = "https://api.coingecko.com/api/v3/simple/price?ids={}&vs_currencies=usd"


def temperature_color(celsius):
    """Cold -> hot color ramp."""
    if celsius <= 0:
        return 0x00AAFF   # icy blue
    if celsius <= 15:
        return 0x00FF88   # cool green
    if celsius <= 28:
        return 0xFFAA00   # warm orange
    return 0xFF3300       # hot red


def _price(usd):
    """Compact price string (whole dollars for big coins, cents for small)."""
    try:
        usd = float(usd)
    except (TypeError, ValueError):
        return "?"
    return str(int(usd)) if usd >= 1 else "%.2f" % usd


class DashboardContent(DisplayContent):
    """A single, never-completing content that draws the whole animated frame.

    The app's display loop calls render() ~20x/second; we use a frame counter to
    animate. Each row is just draw_text() calls — multiple per frame fill the
    full height — so the same code renders on real hardware.
    """

    INTRO_FRAMES = 45  # ~2.2s animated intro

    def __init__(self, app):
        super().__init__(duration=None)   # never completes; animates forever
        self.app = app
        self.effects = EffectsEngine()
        self.frame = 0
        self.ticker_x = 64

    def _rainbow(self, i):
        """Rainbow color flowing over character index i and time."""
        return self.effects.get_rainbow_color(((i * 2 + self.frame) % 30) / 30.0)

    async def render(self, display):
        self.frame += 1
        if self.frame <= self.INTRO_FRAMES:
            await self._render_intro(display)
        else:
            await self._render_dashboard(display)

    async def _render_intro(self, display):
        title = "SCROLLKIT"
        shown = min(len(title), 1 + self.frame // 3)   # reveal letter by letter
        x0 = max(1, (display.width - shown * 6) // 2)
        for i in range(shown):
            await display.draw_text(title[i], x0 + i * 6, 12, self._rainbow(i))

    async def _draw_centered(self, display, text, y, color):
        x = max(0, (display.width - len(text) * 6) // 2)
        await display.draw_text(text, x, y, color)

    async def _render_dashboard(self, display):
        # Three evenly-spaced rows. The font draws ~3px above its y and caps are
        # ~6px tall, so centers at y=6/16/26 give ~3px top margin and ~4px gaps.

        # Row 0: flowing rainbow title, centered.
        title = "CRYPTO LIVE"
        x0 = max(0, (display.width - len(title) * 6) // 2)
        for i, ch in enumerate(title):
            await display.draw_text(ch, x0 + i * 6, 6, self._rainbow(i))

        # Row 1: a rotating headline cycling through weather + each coin,
        # colored (temperature cold->hot, prices green/up or red/down).
        headline = self._headline()
        if headline:
            text, color = headline
            await self._draw_centered(display, text, 16, color)
        else:
            await self._draw_centered(display, "loading...", 16, 0x888888)

        # Row 2: continuous scrolling ticker of every price.
        ticker = self._ticker_text()
        if ticker:
            self.ticker_x -= 1
            if self.ticker_x < -len(ticker) * 6:
                self.ticker_x = display.width
            await display.draw_text(ticker, self.ticker_x, 26, 0x00CCFF)

    def _headline(self):
        """One rotating headline: weather, then each coin with up/down color."""
        items = []
        if self.app.temperature is not None:
            items.append(("BERLIN %dC" % int(round(self.app.temperature)),
                          temperature_color(self.app.temperature)))
        for coin in COINS:
            usd = self.app.prices.get(coin, {}).get("usd")
            if usd is None:
                continue
            prev = self.app.prev_prices.get(coin, {}).get("usd")
            up = prev is None or usd >= prev
            items.append((
                "%s %s %s" % ("^" if up else "v",
                              SYMBOLS.get(coin, coin[:3].upper()), _price(usd)),
                0x00FF00 if up else 0xFF0000))
        if not items:
            return None
        return items[(self.frame // 45) % len(items)]

    def _ticker_text(self):
        parts = []
        for coin in COINS:
            usd = self.app.prices.get(coin, {}).get("usd")
            if usd is not None:
                parts.append("%s $%s" % (SYMBOLS.get(coin, coin[:3].upper()), _price(usd)))
        return "    ".join(parts)


class CryptoDashboardApp(ScrollKitApp):
    def __init__(self):
        super().__init__(enable_web=True, update_interval=300)
        self.http = HttpClient()
        self.prices = {}
        self.prev_prices = {}
        self.temperature = None
        self.dashboard = DashboardContent(self)

    async def create_display(self):
        try:
            from scrollkit.display.simulator import SimulatorDisplay
            return SimulatorDisplay(width=64, height=32)
        except ImportError:
            return await super().create_display()

    async def prepare_display_content(self):
        # One persistent, self-animating dashboard (instead of a content queue).
        return self.dashboard

    async def setup(self):
        if hasattr(self.display, "create_window"):
            await self.display.create_window("ScrollKit - Dashboard (hard)")
        await self._check_for_updates()
        await self.update_data()

    async def _check_for_updates(self):
        """Best-effort OTA check (points at an example repo; offline-safe)."""
        try:
            ota = OTAClient.for_github("myorg", "myapp", current_version="1.0.0")
            has_update, info = ota.check_for_updates()
            print("OTA:", ("update available -> " + info.version) if has_update
                  else "up to date (%s)" % (info,))
        except Exception as e:
            print("OTA check skipped:", e)

    async def update_data(self):
        # --- Source 1: weather (one small request) ---
        try:
            resp = await self.http.get(WEATHER_URL)
            self.temperature = resp.json()["current"]["temperature_2m"]
        except Exception as e:
            print("weather fetch failed:", e)

        # --- Source 2: crypto prices, fetched in CHUNKS so the display keeps
        # animating during the (blocking on CircuitPython) HTTP calls ---
        self.prev_prices = dict(self.prices)
        prices = {}
        for i in range(0, len(COINS), CHUNK_SIZE):
            chunk = COINS[i:i + CHUNK_SIZE]
            try:
                resp = await self.http.get(PRICE_URL.format(",".join(chunk)))
                prices.update(resp.json())
            except Exception as e:
                print("price chunk failed:", chunk, e)
            await asyncio.sleep(0)          # let the display render a frame
        self.prices = prices


if __name__ == "__main__":
    asyncio.run(CryptoDashboardApp().run())
