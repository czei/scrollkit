# Copyright (c) 2024-2026 Michael Czeiszperger
"""OTA checksum algorithm selection (the CP 9.2.x sha256 gap, 2026-07-20).

CircuitPython 9.2.x ships a ``hashlib`` with NO sha256 —
``hashlib.new("sha256")`` raises ``ValueError: Unsupported hash algorithm``
(verified on a MatrixPortal S3 / CP 9.2.8). Every OTA download therefore failed
its checksum and rolled back: 3.x OTA was 10.x-only in practice with no error
that named the cause. The client now picks the strongest digest the RUNTIME can
compute — sha256 where available, native ``binascii.crc32`` otherwise — and
manifests carry both. Verification is never skipped: a manifest with no usable
digest is a loud failure, not a silent pass.
"""

import binascii
import hashlib

import pytest

from scrollkit.ota import client as ota_client
from scrollkit.ota.client import (_Crc32Digest, _expected, _hexdigest,
                                  _new_digest, OTAError)


@pytest.fixture(autouse=True)
def _reset_probe():
    """The sha256 probe is cached module-wide; clear it around each test."""
    ota_client._SHA256_OK = None
    yield
    ota_client._SHA256_OK = None


def _no_sha256(monkeypatch):
    """Simulate the CP 9.2.x hashlib: new() exists, sha256 unsupported."""
    def _raise(name, *a, **kw):
        raise ValueError("Unsupported hash algorithm")
    monkeypatch.setattr(ota_client.hashlib, "new", _raise, raising=False)
    monkeypatch.delattr(ota_client.hashlib, "sha256", raising=False)


class TestDigestSelection:
    def test_prefers_sha256_when_available(self):
        digest, key = _new_digest()
        assert key == "checksum"
        digest.update(b"hello")
        assert _hexdigest(digest) == hashlib.sha256(b"hello").hexdigest()

    def test_falls_back_to_crc32_without_sha256(self, monkeypatch):
        _no_sha256(monkeypatch)
        digest, key = _new_digest()
        assert key == "crc32", "CP 9.2.x must fall back, not fail"
        digest.update(b"hello")
        assert _hexdigest(digest) == "%08x" % (binascii.crc32(b"hello") & 0xFFFFFFFF)

    def test_crc32_digest_matches_binascii_across_chunks(self):
        """Chunked updates must equal a one-shot crc32 (streamed downloads
        feed the digest per chunk)."""
        body = bytes(range(256)) * 7
        d = _Crc32Digest()
        for i in range(0, len(body), 13):
            d.update(body[i:i + 13])
        assert d.hexdigest() == "%08x" % (binascii.crc32(body) & 0xFFFFFFFF)

    def test_probe_is_cached(self, monkeypatch):
        calls = []
        real_new = ota_client.hashlib.new

        def _counting(name, *a, **kw):
            calls.append(name)
            return real_new(name, *a, **kw)

        monkeypatch.delattr(ota_client.hashlib, "sha256", raising=False)
        monkeypatch.setattr(ota_client.hashlib, "new", _counting, raising=False)
        for _ in range(5):
            _new_digest()
        # One probe call, plus one construction per _new_digest() call.
        assert calls.count("sha256") <= 6


class TestNeverSkipsVerification:
    """The one thing that must never happen: a download accepted unverified."""

    def test_missing_digest_field_raises(self):
        with pytest.raises(OTAError) as e:
            _expected({"size": 10}, "crc32", "/src/app.py")
        assert "cannot verify" in str(e.value)

    def test_empty_digest_field_raises(self):
        with pytest.raises(OTAError):
            _expected({"size": 10, "crc32": ""}, "crc32", "/src/app.py")

    def test_present_digest_returned(self):
        assert _expected({"crc32": "deadbeef"}, "crc32", "/x") == "deadbeef"

    def test_old_manifest_on_crc32_device_fails_loudly(self, monkeypatch):
        """A pre-dual-checksum manifest (sha256 only) reaching a 9.2.x device
        must raise a NAMED error — not silently install unverified bytes."""
        _no_sha256(monkeypatch)
        _digest, key = _new_digest()
        legacy = {"size": 3, "checksum": "a" * 64}      # no crc32
        with pytest.raises(OTAError) as e:
            _expected(legacy, key, "/src/app.py")
        assert "crc32" in str(e.value)


class TestManifestCarriesBothDigests:
    def test_publisher_emits_sha256_and_crc32(self, tmp_path):
        """The app's generator must emit both so either runtime can verify."""
        import importlib.util
        import os
        gen = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
            os.path.dirname(os.path.abspath(__file__))))),
            "..", "themeparkwaits", "scripts", "make_manifest.py")
        gen = os.path.normpath(gen)
        if not os.path.exists(gen):
            pytest.skip("app repo not alongside the library checkout")
        spec = importlib.util.spec_from_file_location("make_manifest", gen)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)

        src = tmp_path / "src"
        src.mkdir()
        (src / "app.py").write_bytes(b"print('hi')\n")
        out = tmp_path / "out"
        manifest = mod.build_manifest(str(src), str(out), device_root="/src",
                                      version="1.2.3")
        info = manifest["files"]["/src/app.py"]
        assert len(info["checksum"]) == 64                  # sha256 hex
        assert info["crc32"] == "%08x" % (
            binascii.crc32(b"print('hi')\n") & 0xFFFFFFFF)
