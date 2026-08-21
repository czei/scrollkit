"""Contracts for the small CircuitPython-safe URL and credentials helpers."""

import sys
import types

from scrollkit.utils.url_utils import load_credentials, url_decode


def test_url_decode_handles_spaces_valid_and_malformed_escapes():
    assert url_decode("hello+world%21") == "hello world!"
    assert url_decode("%4a%4B") == "JK"
    assert url_decode("bad%2G%") == "bad%2G%"


def test_url_decode_reassembles_multi_byte_utf8():
    """Percent-escapes are BYTES; browsers encode form fields as UTF-8.

    Decoding each escape with chr() individually turned 'é' (%C3%A9) into 'Ã©'
    — silently, in whatever the user typed. For a WiFi password that means the
    board saves something the user never entered and can never join, while the
    setup portal reports success, because nothing checks before the corruption
    happens.
    """
    assert url_decode("Caf%C3%A9") == "Café"
    assert url_decode("Pi%C3%B1ata+Net") == "Piñata Net"
    assert url_decode("Stra%C3%9Fe") == "Straße"
    assert url_decode("%C2%A35note") == "£5note"
    assert url_decode("smart%E2%80%99quote") == "smart’quote"      # 3-byte
    assert url_decode("emoji%F0%9F%8E%A2") == "emoji🎢"             # 4-byte


def test_url_decode_round_trips_what_a_browser_sends():
    import urllib.parse
    for original in ("Café£5", "p@ss w0rd!", "#ffffff", "a+b", "50%",
                     "100%41", "naïve", "plain-ascii"):
        wire = urllib.parse.quote_plus(original)
        assert url_decode(wire) == original, original


def test_url_decode_leaves_undecodable_input_alone():
    """A literal '%' or a non-UTF-8 client must not lose the value entirely:
    a mangled password beats no password."""
    assert url_decode("50%off") == "50%off"
    assert url_decode("abc%") == "abc%"
    assert url_decode("%") == "%"
    assert url_decode("%ff%fe") == "\xff\xfe"      # not valid UTF-8; byte-wise


def test_load_credentials_reads_device_secrets(monkeypatch):
    secrets_module = types.SimpleNamespace(secrets={"ssid": "park", "password": "lamp"})
    monkeypatch.setitem(sys.modules, "secrets", secrets_module)
    assert load_credentials() == ("park", "lamp")


def test_load_credentials_falls_back_when_secrets_module_has_no_mapping(monkeypatch):
    monkeypatch.setitem(sys.modules, "secrets", types.ModuleType("secrets"))
    assert load_credentials() == ("", "")
