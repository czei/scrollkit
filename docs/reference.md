# API Reference

The public surface of `scrollkit`, grouped by submodule. Import exactly what you
need — the top-level `scrollkit` package is intentionally lightweight (version
metadata only) so importing it costs almost no RAM on CircuitPython.

!!! tip "Auto-generated docs"
    Install `mkdocstrings[python]` and add the plugin to `mkdocs.yml` to render
    full signatures and docstrings from source. This page is the curated map.

## App

```python
from scrollkit.app.base import ScrollKitApp     # alias: SLDKApp
```

- **`ScrollKitApp`** — `__init__(enable_web=True, update_interval=300,
  enable_watchdog=False, watchdog_timeout=8, enable_auto_reboot=False,
  max_refresh_failures=None)`; override `setup()`, `update_data()`,
  `prepare_display_content()`, `cleanup()`; run with `await app.run()`; `stop()`. Has
  `self.display` and `self.content_queue`. Render suspension:
  `suspend_render()` / `resume_render()` / `with suspended_render(): ...` /
  `render_suspended` — pause queue rendering (queue preserved) while painting an
  off-queue status frame and blocking on a fetch. `enable_auto_reboot` opts into
  rebooting after `max_refresh_failures` (default 12) consecutive
  `note_refresh_result(ok=False)` calls, to recover a wedged radio/session.

## Display

```python
from scrollkit.display.unified import UnifiedDisplay
from scrollkit.display.interface import DisplayInterface
from scrollkit.display.content import DisplayContent, StaticText, ScrollingText, ContentQueue, Priority
```

- **`DisplayInterface`** — `width`, `height`, `initialize()`, `clear()`,
  `show()`, `set_pixel(x, y, color)`, `fill(color)`, `set_brightness(v)`,
  `draw_text(text, x, y, color, font=None)`
- **`UnifiedDisplay`** — `DisplayInterface` that auto-selects hardware/simulator
- **`StaticText(text, x, y, color, duration, priority)`**,
  **`ScrollingText(text, y, color, speed, priority)`** — `is_complete`,
  `elapsed`, `update()`, `await render(display)`
- **`ContentQueue(loop=True)`** — `add(content)`, `get_content_count()`, `clear()`,
  `await get_current()`. Plays content in **priority order**
  (`content.priority`, higher first; equal priority plays in insertion order) —
  not a simple round-robin loop. With `loop=False` the queue terminates after
  the last item's `stop()`: `get_current()` returns `None` until `add()`
  re-arms it with new content.
- **`Priority`** — `IDLE, LOW, NORMAL, HIGH, URGENT, SYSTEM`

## Effects

```python
from scrollkit.effects.transitions import transition_factory, Transition
from scrollkit.effects.particles import ParticleEngine
from scrollkit.effects.reveal_splash import show_reveal_splash
from scrollkit.effects.image_animators import TwinkleAnimator  # + 11 more image animators
```

## Web

```python
from scrollkit.web.settings_server import SettingsWebServer
```

## Exceptions

```python
from scrollkit.exceptions import ScrollKitError, NetworkError, OTAError, FeasibilityError
```

- **`ScrollKitError`** — base class for every ScrollKit exception (alias
  `SLDKError`, kept for backward compatibility).
- **`NetworkError`** — raised by `HttpClient.get` / `get_sync` / `post` after
  retries are exhausted (or when no HTTP client is available);
  `HttpClient.last_error` keeps the raw underlying exception.
- **`OTAError`** — raised internally by `OTAClient` on a server / size / checksum
  failure; the public `OTAClient` methods catch it and return `(ok, reason)`, so
  it does not escape their tuple contract.
- **`FeasibilityError`** — raised by the desktop simulator's strict feasibility
  gate (`run_headless(app, strict=True)`) when a frame busts the device time or
  RAM budget. Never raised on hardware.

Only these four are ever raised by the library — there is no aspirational
hierarchy of types the library never uses.

## OTA

```python
from scrollkit.ota.client import OTAClient
from scrollkit.ota.manifest import UpdateManifest
from scrollkit.ota.display_progress import OTAProgressDisplay
```

- **`OTAClient(update_server_url, current_version, update_dir, backup_dir)`** —
  `check_for_updates() -> (bool, manifest|str)`, `download_update(manifest)`,
  `apply_update()`. There is no public `rollback()` — `apply_update()`
  automatically restores the pre-update backup internally if install fails.
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
from scrollkit.utils.color_utils import ColorUtils
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
