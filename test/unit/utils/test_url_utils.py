"""Contracts for the small CircuitPython-safe URL and credentials helpers."""

import sys
import types

from scrollkit.utils.url_utils import load_credentials, url_decode


def test_url_decode_handles_spaces_valid_and_malformed_escapes():
    assert url_decode("hello+world%21") == "hello world!"
    assert url_decode("%4a%4B") == "JK"
    assert url_decode("bad%2G%") == "bad%2G%"


def test_load_credentials_reads_device_secrets(monkeypatch):
    secrets_module = types.SimpleNamespace(secrets={"ssid": "park", "password": "lamp"})
    monkeypatch.setitem(sys.modules, "secrets", secrets_module)
    assert load_credentials() == ("park", "lamp")


def test_load_credentials_falls_back_when_secrets_module_has_no_mapping(monkeypatch):
    monkeypatch.setitem(sys.modules, "secrets", types.ModuleType("secrets"))
    assert load_credentials() == ("", "")
