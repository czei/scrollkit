# Hard: Full App — Web Config, Effects, OTA, Chunked Fetch

The complete stack: a web configuration UI, a priority display queue, the
effects engine, multiple public data sources, an OTA update check, and the
**chunked-fetch** technique that keeps the scroll alive during blocking HTTP.

![Crypto dashboard demo](../assets/demos/crypto_dashboard.gif){ width="480" }

Full source: [`demos/hard/crypto_dashboard.py`](https://github.com/Czeiszperger/scrollkit/blob/main/demos/hard/crypto_dashboard.py)

## The chunked-fetch workaround

This is the most important pattern for any data-heavy CircuitPython display.

`adafruit_requests` is **synchronous**: one request that returns all ten prices
blocks the display loop for the *entire* transfer, freezing the scroll. Instead,
fetch a few items per request and yield to the event loop between chunks:

```python
COINS = ["bitcoin", "ethereum", "solana", "cardano", "dogecoin",
         "polkadot", "litecoin", "chainlink", "stellar", "monero"]
CHUNK_SIZE = 3  # few items per request -> each blocking call stays short

async def update_data(self):
    prices = {}
    for i in range(0, len(COINS), CHUNK_SIZE):
        chunk = COINS[i:i + CHUNK_SIZE]
        url = ("https://api.coingecko.com/api/v3/simple/price"
               "?ids=" + ",".join(chunk) + "&vs_currencies=usd")
        resp = await self.http.get(url)   # short blocking call (a few items)
        prices.update(resp.json())
        await asyncio.sleep(0)            # (1) let the display render a frame
    ...
```

1. The yield is the whole trick: between each short request the event loop runs,
   so the display renders a frame and the scroll keeps moving. Slower overall
   than one big request, but no screen lock-up.

## Priority queue

A `SYSTEM`-priority item is always admitted and shown ahead of normal content —
useful for alerts. Normal content is evicted to make room when the queue is full
(see the [eviction policy](../guide/display.md#priority-eviction)).

```python
from scrollkit.display.strategy import Priority

self.content_queue.add(StaticText("ScrollKit", x=6, y=12, color=0x00FF88,
                                  duration=2, priority=Priority.SYSTEM))
```

## Web configuration

Constructing the app with `enable_web=True` starts `ScrollKitWebServer` (when
memory allows). Browse to the device's IP to change settings live — backed by
`SettingsManager`, which persists to JSON across reboots.

## OTA at startup

Check GitHub for a new release on boot. Recovery rests on the immutable
`boot.py` + update system, so a bad update can never disable the updater (see
[OTA Updates](../guide/ota.md)).

Run it:

```bash
PYTHONPATH=src python demos/hard/crypto_dashboard.py
```

Data source: CoinGecko `/simple/price` (no API key required).
