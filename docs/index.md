<div class="sk-hero">
  <video class="sk-hero__video" autoplay loop muted playsinline preload="auto"
         poster="assets/video/scrollkit-hero-poster.png">
    <source src="assets/video/scrollkit-hero.mp4" type="video/mp4">
    Your browser doesn't support embedded video.
  </video>
  <p class="sk-hero__caption">One 64×32 LED show &mdash; swarm-assembled, lit with sweeping sheen, and colored entirely by ScrollKit, captured from its pixel-accurate simulator.</p>
</div>

# ScrollKit

**ScrollKit is an LED matrix display framework that runs the same code on
CircuitPython HUB75 boards (the Adafruit MatrixPortal S3 and the Pimoroni
Interstate 75 W) and on your desktop.**

Write your app once. On the device it drives a real 64×32 RGB LED matrix over
CircuitPython, auto-detecting the board it's running on; on your laptop it
renders in a pixel-accurate pygame simulator, so no hardware is required to
develop, test, or demo.

```python
from scrollkit.app.minimal import MinimalLEDApp

app = MinimalLEDApp()
app.scroll_text("Hello, World!", color=(0, 255, 128))
```

## Why ScrollKit

- **One codebase, two targets.** A platform-detecting display layer picks the
  real `displayio` hardware backend on CircuitPython and the simulator on
  desktop. Your application code never branches on platform.
- **Board-agnostic.** On CircuitPython it auto-detects the board (MatrixPortal S3
  or Interstate 75 W) and falls back cleanly; adding a board is a small recipe.
  See [Adding New Hardware](guide/hardware.md).
- **Async-first.** A cooperative event loop keeps the display scrolling while
  data refreshes and the web server run as background tasks.
- **Memory-aware.** Built for the tight RAM budgets of embedded boards (the
  MatrixPortal S3, the RP2350-based Interstate 75 W): a lightweight import
  surface and graduated feature degradation when memory is low.
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
