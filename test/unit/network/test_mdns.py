# Copyright (c) 2024-2026 Michael Czeiszperger
"""mDNS advertising wrapper.

On desktop the ``mdns``/``wifi`` modules don't exist, so ``advertise()`` is a
no-op returning ``None``. The success path and the never-raise contract are
exercised by faking ``wifi``/``mdns`` in ``sys.modules``.
"""
import sys
from unittest.mock import MagicMock, patch

from scrollkit.network.mdns import advertise


def test_advertise_returns_none_off_device():
    """No CircuitPython mdns module -> no-op, returns None (never raises)."""
    assert advertise("themeparkwaits") is None


def test_advertise_registers_service_with_faked_mdns():
    fake_wifi = MagicMock()
    fake_mdns = MagicMock()
    server = MagicMock()
    fake_mdns.Server.return_value = server

    with patch.dict(sys.modules, {"wifi": fake_wifi, "mdns": fake_mdns}):
        result = advertise("themeparkwaits", port=8080)

    assert result is server
    fake_mdns.Server.assert_called_once_with(fake_wifi.radio)
    assert server.hostname == "themeparkwaits"
    server.advertise_service.assert_called_once_with(
        service_type="_http", protocol="_tcp", port=8080)


def test_advertise_never_raises_on_failure():
    """A radio/responder that throws must yield None, not propagate (boot safety)."""
    fake_wifi = MagicMock()
    fake_mdns = MagicMock()
    fake_mdns.Server.side_effect = RuntimeError("no radio")

    with patch.dict(sys.modules, {"wifi": fake_wifi, "mdns": fake_mdns}):
        assert advertise("themeparkwaits") is None
