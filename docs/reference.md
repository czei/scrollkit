# API Reference

The public surface of `scrollkit`, grouped by submodule. Import exactly what you
need — the top-level `scrollkit` package is intentionally lightweight (version
metadata only) so importing it costs almost no RAM on CircuitPython.

!!! tip "Auto-generated docs"
    Install `mkdocstrings[python]` and add the plugin to `mkdocs.yml` to render
    full signatures and docstrings from source. This page is the curated map.

## App

```python
from scrollkit.app.minimal import MinimalLEDApp
from scrollkit.app.base import ScrollKitApp     # alias: SLDKApp
```

- **`MinimalLEDApp`** — `show_text(text, color)`, `scroll_text(text, color, delay)`, `clear()`
- **`ScrollKitApp`** — `__init__(enable_web=True, update_interval=300)`; override
  `setup()`, `update_data()`, `prepare_display_content()`, `cleanup()`; run with
  `await app.run()`; `stop()`. Has `self.display` and `self.content_queue`.

## Display

```python
from scrollkit.display.unified import UnifiedDisplay
from scrollkit.display.interface import DisplayInterface
from scrollkit.display.content import DisplayContent, StaticText, ScrollingText
from scrollkit.display.queue import DisplayQueue
from scrollkit.display.strategy import Priority
```

- **`DisplayInterface`** — `width`, `height`, `initialize()`, `clear()`,
  `show()`, `set_pixel(x, y, color)`, `fill(color)`, `set_brightness(v)`,
  `draw_text(text, x, y, color, font=None)`
- **`UnifiedDisplay`** — `DisplayInterface` that auto-selects hardware/simulator
- **`StaticText(text, x, y, color, duration, priority)`**,
  **`ScrollingText(text, y, color, speed, priority)`** — `is_complete`,
  `elapsed`, `update()`, `await render(display)`
- **`DisplayQueue`** — `add(content)`, `peek()`, `pop()`, `expire()`, `len()`
- **`Priority`** — `IDLE, LOW, NORMAL, HIGH, SYSTEM`

## Effects

```python
from scrollkit.effects.transitions import transition_factory, Transition
from scrollkit.effects import ParticleEngine, show_reveal_splash
```

## Web

```python
from scrollkit.web.server import ScrollKitWebServer   # alias: SLDKWebServer
```

## OTA

```python
from scrollkit.ota.client import OTAClient
from scrollkit.ota.manifest import UpdateManifest
```

- **`OTAClient(update_server_url, current_version, update_dir, backup_dir)`** —
  `check_for_updates() -> (bool, manifest|str)`, `download_update(manifest)`,
  `apply_update()`, `rollback()`
- **`UpdateManifest`** — `version`, `files`, `requirements`,
  `compare_version(other)`, `validate()`, `from_dict(d)`, `to_json()`

## Network / Config / Utils

```python
from scrollkit.network.wifi_manager import WiFiManager
from scrollkit.network.http_client import HttpClient
from scrollkit.config.settings_manager import SettingsManager
from scrollkit.utils.error_handler import ErrorHandler
from scrollkit.utils.color_utils import rgb_to_hex, hex_to_rgb, scale_brightness
```

- **`HttpClient`** — `await get(url, headers, max_retries)`, `await post(...)`,
  responses expose `.json()`
- **`SettingsManager(filename, defaults, bool_keys)`** — `get`, `set`,
  `save_settings`, `load_settings`, `get_scroll_speed`, `get_pretty_name`
