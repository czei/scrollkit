"""Regression guards for library bugs the demo audit surfaced.

See plans/DEMO_BUG_AUDIT.md. Each test pins a specific defect found by running
demos/hard/crypto_dashboard.py so it can't silently come back.
"""

import sys


# --- Bug 2: OTA mis-detected desktop as CircuitPython ----------------------

def test_ota_client_detects_desktop_platform():
    """Off-device the client must be 'desktop', not 'circuitpython'."""
    from scrollkit.ota import client

    assert sys.implementation.name != "circuitpython"  # sanity for this runner
    assert client.PLATFORM == "desktop"
    # Whatever 'requests' the desktop client bound, it must expose a usable get()
    # (the bug was binding adafruit_requests, which has no module-level get).
    assert client.requests is not None
    assert hasattr(client.requests, "get")


# --- Bug 3: HTTP errors were re-wrapped as JSON syntax errors --------------

def test_http_error_response_reports_status_not_json_syntax():
    from scrollkit.network.http_client import BaseResponse
    import pytest

    resp = BaseResponse(status_code=500, text="{}")
    with pytest.raises(ValueError) as exc:
        resp.json()
    message = str(exc.value)
    assert "HTTP error 500" in message
    assert "syntax error in JSON" not in message


def test_http_ok_response_still_parses_json():
    from scrollkit.network.http_client import BaseResponse

    assert BaseResponse(status_code=200, text='{"a": 1}').json() == {"a": 1}
    assert BaseResponse(status_code=200, text="").json() == {}
