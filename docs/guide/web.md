# Web Interface

`scrollkit.web` provides a configuration web server that runs on the LED device
itself. It is strictly a **configuration UI** — there is no display preview,
because the server runs on the same device that drives the panel.

## ScrollKitWebServer

`scrollkit.web.server.ScrollKitWebServer` is a single server that works on both
platforms via an adapter:

- **CircuitPython** → `adafruit_httpserver`
- **Desktop** → an async HTTP adapter

Your application layer is identical on both. Enable it through the app:

```python
class MyApp(ScrollKitApp):
    def __init__(self):
        super().__init__(enable_web=True)   # started when memory allows
```

Then browse to the device's IP address on your local network to change settings.

## Pieces

| Module | Role |
|--------|------|
| `web.server` | `ScrollKitWebServer` — the unified server (alias: `SLDKWebServer`) |
| `web.adapters` | platform HTTP adapters (CircuitPython / desktop) |
| `web.handlers` | request routing: static files, API, forms |
| `web.forms` | form parsing for settings updates |
| `web.templates` | HTML template rendering |

## Thread-safety rule

The web server runs in a separate context from the display loop. It must **only
update settings/flags that the main loop reads** — it must never mutate the
message/display queue directly. Settings changes take effect on the next content
cycle.
