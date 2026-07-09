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
