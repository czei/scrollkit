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
- **`ScrollKitApp`** — `__init__(enable_web=True, update_interval=300,
  enable_watchdog=False, watchdog_timeout=8)`; override `setup()`, `update_data()`,
  `prepare_display_content()`, `cleanup()`; run with `await app.run()`; `stop()`. Has
  `self.display` and `self.content_queue`. Render suspension:
  `suspend_render()` / `resume_render()` / `with suspended_render(): ...` /
  `render_suspended` — pause queue rendering (queue preserved) while painting an
  off-queue status frame and blocking on a fetch.

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
from scrollkit.ota.display_progress import OTAProgressDisplay
```

- **`OTAClient(update_server_url, current_version, update_dir, backup_dir)`** —
  `check_for_updates() -> (bool, manifest|str)`, `download_update(manifest)`,
  `apply_update()`, `rollback()`
- **`UpdateManifest`** — `version`, `files`, `requirements`,
  `compare_version(other)`, `validate()`, `from_dict(d)`, `to_json()`
- **`OTAProgressDisplay(client, display=None)`** — display-progress + staged-install
  adapter over an `OTAClient`: `attach_display(display)`, `has_pending()`,
  `schedule_update()`, `await install_pending()`. Renders centered status frames
  ("Installing… DO NOT UNPLUG!"); never raises into the OTA flow.

## Network / Config / Utils

```python
from scrollkit.network.wifi_manager import WiFiManager
from scrollkit.network.http_client import HttpClient
from scrollkit.network import mdns
from scrollkit.config.settings_manager import SettingsManager
from scrollkit.utils.error_handler import ErrorHandler
from scrollkit.utils import diagnostics
from scrollkit.utils.color_utils import rgb_to_hex, hex_to_rgb, scale_brightness
```

- **`HttpClient`** — `await get(url, headers, max_retries)`, `await post(...)`,
  responses expose `.json()`
- **`mdns.advertise(hostname, *, port=80, service_type="_http", protocol="_tcp")`**
  — advertise `<hostname>.local`; returns the `mdns.Server` (RETAIN it — GC stops
  resolution) or `None` on desktop / no radio; never raises.
- **`SettingsManager(filename, defaults, bool_keys)`** — `get`, `set`,
  `save_settings`, `load_settings`, `get_scroll_speed`, `get_pretty_name`
- **`diagnostics`** — `open() -> Diagnostics` (NVM-bound on device, no-op on
  desktop), `read_reset_reason()`; `Diagnostics.record_boot(reason)`, `.safe_mode`,
  `note_clean_run()`, `note_fetch_result(ok, n)`, `record_crash(msg)`, `summary()`.
  NVM-backed boot/crash record + reboot-loop safe-mode breaker.
