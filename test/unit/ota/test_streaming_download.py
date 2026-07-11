# Copyright (c) 2024-2026 Michael Czeiszperger
"""Streamed OTA bodies (the hot-heap MemoryError fix, 2026-07-09).

On a fragmented CircuitPython heap the largest free block is often smaller than
a ~30 KB manifest or source file, so ``response.json()`` / ``response.content``
(one contiguous allocation each) intermittently raise MemoryError — the
"Check for Update ... MemoryError" that recurred for days on the MatrixPortal.
The client now streams bodies to flash in small chunks whenever the response
supports ``iter_content``, parsing the manifest incrementally from the file.

These tests pin that behavior: the streaming path is USED whenever available
(``.json()`` / ``.content`` must never be touched), verification hashes per
chunk, the manifest temp file is cleaned up, and a corrupt body never survives
in the staging area.
"""

import json

from scrollkit.ota.client import OTAClient
from scrollkit.ota.manifest import UpdateManifest


class _ChunkedResponse:
    """adafruit_requests-shaped response: the body is ONLY reachable via
    ``iter_content`` — touching ``.content`` or ``.json()`` fails the test,
    proving the client took the streaming path."""

    def __init__(self, status_code, body):
        self.status_code = status_code
        self._body = body

    def iter_content(self, chunk_size=32):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i:i + chunk_size]

    @property
    def content(self):
        raise AssertionError("streaming path must not touch .content")

    def json(self):
        raise AssertionError("streaming path must not call .json()")

    def close(self):
        pass


class _ChunkedSession:
    def __init__(self, routes):
        self._routes = routes  # url suffix -> body bytes

    def get(self, url, timeout=None):
        for suffix, body in self._routes.items():
            if url.endswith(suffix):
                return _ChunkedResponse(200, body)
        return _ChunkedResponse(404, b"")


def _client(tmp_path, routes, version="1.0.0"):
    return OTAClient("https://example.invalid/releases", current_version=version,
                     update_dir=str(tmp_path / "updates"),
                     backup_dir=str(tmp_path / "backup"),
                     session=_ChunkedSession(routes))


def test_check_for_updates_streams_manifest_to_file(tmp_path):
    m = UpdateManifest(version="2.0.0", description="test")
    m.add_file("src/main.py", content=b"print('hi')\n")
    client = _client(tmp_path, {"manifest.json": json.dumps(m.to_dict()).encode()})

    ok, got = client.check_for_updates()

    assert ok is True and got.version == "2.0.0"
    # the streamed temp file must not linger in the staging area
    assert not (tmp_path / "updates" / "manifest.part").exists()


def test_download_file_streams_and_verifies_per_chunk(tmp_path):
    body = b"x" * 3000                    # spans several 1024-byte chunks
    m = UpdateManifest(version="2.0.0", description="test")
    m.add_file("src/big.py", content=body)
    client = _client(tmp_path, {
        "manifest.json": json.dumps(m.to_dict()).encode(),
        "src/big.py": body,
    })

    ok, msg = client.download_update(m)

    assert ok is True, msg
    staged = tmp_path / "updates" / "src" / "big.py"
    assert staged.read_bytes() == body


def test_download_file_removes_staged_file_on_checksum_mismatch(tmp_path):
    good = b"y" * 2048
    m = UpdateManifest(version="2.0.0", description="test")
    m.add_file("src/big.py", content=good)
    client = _client(tmp_path, {
        "manifest.json": json.dumps(m.to_dict()).encode(),
        "src/big.py": good[:-1] + b"!",   # same size, wrong hash
    })

    ok, msg = client.download_update(m)

    assert ok is False and "Checksum" in msg
    assert not (tmp_path / "updates" / "src" / "big.py").exists()


class _TextResponse:
    """version.txt-shaped response: tiny text body, no iter_content needed."""

    def __init__(self, status_code, text):
        self.status_code = status_code
        self.text = text

    def json(self):
        raise AssertionError("version fast path must not call .json()")

    def close(self):
        pass


class _VersionedSession:
    """Serves version.txt as text; anything else via _ChunkedResponse routes.
    Records every URL so tests can assert the manifest was (not) fetched."""

    def __init__(self, version_text, routes=None, version_status=200):
        self._version_text = version_text
        self._version_status = version_status
        self._routes = routes or {}
        self.urls = []

    def get(self, url, timeout=None):
        self.urls.append(url)
        if url.endswith("version.txt"):
            return _TextResponse(self._version_status, self._version_text)
        for suffix, body in self._routes.items():
            if url.endswith(suffix):
                return _ChunkedResponse(200, body)
        return _ChunkedResponse(404, b"")


def _version_client(tmp_path, session, current="1.0.0"):
    return OTAClient("https://example.invalid/releases", current_version=current,
                     update_dir=str(tmp_path / "updates"),
                     backup_dir=str(tmp_path / "backup"), session=session)


def test_up_to_date_answered_by_version_txt_alone(tmp_path):
    """The common case costs ~6 bytes: equal version -> UP_TO_DATE with the
    manifest never requested."""
    session = _VersionedSession("1.0.0\n")
    client = _version_client(tmp_path, session)

    ok, reason = client.check_for_updates()

    assert ok is False and reason == "No updates available"
    assert not any(u.endswith("manifest.json") for u in session.urls)


def test_newer_version_txt_proceeds_to_manifest(tmp_path):
    m = UpdateManifest(version="2.0.0", description="test")
    m.add_file("src/main.py", content=b"print('hi')\n")
    session = _VersionedSession(
        "2.0.0\n", routes={"manifest.json": json.dumps(m.to_dict()).encode()})
    client = _version_client(tmp_path, session)

    ok, got = client.check_for_updates()

    assert ok is True and got.version == "2.0.0"
    assert any(u.endswith("manifest.json") for u in session.urls)


def test_version_txt_404_falls_back_to_manifest(tmp_path):
    """Channels published before version.txt existed keep working."""
    m = UpdateManifest(version="2.0.0", description="test")
    m.add_file("src/main.py", content=b"print('hi')\n")
    session = _VersionedSession(
        "ignored", version_status=404,
        routes={"manifest.json": json.dumps(m.to_dict()).encode()})
    client = _version_client(tmp_path, session)

    ok, got = client.check_for_updates()
    assert ok is True and got.version == "2.0.0"


def test_junk_version_txt_never_fakes_up_to_date(tmp_path):
    """parse_version maps junk to (0,0,0); an unvalidated error page would fake
    'up to date'. Junk must fall through to the manifest instead."""
    m = UpdateManifest(version="2.0.0", description="test")
    m.add_file("src/main.py", content=b"print('hi')\n")
    session = _VersionedSession(
        "<html>404: Not Found</html>",
        routes={"manifest.json": json.dumps(m.to_dict()).encode()})
    client = _version_client(tmp_path, session)

    ok, got = client.check_for_updates()
    assert ok is True and got.version == "2.0.0"
