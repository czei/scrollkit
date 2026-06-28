# Networking

`scrollkit.network` provides WiFi connection management and a cross-platform HTTP
client.

## WiFiManager

`scrollkit.network.wifi_manager.WiFiManager` handles CircuitPython WiFi:
connecting (with retries), reconnecting, scanning networks, and a web-based
first-run setup flow (access-point mode + a config page) so a user can enter
credentials without editing files. It creates the `adafruit_requests` session
the HTTP client uses.

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
