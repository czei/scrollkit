# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""OTA client typed-error boundary (0.8.2).

_http_get raises NetworkError on a transport failure; _download_file raises
OTAError on a server/size/checksum mismatch. Both are INTERNAL — the public
methods (check_for_updates / download_update) catch them and keep returning the
(ok, reason) tuple contract, so the typed errors never escape the public API.
"""

import hashlib

import pytest

from scrollkit.exceptions import NetworkError, OTAError
from scrollkit.ota.client import OTAClient
from scrollkit.ota.manifest import UpdateManifest


class _BoomSession:
    """A Session-style client whose every GET fails at the transport layer."""

    def get(self, url, timeout=None):
        raise OSError("connection refused")


class _Response:
    def __init__(self, status_code, content=b"", payload=None):
        self.status_code = status_code
        self.content = content
        self._payload = payload

    def json(self):
        return self._payload

    def close(self):
        pass


class _FileSession:
    """Serves manifest.json then a single file body for the download path."""

    def __init__(self, manifest_dict, file_body):
        self._manifest = manifest_dict
        self._file_body = file_body

    def get(self, url, timeout=None):
        if url.endswith("manifest.json"):
            return _Response(200, payload=self._manifest)
        return _Response(200, content=self._file_body)


def _manifest_with_file(body):
    m = UpdateManifest(version="2.0.0", description="test")
    m.add_file("src/main.py", content=body)
    return m


def test_http_get_wraps_transport_failure_in_network_error():
    client = OTAClient("https://example.invalid/releases", current_version="1.0.0",
                       session=_BoomSession())
    with pytest.raises(NetworkError) as exc:
        client._http_get("https://example.invalid/releases/manifest.json")
    assert "connection refused" in str(exc.value)


def test_check_for_updates_returns_tuple_on_network_failure():
    """A NetworkError from _http_get must NOT escape — the public contract is a tuple."""
    client = OTAClient("https://example.invalid/releases", current_version="1.0.0",
                       session=_BoomSession())
    result = client.check_for_updates()
    assert isinstance(result, tuple) and len(result) == 2
    assert result[0] is False
    assert isinstance(result[1], str)


def test_download_update_reports_checksum_mismatch_as_tuple(tmp_path):
    """A corrupted file body (checksum mismatch) surfaces as (False, '...Checksum...'),
    proving _download_file raises OTAError internally and download_update catches it."""
    good_body = b"print('hello')\n"
    manifest = _manifest_with_file(good_body)
    # Serve a SAME-LENGTH but different body so it clears the size check and
    # fails on the SHA-256 checksum instead.
    corrupt = b"print('world')\n"
    assert len(corrupt) == len(good_body)
    session = _FileSession(manifest.to_dict(), corrupt)

    client = OTAClient("https://example.invalid/releases", current_version="1.0.0",
                       update_dir=str(tmp_path / "updates"),
                       backup_dir=str(tmp_path / "backup"),
                       session=session)

    ok, err = client.download_update(manifest)
    assert ok is False
    assert "Checksum mismatch" in err


def test_download_update_reports_size_mismatch_as_tuple(tmp_path):
    """A short body (size mismatch) also surfaces as a (False, reason) tuple."""
    manifest = _manifest_with_file(b"the-real-body-bytes")
    session = _FileSession(manifest.to_dict(), b"short")

    client = OTAClient("https://example.invalid/releases", current_version="1.0.0",
                       update_dir=str(tmp_path / "updates"),
                       backup_dir=str(tmp_path / "backup"),
                       session=session)

    ok, err = client.download_update(manifest)
    assert ok is False
    assert "Size mismatch" in err
