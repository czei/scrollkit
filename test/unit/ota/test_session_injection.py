# Copyright (c) 2024-2026 Michael Czeiszperger
"""OTA client must use an injected Session for HTTP, not module-level requests.

Regression test for the on-device OTA bug (Matrix Portal S3, CircuitPython
10.2.1): modern ``adafruit_requests`` is Session-based and exposes no
module-level ``get``, so ``requests.get(...)`` raised
``AttributeError: 'module' object has no attribute 'get'`` on every OTA check —
silently no-op'ing updates. The app injects its existing Session; the client
must accept and use it.
"""

from scrollkit.ota.client import OTAClient
from scrollkit.ota.manifest import UpdateManifest


class _FakeResponse:
    """Minimal Response: what check_for_updates touches."""

    def __init__(self, payload):
        self.status_code = 200
        self._payload = payload
        self.closed = False

    def json(self):
        return self._payload

    def close(self):
        self.closed = True


class _FakeSession:
    """Session-style HTTP client: exposes only ``.get`` (like adafruit_requests.Session)."""

    def __init__(self, payload):
        self._payload = payload
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append((url, timeout))
        return _FakeResponse(self._payload)


class _BoomModule:
    """Stand-in for the module-level ``requests``; fails loudly if used."""

    def get(self, *args, **kwargs):  # pragma: no cover - asserts on call
        raise AssertionError("module-level requests.get must not be called")


def _newer_manifest_dict():
    manifest = UpdateManifest(version="2.0.0", description="Newer release")
    manifest.add_file("src/main.py", content=b"print('hello')\n")
    return manifest.to_dict()


def test_check_for_updates_uses_injected_session(monkeypatch):
    """An injected session is used (not module requests) and detects a newer version."""
    session = _FakeSession(_newer_manifest_dict())
    # Any fallback to the module-level requests.get would explode, proving the
    # session is what actually serviced the request.
    monkeypatch.setattr("scrollkit.ota.client.requests", _BoomModule())

    client = OTAClient(
        update_server_url="https://raw.githubusercontent.com/owner/repo/releases",
        current_version="1.0.0",
        session=session,
    )

    has_update, manifest = client.check_for_updates()

    assert has_update is True
    assert isinstance(manifest, UpdateManifest)
    assert manifest.version == "2.0.0"

    # The session serviced every GET (none leaked to module requests): the
    # ~6-byte version.txt fast-path probe first (which falls through here —
    # _FakeResponse has no .text), then the manifest. Both carry the timeout.
    assert [u.rsplit("/", 1)[1] for u, _ in session.calls] == [
        "version.txt", "manifest.json"]
    assert all(t == client.download_timeout for _, t in session.calls)


def test_session_is_read_live_after_construction(monkeypatch):
    """session may be assigned after construction (app rebuilds it on WiFi connect)."""
    monkeypatch.setattr("scrollkit.ota.client.requests", _BoomModule())

    client = OTAClient(
        update_server_url="https://raw.githubusercontent.com/owner/repo/releases",
        current_version="1.0.0",
    )
    # Not bound at construction; assigned live, just before use.
    session = _FakeSession(_newer_manifest_dict())
    client.session = session

    has_update, manifest = client.check_for_updates()

    assert has_update is True
    assert manifest.version == "2.0.0"
    # version.txt probe + manifest, both via the live-assigned session.
    assert len(session.calls) == 2


def test_for_github_passes_session_through():
    """OTAClient.for_github must forward the session to the instance."""
    session = _FakeSession(_newer_manifest_dict())
    client = OTAClient.for_github("owner", "repo", session=session)
    assert client.session is session


def test_no_session_falls_back_to_module_requests(monkeypatch):
    """Desktop default: with no session, the module-level requests.get is used."""
    calls = []

    class _DesktopModule:
        def get(self, url, timeout=None):
            calls.append((url, timeout))
            return _FakeResponse(_newer_manifest_dict())

    monkeypatch.setattr("scrollkit.ota.client.requests", _DesktopModule())

    client = OTAClient(
        update_server_url="https://raw.githubusercontent.com/owner/repo/releases",
        current_version="1.0.0",
    )

    has_update, manifest = client.check_for_updates()

    assert has_update is True
    assert manifest.version == "2.0.0"
    assert [u.rsplit("/", 1)[1] for u, _ in calls] == [
        "version.txt", "manifest.json"]
