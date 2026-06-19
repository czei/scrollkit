"""End-to-end render smoke tests for the medium and hard demos.

Like ``test_app_render_smoke.py``, these drive the *real* demo apps against the
simulator headlessly and assert something visible actually renders. The data
fetches are mocked (no real network — that would be slow and flaky), so what's
exercised is the demo's own wiring: setup, update_data, the content queue, and
the display loop end to end.

These would have failed on the ``create_task``/brightness bugs too.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")  # headless pygame, before import

import asyncio
import importlib.util
from unittest.mock import AsyncMock, MagicMock

import pytest

pygame = pytest.importorskip("pygame")

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DEMOS_DIR = os.path.join(REPO_ROOT, "demos")


def _load_demo(relpath, name):
    """Load a standalone demo script as a module (without running __main__)."""
    spec = importlib.util.spec_from_file_location(name, os.path.join(DEMOS_DIR, relpath))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _fake_http(payload):
    """An HttpClient stand-in whose async get() returns payload via .json()."""
    resp = MagicMock()
    resp.json = MagicMock(return_value=payload)
    client = MagicMock()
    client.get = AsyncMock(return_value=resp)
    return client


def _fake_http_router(routes):
    """HttpClient stand-in that returns a different payload per URL substring."""
    async def get(url, *args, **kwargs):
        payload = {}
        for key, value in routes.items():
            if key in url:
                payload = value
                break
        resp = MagicMock()
        resp.json = MagicMock(return_value=payload)
        return resp
    client = MagicMock()
    client.get = AsyncMock(side_effect=get)
    return client


def _bright_pixels(surface):
    w, h = surface.get_size()
    n = 0
    for y in range(0, h, 2):
        for x in range(0, w, 2):
            r, g, b = surface.get_at((x, y))[:3]
            if r + g + b > 250:
                n += 1
    return n


async def _run_briefly(app, timeout=2.0):
    try:
        await asyncio.wait_for(app.run(), timeout=timeout)
    except asyncio.TimeoutError:
        pass
    finally:
        app.stop()


@pytest.mark.asyncio
async def test_medium_temperature_demo_renders():
    mod = _load_demo("medium/temperature.py", "demo_medium")
    app = mod.TemperatureApp()
    app.http = _fake_http({"current": {"temperature_2m": 21.5}})

    await _run_briefly(app)

    # update_data ran with the mocked reading and built the display text.
    assert app.text == "Berlin: 21.5 C"
    # The display loop actually rendered something visible.
    surface = app.display.matrix.get_surface()
    assert _bright_pixels(surface) > 20, "medium demo rendered no visible pixels"


@pytest.mark.asyncio
async def test_hard_crypto_demo_renders():
    mod = _load_demo("hard/crypto_dashboard.py", "demo_hard")
    app = mod.CryptoDashboardApp()
    # Route each data source to its own canned payload (no real network).
    app.http = _fake_http_router({
        "open-meteo": {"current": {"temperature_2m": 21.5}},
        "coingecko": {coin: {"usd": 100} for coin in mod.COINS},
    })
    # Stub the startup OTA check (it makes its own HTTP call) and don't start
    # the real web server (it would bind a socket) in the test.
    app._check_for_updates = AsyncMock()
    app.enable_web = False

    await _run_briefly(app)

    # Both sources were consumed: weather parsed and all prices populated.
    assert app.temperature == 21.5, "hard demo did not read the weather source"
    assert app.prices and all(coin in app.prices for coin in mod.COINS), \
        "hard demo did not populate prices from the chunked fetch"
    # The display loop actually rendered something visible.
    surface = app.display.matrix.get_surface()
    assert _bright_pixels(surface) > 20, "hard demo rendered no visible pixels"
