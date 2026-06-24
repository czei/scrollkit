# ScrollKit

**ScrollKit is an LED matrix display framework that runs the same code on an
Adafruit MatrixPortal S3 and on your desktop.**

Write your app once. On the device it drives a real 64×32 RGB LED matrix over
CircuitPython; on your laptop it renders in a pixel-accurate pygame simulator —
no hardware required to develop, test, or demo.

```python
from scrollkit.app.minimal import MinimalLEDApp

app = MinimalLEDApp()
app.scroll_text("Hello, World!", color=(0, 255, 128))
```

## Why ScrollKit

- **One codebase, two targets.** A platform-detecting display layer picks the
  real `displayio` hardware backend on CircuitPython and the simulator on
  desktop. Your application code never branches on platform.
- **Async-first.** A cooperative event loop keeps the display scrolling while
  data refreshes and the web server run as background tasks.
- **Memory-aware.** Built for the MatrixPortal S3's tight RAM budget: a
  lightweight import surface and graduated feature degradation when memory is
  low.
- **Batteries included.** Priority content queue, an effects/transitions engine,
  a configuration web UI, manifest-based OTA updates from GitHub, WiFi and HTTP
  helpers, and JSON settings persistence.

## What you can build

ScrollKit is the engine behind DIY scrolling-LED projects — clocks, weather
boards, crypto/stock tickers, status displays, and bigger apps like
**ThemeParkWaits** (a live theme-park wait-time board). The library ships with
graded demos so you can see each capability in isolation:

| Demo | Shows |
|------|-------|
| [`demos/easy/`](tutorials/easy.md) | Scrolling text, no network |
| [`demos/medium/`](tutorials/medium.md) | Live temperature from a public API, periodic refresh |
| [`demos/hard/`](tutorials/hard.md) | Web config, priority queue, effects, multiple data sources, OTA, chunked fetch |

## Architecture at a glance

```
your app  ──▶  scrollkit.app.ScrollKitApp        (async lifecycle: display + data + web)
                 │
                 ├─ scrollkit.display   UnifiedDisplay ─▶ hardware (displayio) | simulator (pygame)
                 │                      DisplayQueue (priority + expiry), DisplayContent
                 ├─ scrollkit.effects   Transition (content swaps), particles, splash reveals
                 ├─ scrollkit.web       ScrollKitWebServer (config UI; adafruit_httpserver | async)
                 ├─ scrollkit.ota       OTAClient + UpdateManifest (GitHub-hosted)
                 ├─ scrollkit.network   WiFiManager, HttpClient
                 ├─ scrollkit.config    SettingsManager (JSON persistence)
                 └─ scrollkit.utils     color, error logging, timing
```

Head to **[Getting Started](getting-started.md)**, then work through the
tutorials from easy to hard.
