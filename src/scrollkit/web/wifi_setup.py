"""WiFi onboarding portal — configure Wi-Fi from a phone, no file editing.

This is the restored no-``secrets.py`` setup flow (see the original in git at
``149ed9c:src/wifimgr.py`` — this is a redesign against the current
architecture, not a revert). The flow:

1. The device can't join Wi-Fi (no/wrong credentials), so the app calls
   ``WiFiManager.run_setup_portal(display=...)`` — usually right after a
   failed ``connect()``.
2. The device starts its own access point (``WifiManager_XXXX``) and shows
   join instructions on the LED panel.
3. The user's phone joins that AP and opens ``http://192.168.4.1``: a page
   with the scanned nearby networks (signal bars), a manual-SSID field, and
   a password field.
4. Submitting saves ``wifi_ssid``/``wifi_password`` through the
   ``SettingsManager`` (settings.json — never a code file), then the device
   reboots and ``WiFiManager`` connects with the saved credentials.

Contract notes (same discipline as ``settings_server``):
- The portal only ever WRITES SETTINGS. It never touches the content queue.
  It runs as a blocking boot-phase flow that owns the screen exclusively —
  before the app's display loop starts — like ``OTAProgressDisplay.
  install_pending()``.
- ``adafruit_httpserver``/``socketpool``/``wifi`` are imported lazily inside
  methods, so importing this module costs nothing and the device only pays
  for the portal on an unconfigured boot.
- Desktop CPython works too (stdlib ``socket`` as the pool, localhost) so
  the flow is testable off-device.

Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""
from __future__ import annotations

import asyncio
import time

from ..utils.url_utils import url_decode as _url_decode

_SEE_OTHER = (303, "See Other")
_POLL_INTERVAL = 0.05    # seconds between poll() calls (matches settings_server)
# Keep serving briefly after a save so the browser finishes receiving the
# confirmation page before the server (and on hardware, the AP) goes away.
_LINGER_S = 2.0


__all__ = ['WiFiSetupPortal']


def _esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


def _bars(rssi):
    """Rough signal-strength bars from RSSI (dBm)."""
    try:
        rssi = int(rssi)
    except (ValueError, TypeError):
        return 1
    if rssi >= -55:
        return 4
    if rssi >= -65:
        return 3
    if rssi >= -75:
        return 2
    return 1


_PAGE_HEADER = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wi-Fi Setup</title>
<style>
body{font-family:sans-serif;max-width:480px;margin:40px auto;padding:0 16px;background:#f5f5f5}
h1{font-size:1.2em;margin-bottom:8px;color:#222}
p.hint{font-size:.85em;color:#555;margin-top:0}
.field{margin-bottom:16px}
label{display:block;font-size:.85em;color:#555;margin-bottom:4px}
input[type=text],input[type=password],select{
  width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;
  box-sizing:border-box;font-size:1em;background:#fff}
button{background:#333;color:#fff;border:none;padding:10px 28px;
  border-radius:4px;font-size:1em;cursor:pointer;margin-top:8px}
button:hover{background:#555}
</style></head>
<body><h1>Wi-Fi Setup</h1>
<p class="hint">Pick your network (or type its name), enter the password,
and the display will restart and connect.</p>
<form method="POST" action="/save">
"""

_PAGE_FOOTER = """<button type="submit">Connect</button>
</form></body></html>
"""

