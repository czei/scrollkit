"""Resilience tests for HttpClient — the silent persistent-fetch-failure fix.

Reproduces the field outage (a wedged adafruit_requests session whose every
fetch fails identically until reboot, with an empty "Last error") and asserts the
library now (1) rebuilds the session on any repeated failure, (2) surfaces the
real cause, and (3) self-recovers once the session works again.
"""
import sys
import types

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from scrollkit.network.http_client import HttpClient


def _adafruit_client(session, **kw):
    """An HttpClient pinned to the adafruit (device) path with a mock session."""
    client = HttpClient(session=session, **kw)
    client.using_adafruit = True
    return client


class TestSessionRebuild:
    @pytest.mark.asyncio
    async def test_session_rebuilt_after_repeated_failures(self):
        """A wedged session (every get fails) is rebuilt once the consecutive
        failure count crosses the threshold — the in-place root-cause repair."""
        session = MagicMock()
        session.get.side_effect = OSError("read timeout")  # NOT OutOfRetries
        client = _adafruit_client(session, session_rebuild_threshold=2)

        with patch.object(client, "_rebuild_session", return_value=True) as rebuild:
            with patch("asyncio.sleep", new=AsyncMock()):
                with patch("scrollkit.network.http_client.logger"):
                    resp = await client.get("https://example.com/api", max_retries=3)

        # threshold=2: attempt1 -> count 1, attempt2 -> count 2 -> rebuild fires.
        assert rebuild.called
        assert resp.status_code == 500

    @pytest.mark.asyncio
    async def test_single_failure_does_not_rebuild(self):
        """One blip must NOT rebuild the pool (avoid thrash) — rebuild only on a
        repeated failure run."""
        session = MagicMock()
        # Fail once, then succeed.
        good = MagicMock(status_code=200, text="{}")
        session.get.side_effect = [OSError("blip"), good]
        client = _adafruit_client(session, session_rebuild_threshold=2)

        with patch.object(client, "_rebuild_session", return_value=True) as rebuild:
            with patch("asyncio.sleep", new=AsyncMock()):
                with patch("scrollkit.network.http_client.logger"):
                    resp = await client.get("https://example.com/api", max_retries=3)

        assert not rebuild.called
        assert resp.status_code == 200

    def test_rebuild_session_creates_fresh_session(self):
        """_rebuild_session swaps in a brand-new Session from a fresh
        SocketPool(wifi.radio) + ssl context (the wedge-clearing mechanism),
        exercised on desktop via injected fake device modules."""
        old_session = MagicMock(name="old_session")
        client = _adafruit_client(old_session)

        new_session = MagicMock(name="new_session")
        fake_pool = MagicMock(name="pool_instance")

        socketpool = types.ModuleType("socketpool")
        socketpool.SocketPool = MagicMock(return_value=fake_pool)
        wifi = types.ModuleType("wifi")
        wifi.radio = MagicMock(name="radio")
        ssl = types.ModuleType("ssl")
        ssl.create_default_context = MagicMock(return_value=MagicMock(name="ssl_ctx"))
        adafruit_requests = types.ModuleType("adafruit_requests")
        adafruit_requests.Session = MagicMock(return_value=new_session)

        injected = {
            "socketpool": socketpool,
            "wifi": wifi,
            "ssl": ssl,
            "adafruit_requests": adafruit_requests,
        }
        with patch.dict(sys.modules, injected):
            with patch("scrollkit.network.http_client.logger"):
                ok = client._rebuild_session()

        assert ok is True
        assert client.session is new_session
        socketpool.SocketPool.assert_called_once_with(wifi.radio)
        adafruit_requests.Session.assert_called_once_with(
            fake_pool, ssl.create_default_context.return_value)

    def test_rebuild_session_noop_on_desktop(self):
        """On desktop (urllib path, no session) rebuild is a no-op returning
        False — never raises, never breaks the simulator."""
        client = HttpClient(session=None)
        client.using_adafruit = False
        assert client._rebuild_session() is False


class TestErrorSurfaced:
    @pytest.mark.asyncio
    async def test_failure_response_carries_cause(self):
        """The synthesized 500 carries the real exception on .error and
        client.last_error stays set — no more opaque empty 'Last error'."""
        boom = OSError("mbedtls handshake failed")
        session = MagicMock()
        session.get.side_effect = boom
        client = _adafruit_client(session, session_rebuild_threshold=99)

        with patch.object(client, "_rebuild_session", return_value=True):
            with patch("asyncio.sleep", new=AsyncMock()):
                with patch("scrollkit.network.http_client.logger"):
                    resp = await client.get("https://example.com/api", max_retries=3)

        assert resp.status_code == 500
        assert resp.error is boom
        assert client.last_error is boom

    @pytest.mark.asyncio
    async def test_success_clears_error_and_stamps_time(self):
        """A success after failures clears last_error, resets the streak, and
        starts the staleness clock (seconds_since_last_success)."""
        good = MagicMock(status_code=200, text="{}")
        session = MagicMock()
        session.get.side_effect = [OSError("blip"), good]
        client = _adafruit_client(session, session_rebuild_threshold=99)

        assert client.seconds_since_last_success() is None
        with patch("asyncio.sleep", new=AsyncMock()):
            with patch("scrollkit.network.http_client.logger"):
                resp = await client.get("https://example.com/api", max_retries=3)

        assert resp.status_code == 200
        assert client.last_error is None
        assert client._failures_since_rebuild == 0
        assert client.seconds_since_last_success() is not None


class TestWedgeRecovery:
    @pytest.mark.asyncio
    async def test_wedged_session_recovers_after_rebuild(self):
        """End-to-end repro: the session is wedged (fails) until a rebuild swaps
        in a working one, after which the next get() succeeds — self-recovery
        without a reboot."""
        wedged = MagicMock(name="wedged")
        wedged.get.side_effect = OSError("connection reset")
        working = MagicMock(name="working")
        working.get.return_value = MagicMock(status_code=200, text="{}")

        client = _adafruit_client(wedged, session_rebuild_threshold=2)

        def fake_rebuild():
            client.session = working
            return True

        with patch.object(client, "_rebuild_session", side_effect=fake_rebuild):
            with patch("asyncio.sleep", new=AsyncMock()):
                with patch("scrollkit.network.http_client.logger"):
                    # First call wedged -> after 2 failures the session is rebuilt;
                    # the 3rd attempt in the same call uses the working session.
                    resp = await client.get("https://example.com/api", max_retries=3)

        assert resp.status_code == 200
        assert client.session is working
