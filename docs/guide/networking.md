# Networking

`scrollkit.network` provides WiFi connection management and a cross-platform HTTP
client.

## WiFiManager

`scrollkit.network.wifi_manager.WiFiManager` handles CircuitPython WiFi:
connecting (with retries), reconnecting, scanning networks, and creating the
`adafruit_requests` session the HTTP client uses after a successful connection
(`create_http_session()`). `start_access_point()` / `stop_access_point()` bring
up the device's own AP radio; pairing that with a captive-portal config page is
left to the application (an earlier built-in web-based WiFi setup flow was
removed as unused legacy code in 0.8.2 — see `docs/guide/web.md` for the
settings web UI, which is the maintained config-page path).

`scrollkit.network.wifi_manager.is_dev_mode()` reports whether a real WiFi
radio is available (always `False` on CircuitPython; `True` on desktop unless
the test suite mocks a `wifi` module) — the canonical desktop-vs-device check
for network code.

## HttpClient

`scrollkit.network.http_client.HttpClient` exposes one API across platforms:

```python
from scrollkit.network.http_client import HttpClient

http = HttpClient()
resp = await http.get("https://api.open-meteo.com/v1/forecast?...")
data = resp.json()
```

- **CircuitPython** → `adafruit_requests` (synchronous, behind `await`).
- **Desktop** → `urllib` fallback when no session is supplied.

It supports retries with backoff and a pluggable mock provider for tests.

## Blocking I/O is real on CircuitPython

`adafruit_requests` is synchronous — a request blocks the event loop until it
returns, pausing the scroll. ScrollKit does **not** pretend this is transparently
async. Design around it:

- Render a static/loading frame before a known-slow fetch.
- For lots of data, **chunk the requests** and `await asyncio.sleep(0)` between
  chunks so the display keeps moving. See the
  [hard tutorial](../tutorials/hard.md) for the full pattern.

## mDNS: reach the device by name

`scrollkit.network.mdns.advertise()` advertises `<hostname>.local` plus a service
record, so the config web UI is reachable by name without knowing the IP. It is
CircuitPython-only — a no-op returning `None` on desktop / when there's no radio —
and never raises, so it can't block boot:

```python
from scrollkit.network import mdns

# Keep the returned server alive for the app's lifetime!
self._mdns = mdns.advertise(self.settings.get("hostname", "scrollkit"))
```

!!! warning "Retain the server"
    You **must** hold a reference to the returned `mdns.Server`. If it is
    garbage-collected the responder stops and `.local` resolution dies after the
    first cached query expires — an intermittent failure that's painful to debug.
