# Networking

`scrollkit.network` provides WiFi connection management and a cross-platform HTTP
client.

## WiFiManager

`scrollkit.network.wifi_manager.WiFiManager` handles CircuitPython WiFi:
connecting (with retries), reconnecting, scanning networks, creating the
`adafruit_requests` session the HTTP client uses after a successful connection
(`create_http_session()`), and — when the device has no working credentials —
running the [WiFi onboarding portal](#wifi-onboarding-portal-no-file-editing)
over its own access point (`start_access_point()` / `stop_access_point()` /
`run_setup_portal()`).

Credentials are resolved **settings first, `secrets.py` second**: whatever the
onboarding portal saved into `settings.json` (`wifi_ssid` / `wifi_password`)
beats a stale `secrets.py`, so a device configured from a phone never needs a
file edited.

`scrollkit.network.wifi_manager.is_dev_mode()` reports whether a real WiFi
radio is available (always `False` on CircuitPython; `True` on desktop unless
the test suite mocks a `wifi` module) — the canonical desktop-vs-device check
for network code.

### The radio bounce: link up, new connects dead (0.9.2)

There is a field failure `reconnect()` cannot see: the ESP32-S3's session
degrades so **new outbound connects fail `OSError: 16` (EBUSY) while pooled
keep-alive connections — and the device's own web server — keep working**.
The link reports connected, so anything that watches "is WiFi up" never acts,
and the box quietly serves stale data. Triggers observed on hardware: a reset
issued while the station was associated (see `cold_reset()` in
[Utilities](utils.md#cold_reset-092)), and long uptimes on multi-AP mesh
networks.

`bounce()` (async) and `bounce_sync()` (for synchronous call sites like web
handlers) force a radio restart and fresh association even when the link
looks healthy. **A bounce alone is not the cure**: any
`adafruit_requests.Session` built on the pre-bounce association keeps its
stale socket plumbing and still fails. Complete every bounce with a full
session rebuild:

```python
if await wifi_manager.bounce():
    http_client.rebuild_session()   # fresh SocketPool + ssl context + Session
```

A good escalation ladder bounces after a few consecutive fetch failures and
keeps a cold-reset watchdog as the last resort; classify errors first so a
remote API outage doesn't trigger radio surgery.

## WiFi onboarding portal (no file editing)

A brand-new (or moved) device has no way onto the local network, and asking a
user to edit `secrets.py` defeats the point of a finished product. The
onboarding portal fixes that end-to-end:

```python
class MyApp(ScrollKitApp):
    async def setup(self):
        wm = WiFiManager(self.settings)
        if not await wm.connect():
            # Blocks here until the user configures WiFi from a phone,
            # then reboots the device with the saved credentials.
            await wm.run_setup_portal(display=self.display)
        ...
```

What the user sees:

1. The panel scrolls **“WiFi setup: join "WifiManager_XXXX" (password:
   password) then open http://192.168.4.1”**.
2. They join that access point from a phone and open the address: a page
   lists the scanned nearby networks (with signal bars), plus a manual
   network-name field (for hidden SSIDs) and a password field.
3. Submitting saves `wifi_ssid`/`wifi_password` through the
   `SettingsManager` (into `settings.json` — **never** a code file), shows a
   confirmation page, and reboots the device, which then connects with the
   saved credentials (they take precedence over `secrets.py`).

Details worth knowing:

- `run_setup_portal(display=..., port=80, reboot=True, timeout_s=None)`
  returns `True` when credentials were saved. `reboot` applies on hardware
  only; on desktop the call simply returns so the flow is testable.
- The portal is a **boot-phase** flow: it owns the screen exclusively before
  the app's display loop starts (like `OTAProgressDisplay.install_pending()`),
  and it only ever **writes settings** — the same discipline as the settings
  web UI (see `docs/guide/web.md`).
- Everything is imported lazily (`scrollkit.web.wifi_setup`,
  `adafruit_httpserver`) — a device that boots with working credentials never
  pays a byte of RAM for the portal.
- The network scan happens *before* AP mode starts (some radio builds can't
  scan while running an access point).
- The AP is WPA2 with the default password `password` (attributes
  `AP_SSID` / `AP_PASSWORD` on `WiFiManager`, derived from the radio MAC).

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

`rebuild_session()` (0.9.2) tears down the current session's pooled sockets —
releasing their native mbedTLS contexts — and installs a fresh
`SocketPool` + ssl context + `Session`. It is the required second half of a
[radio bounce](#the-radio-bounce-link-up-new-connects-dead-092), and useful on
its own when the pool's native state is suspect.

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