_SAVED_PAGE = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Wi-Fi Saved</title></head>
<body style="font-family:sans-serif;max-width:480px;margin:40px auto;padding:0 16px">
<h1>Saved</h1>
<p>The display is restarting and will join <b>%s</b>.</p>
<p>You can now reconnect this phone to your normal Wi-Fi.</p>
</body></html>
"""


class WiFiSetupPortal:
    """Access-point onboarding portal over a ``WiFiManager``.

    Usually not constructed directly — call
    ``WiFiManager.run_setup_portal(display=...)`` instead.
    """

    def __init__(self, wifi_manager, display=None, port=80):
        self._wm = wifi_manager
        self._display = display
        self._port = port
        self._server = None
        self._server_url = ""
        self._networks = []
        self.saved = False
        self.saved_ssid = None
        self.error = None

    # ------------------------------------------------------------------ #
    # Form rendering
    # ------------------------------------------------------------------ #

    def _render_form(self):
        parts = [_PAGE_HEADER]

        if self._networks:
            opts = ['<option value="" disabled selected>Choose a network...'
                    '</option>']
            for net in self._networks:
                ssid = net.get("ssid", "")
                if not ssid:
                    continue
                rssi = net.get("rssi", -99)
                opts.append('<option value="%s">%s (%s bars, %s dBm)</option>'
                            % (_esc(ssid), _esc(ssid), _bars(rssi), rssi))
            parts.append(
                '<div class="field"><label>Nearby networks</label>'
                '<select name="ssid">%s</select></div>' % "".join(opts)
            )

        parts.append(
            '<div class="field"><label>Or type a network name</label>'
            '<input type="text" name="ssid_manual" value=""></div>'
        )
        parts.append(
            '<div class="field"><label>Password</label>'
            '<input type="password" name="password" value=""></div>'
        )
        if self.error:
            parts.append('<p style="color:#a00">%s</p>' % _esc(self.error))
        parts.append(_PAGE_FOOTER)
        return "".join(parts)

    # ------------------------------------------------------------------ #
    # POST /save
    # ------------------------------------------------------------------ #

    def _apply(self, request):
        """Read the submitted form; save credentials through the settings
        manager. Returns True when credentials were saved. Only ever writes
        settings — never display/queue state."""
        fd = getattr(request, "form_data", None)

        def _get(key):
            if fd is None:
                return ""
            try:
                v = fd.get(key)
            except Exception:
                return ""
            if v is None:
                return ""
            if isinstance(v, bytes):
                v = v.decode("utf-8", "replace")
            if isinstance(v, str):
                v = _url_decode(v)
            return v.strip()

        # A typed name beats the dropdown (covers hidden networks and an
        # empty scan); the dropdown is the common path.
        ssid = _get("ssid_manual") or _get("ssid")
        password = _get("password")

        if not ssid:
            self.error = "Please choose or type a network name."
            return False

        self._wm.ssid = ssid
        self._wm.password = password
        self._wm.save_credentials()          # -> settings.json, never a code file
        self.saved = True
        self.saved_ssid = ssid
        self.error = None
        return True

    # ------------------------------------------------------------------ #
    # Server plumbing (lazy adafruit_httpserver import)
    # ------------------------------------------------------------------ #

    def _build_server(self):
        import sys
        import socket as _stdlib_socket
        from adafruit_httpserver import Server, Response, Redirect, GET, POST

        is_cp = (hasattr(sys, "implementation")
                 and sys.implementation.name == "circuitpython")
        if is_cp:
            import socketpool
            import wifi
            pool = socketpool.SocketPool(wifi.radio)
            host = self._wm.ap_ip_address()
        else:
            pool = _stdlib_socket
            host = "localhost"

        self._server = Server(pool, root_path=None, debug=False)
        self._server_url = "http://{}:{}/".format(host, self._port)
        self._host = host

        _self = self

        @self._server.route("/", [GET])
        def _index(request):
            return Response(request, _self._render_form(),
                            content_type="text/html")

        @self._server.route("/save", [POST])
        def _save(request):
            if _self._apply(request):
                return Response(request, _SAVED_PAGE % _esc(_self.saved_ssid),
                                content_type="text/html")
            return Redirect(request, "/", status=_SEE_OTHER)

    # ------------------------------------------------------------------ #
    # Panel instructions
    # ------------------------------------------------------------------ #

    def _instructions(self):
        wm = self._wm
        return ("WiFi setup: join \"%s\" (password: %s) then open http://%s"
                % (wm.AP_SSID, wm.AP_PASSWORD, wm.ap_ip_address()))

    def _make_status_content(self):
        """A ScrollingText with the join instructions, or None if the display
        stack isn't usable (the portal must never die because of the panel)."""
        if self._display is None:
            return None
        try:
            from ..display.content import ScrollingText
            return ScrollingText(self._instructions(), y=20, color=0x00A0FF)
        except Exception as e:
            print("wifi portal: status content unavailable:", e)
            return None

    # ------------------------------------------------------------------ #
    # The blocking onboarding loop
    # ------------------------------------------------------------------ #

    async def run(self, timeout_s=None):
        """Scan, start the AP, and serve the portal until credentials are
        saved (returns True), the timeout passes, or the simulator window is
        closed (returns False). Stops the server and the AP either way."""
        wm = self._wm

        # Scan BEFORE AP mode: some radio builds can't scan while running an
        # access point, and the list only needs to be fresh-ish.
        try:
            self._networks = wm.scan_networks() or []
        except Exception as e:
            print("wifi portal: scan failed:", e)
            self._networks = []

        wm.start_access_point()
        try:
            self._build_server()
            self._server.start(getattr(self, "_host", "localhost"), self._port)
            print("WiFi setup portal on %s (AP %r)"
                  % (self._server_url, wm.AP_SSID))

            status = self._make_status_content()
            if status is not None:
                try:
                    await status.start()
                except Exception:
                    status = None

            start = time.monotonic()
            linger_until = None
            while True:
                try:
                    self._server.poll()
                except OSError as e:
                    print("wifi portal poll error:", e)

                # Serve a little longer after the save so the confirmation
                # page reaches the phone, then exit.
                if self.saved and linger_until is None:
                    linger_until = time.monotonic() + _LINGER_S
                if linger_until is not None and time.monotonic() >= linger_until:
                    break
                if (timeout_s is not None
                        and time.monotonic() - start >= timeout_s):
                    break

                if status is not None:
                    try:
                        await self._display.clear()
                        await status.render(self._display)
                        if await self._display.show() is False:
                            break   # simulator window closed
                    except Exception as e:
                        print("wifi portal display error:", e)
                        status = None

                await asyncio.sleep(_POLL_INTERVAL)
        finally:
            try:
                if self._server is not None:
                    self._server.stop()
            except Exception:
                pass
            wm.stop_access_point()

        return self.saved
