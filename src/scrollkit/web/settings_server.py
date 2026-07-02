"""Default settings web UI for ScrollKit apps — native ``adafruit_httpserver``.

``SettingsWebServer`` reads ``SettingsManager._schema`` (populated by
``SettingsManager.define()``) and auto-generates an HTML settings form.
No app-level web code is required: just call ``define()`` on the settings
object and the base class wires the server up automatically.

The same server object runs on desktop CPython (stdlib ``socket`` as the
pool) and on the MatrixPortal S3 (``socketpool.SocketPool(wifi.radio)``).
``adafruit_httpserver`` is lazy-imported inside ``_build_server()`` so the
module is safe to import on memory-constrained CircuitPython before the
memory gate in ``_web_server_process()`` clears.

Routes:
    GET  /      — render the settings form
    POST /save  — persist settings, call ``app.notify_settings_changed()``
                  (a flag the display loop applies at its next frame — this
                  server never mutates display/queue state itself), redirect
                  303 to /

Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""
from __future__ import annotations

_SEE_OTHER = (303, "See Other")
_POLL_INTERVAL = 0.05   # seconds between poll() calls (~20×/s, matches display loop)


__all__ = ['SettingsWebServer']

# adafruit_httpserver does not URL-decode form values. The shared
# CircuitPython-safe decoder lives in utils — one implementation, not two.
from ..utils.url_utils import url_decode as _url_decode


# --------------------------------------------------------------------------- #
# HTML helpers
# --------------------------------------------------------------------------- #

def _esc(text):
    return (str(text).replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;").replace('"', "&quot;"))


_PAGE_HEADER = """<!DOCTYPE html>
<html><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Settings</title>
<style>
body{font-family:sans-serif;max-width:480px;margin:40px auto;padding:0 16px;background:#f5f5f5}
h1{font-size:1.2em;margin-bottom:24px;color:#222}
.field{margin-bottom:16px}
label{display:block;font-size:.85em;color:#555;margin-bottom:4px}
input[type=text],input[type=number],select{
  width:100%;padding:8px;border:1px solid #ccc;border-radius:4px;
  box-sizing:border-box;font-size:1em;background:#fff}
input[type=range]{width:100%;vertical-align:middle}
.range-row{display:flex;gap:8px;align-items:center}
.range-val{min-width:2.5em;text-align:right;color:#333;font-size:.9em}
input[type=color]{width:48px;height:32px;border:1px solid #ccc;
  border-radius:4px;padding:2px;cursor:pointer}
.checkbox-row{display:flex;align-items:center;gap:8px;cursor:pointer}
.checkbox-row input{width:16px;height:16px}
button{background:#333;color:#fff;border:none;padding:10px 28px;
  border-radius:4px;font-size:1em;cursor:pointer;margin-top:8px}
button:hover{background:#555}
</style></head>
<body><h1>Settings</h1>
<form method="POST" action="/save">
"""

_PAGE_FOOTER = """<button type="submit">Save</button>
</form></body></html>
"""


def _color_to_html(value):
    """Convert stored color value (int or hex string) to #rrggbb for HTML."""
    if isinstance(value, int):
        return "#{:06x}".format(value & 0xFFFFFF)
    if isinstance(value, str):
        if value.startswith("#"):
            return value
        if value.startswith("0x") or value.startswith("0X"):
            return "#" + value[2:].lower()
    return "#ffffff"


# --------------------------------------------------------------------------- #
# SettingsWebServer
# --------------------------------------------------------------------------- #

class SettingsWebServer:
    """Auto-generating settings web server driven by ``SettingsManager._schema``.

    Implements the ``ScrollKitApp`` web contract:
    ``await start()`` → bool, ``get_server_url()`` → str,
    ``await run_forever()``, ``await stop()``.
    """

    def __init__(self, settings_manager, app=None, host="0.0.0.0", port=80):
        self._sm = settings_manager
        self._app = app
        self._host = host
        self._port = port
        self._server = None
        self._running = False
        self._server_url = ""

    # ------------------------------------------------------------------ #
    # Internal: build server + routes (lazy adafruit_httpserver import)
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
            display_host = str(wifi.radio.ipv4_address)
        else:
            pool = _stdlib_socket
            display_host = self._host if self._host != "0.0.0.0" else "localhost"

        self._server = Server(pool, root_path=None, debug=False)
        self._server_url = "http://{}:{}/".format(display_host, self._port)

        # Capture references for route closures.
        _self = self
        sm = self._sm
        app = self._app

        @self._server.route("/", [GET])
        def _index(request):
            return Response(request, _self._render_form(), content_type="text/html")

        @self._server.route("/save", [POST])
        def _save(request):
            _self._apply(request, sm, app)
            return Redirect(request, "/", status=_SEE_OTHER)

    # ------------------------------------------------------------------ #
    # Internal: form rendering
    # ------------------------------------------------------------------ #

    def _render_form(self):
        sm = self._sm
        parts = [_PAGE_HEADER]

        for field in sm._schema:
            key = field["key"]
            ftype = field["type"]
            label = _esc(field["label"])
            value = sm.get(key, field["default"])

            if ftype == "checkbox":
                checked = " checked" if value else ""
                parts.append(
                    '<div class="field"><label class="checkbox-row">'
                    '<input type="checkbox" name="%s" value="1"%s>'
                    ' %s</label></div>' % (key, checked, label)
                )

            elif ftype == "color":
                html_val = _color_to_html(value)
                parts.append(
                    '<div class="field"><label>%s</label>'
                    '<input type="color" name="%s" value="%s"></div>'
                    % (label, key, html_val)
                )

            elif ftype == "range":
                val_str = str(value)
                mn = "" if field["min"] is None else str(field["min"])
                mx = "" if field["max"] is None else str(field["max"])
                st = "1" if field["step"] is None else str(field["step"])
                parts.append(
                    '<div class="field"><label>%s</label>'
                    '<div class="range-row">'
                    '<input type="range" name="%s" min="%s" max="%s" step="%s"'
                    ' value="%s" oninput="this.nextElementSibling.textContent=this.value">'
                    '<span class="range-val">%s</span>'
                    '</div></div>'
                    % (label, key, mn, mx, st, val_str, val_str)
                )

            elif ftype == "select":
                opts = []
                for o in (field["options"] or []):
                    sel = " selected" if o == value else ""
                    opts.append('<option%s>%s</option>' % (sel, _esc(o)))
                parts.append(
                    '<div class="field"><label>%s</label>'
                    '<select name="%s">%s</select></div>'
                    % (label, key, "".join(opts))
                )

            elif ftype == "number":
                mn = ("" if field["min"] is None
                      else ' min="%s"' % field["min"])
                mx = ("" if field["max"] is None
                      else ' max="%s"' % field["max"])
                st = ("" if field["step"] is None
                      else ' step="%s"' % field["step"])
                parts.append(
                    '<div class="field"><label>%s</label>'
                    '<input type="number" name="%s"%s%s%s value="%s"></div>'
                    % (label, key, mn, mx, st, str(value))
                )

            else:  # text
                parts.append(
                    '<div class="field"><label>%s</label>'
                    '<input type="text" name="%s" value="%s"></div>'
                    % (label, key, _esc(str(value)))
                )

        parts.append(_PAGE_FOOTER)
        return "".join(parts)

    # ------------------------------------------------------------------ #
    # Internal: apply POSTed form to settings
    # ------------------------------------------------------------------ #

    def _apply(self, request, sm, app):
        fd = getattr(request, "form_data", None)

        # Collect present keys so absent checkboxes can be detected.
        form_keys = set()
        if fd is not None:
            try:
                for k in fd.keys():
                    form_keys.add(k)
            except Exception:
                pass

        def _get(key):
            if fd is None:
                return None
            try:
                v = fd.get(key)
                if isinstance(v, bytes):
                    v = v.decode("utf-8", "replace")
                if isinstance(v, str):
                    v = _url_decode(v)
                return v
            except Exception:
                return None

        for field in sm._schema:
            key = field["key"]
            ftype = field["type"]

            if ftype == "checkbox":
                sm.set(key, key in form_keys)
                continue

            raw = _get(key)
            if raw is None:
                continue

            if ftype == "color":
                try:
                    value = int(raw.lstrip("#"), 16)
                except (ValueError, AttributeError):
                    continue

            elif ftype in ("range", "number"):
                try:
                    if isinstance(field["default"], float):
                        value = float(raw)
                    else:
                        value = int(float(raw))
                except (ValueError, TypeError):
                    continue

            else:  # text, select
                value = raw

            sm.set(key, value)

        sm.save_settings()

        # The web server must never mutate display/queue state itself (see
        # notify_settings_changed()) — it may only write settings and flag the
        # main display loop to apply them at a safe frame boundary.
        if app is not None and hasattr(app, "notify_settings_changed"):
            app.notify_settings_changed()

    # ------------------------------------------------------------------ #
    # ScrollKitApp web contract
    # ------------------------------------------------------------------ #

    async def start(self):
        try:
            self._build_server()
            self._server.start(self._host, self._port)
            self._running = True
            return True
        except Exception as e:
            print("SettingsWebServer start failed:", e)
            return False

    def get_server_url(self):
        return self._server_url

    async def run_forever(self):
        import asyncio
        while self._running:
            try:
                self._server.poll()
            except OSError as e:
                print("settings server poll error:", e)
            await asyncio.sleep(_POLL_INTERVAL)

    async def stop(self):
        self._running = False
        try:
            if self._server is not None:
                self._server.stop()
        except Exception:
            pass
