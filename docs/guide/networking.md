# Networking

`scrollkit.network` provides WiFi connection management and a cross-platform HTTP
client.

## WiFiManager

`scrollkit.network.wifi_manager.WiFiManager` handles CircuitPython WiFi:
connecting (with retries), reconnecting, scanning networks, and creating the
`adafruit_requests` session the HTTP client uses after a successful connection
(`create_http_session()`). An earlier `start_access_point()` / `stop_access_point()`
pair (plus the captive-portal web server built on it) was removed as unused
legacy code — see `docs/guide/web.md` for the settings web UI, which is the
maintained config-page path. `WiFiManager` today only manages station-mode
connectivity (`connect()`, `reconnect()`, `scan_networks()`,
`create_http_session()`); AP-mode setup is not part of the current API.

`scrollkit.network.wifi_manager.is_dev_mode()` reports whether a real WiFi
radio is available (always `False` on CircuitPython; `True` on desktop unless
the test suite mocks a `wifi` module) — the canonical desktop-vs-device check
for network code.

## HttpClient

`scrollkit.network.http_client.HttpClient` exposes one API across platforms:

```python
from scrollkit.network.http_client import HttpClient
from scrollkit.exceptions import NetworkError

http = HttpClient()
try:
    resp = await http.get("https://api.open-meteo.com/v1/forecast?...")
    data = resp.json()
except NetworkError as e:
    ...  # every retry failed; http.last_error holds the raw cause
```

- **CircuitPython** → `adafruit_requests` (synchronous, behind `await`).
- **Desktop** → `urllib` fallback when no session is supplied.

It supports retries with backoff and a pluggable mock provider for tests.

`get()`, `get_sync()`, and `post()` **raise `scrollkit.exceptions.NetworkError`**
when every retry fails (rather than returning a synthesized 500). The raw
underlying exception is retained on `http.last_error` for diagnostics —
`seconds_since_last_success()` and the diagnostics `note_fetch_result` hook read
it to decide when displayed data has gone stale. A mock provider that returns a
response is passed through unchanged (no raise).

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
