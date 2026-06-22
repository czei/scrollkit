# Demo bug audit (pre-publish)

Ran every demo headless (`SDL_VIDEODRIVER=dummy`, time-limited) and triaged the
exceptions. Goal: nothing in `demos/` should throw a library bug before publish.

How to reproduce a single demo headless:

```bash
SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy \
  PYTHONPATH=src timeout 9 python demos/hard/crypto_dashboard.py
```

Render exceptions don't crash the app — the display loop catches them
(`app/base.py` `_display_process`) and prints `Display error: ...` once per
second, so "getting exceptions" shows up as repeating log lines, not a traceback
exit. The audit greps the captured output for `error|exception|traceback|MRO|...`.

## Results by demo

| Demo | Status |
|------|--------|
| `easy/hello_world.py` | clean |
| `easy/colors.py` | clean |
| `easy/clock.py` | clean |
| `medium/rainbow.py` | clean |
| `medium/temperature.py` | clean (needs network; benign ErrorHandler FS-probe logs) |
| `hard/crypto_dashboard.py` | **3 library bugs (fixed) + external rate-limit noise** |

All the real bugs were in the `hard` demo, which is the only one exercising the
web server, the OTA client, and chunked HTTP — so it surfaced library defects the
simpler demos never reached.

## Bugs found and fixed

### 1. Web server crashed on every start — illegal MRO  (HIGH)

`Web server error: Cannot create a consistent method resolution order (MRO) for
bases WebHandler, StaticFileHandler, APIHandler`

`web/server.py` built `class CompositeHandler(WebHandler, StaticFileHandler,
APIHandler)`. `StaticFileHandler` and `APIHandler` already derive from
`WebHandler`, so naming `WebHandler` *first* is an illegal linearization (a base
may not precede its own subclasses). The class raised at definition time, so the
composite-handler web server **never** worked with `enable_web=True`.

- **Fix:** `class CompositeHandler(StaticFileHandler, APIHandler)` — `WebHandler`
  stays reachable via both. MRO is now
  `CompositeHandler -> StaticFileHandler -> APIHandler -> WebHandler -> object`.
- **Verified:** composite handler constructs; `SLDKWebServer.start()` binds
  `localhost:8080` and stops cleanly.

### 2. OTA check crashed on desktop — platform mis-detection  (MEDIUM)

`OTA: up to date (Update check failed: module 'adafruit_requests' has no
attribute 'get')`

`ota/client.py` chose its platform by *trying to import* `adafruit_requests`.
That module is pip-installable on desktop but is Session-based (no module-level
`get`), so desktop was mis-detected as CircuitPython and `requests.get(...)`
blew up.

- **Fix:** detect the platform via `sys.implementation.name == "circuitpython"`
  instead of import success; desktop now uses the real `requests`.
- **Verified:** desktop OTA check returns a clean result; the demo's placeholder
  repo reports `no update (Server error: 404)` instead of crashing.
- **Note:** OTA-over-`adafruit_requests` on real hardware is still unverified
  (the device uses a Session, not a module-level `get`); see the OTA compat note
  in memory. Out of scope for this demo audit; the desktop demo path is fixed.

### 3. HTTP errors mislabeled as JSON syntax errors  (MEDIUM)

`price chunk failed: [...] syntax error in JSON: HTTP error 500: {}`

`network/http_client.py` `BaseResponse.json()` raised the HTTP-status `ValueError`
*inside* the same `try` that wraps JSON parse failures, so an HTTP 500/429 was
re-wrapped as "syntax error in JSON: HTTP error 500" — a misleading message that
hides the real cause.

- **Fix:** raise the HTTP-status error *before* the JSON `try`; only genuine
  parse failures become "syntax error in JSON".
- **Verified:** `BaseResponse(status_code=500, text="{}").json()` now raises
  `HTTP error 500: {}`; the demo logs the accurate cause.

## Not a code bug (noted, not fixed)

- **CoinGecko HTTP 429 / 500 + traceback spam.** CoinGecko's free API rate-limits;
  hammering it (especially across repeated runs while testing) yields 429s, which
  the client logs as `HTTP error 500: {}` after exhausting retries. The
  `ErrorHandler` prints a full stack trace for *every* exception, so each retry
  dumps a urllib traceback. The HTTP failure is external; a single fresh run
  usually succeeds. Quieting tracebacks for routine HTTP errors would be a broad
  change to the global logger and was left out of scope.

## Regression coverage

`test/unit/` gained guards for the three fixed bugs:
- composite web handler builds with a valid MRO and the server start/stops;
- `ota.client.PLATFORM == "desktop"` off-device (no `adafruit_requests` binding);
- `BaseResponse.json()` surfaces the HTTP status, not a JSON-syntax error.
