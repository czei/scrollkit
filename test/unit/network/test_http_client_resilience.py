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


class TestSocketRelease:
    """The success path must close the native response so its socket returns to
    the ~4-socket pool. Leaking it on every successful fetch exhausts the pool and
    wedges the device with permanent OSError 16 (EBUSY) — the original field bug
    that no caller (not even the demos) guarded against, because they never
    ``.close()`` the response."""

    @pytest.mark.asyncio
    async def test_async_get_closes_native_response_on_success(self):
        native = MagicMock(status_code=200, text='{"ok": true}', headers={"X": "y"})
        session = MagicMock()
        session.get.return_value = native
        client = _adafruit_client(session)

        with patch("scrollkit.network.http_client.logger"):
            resp = await client.get("https://example.com/api", max_retries=1)

        # Socket released: the native response was closed exactly once.
        native.close.assert_called_once()
        # And the caller got a detached, socket-free object with the data intact.
        assert resp is not native
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        assert resp.headers == {"X": "y"}

    def test_sync_get_closes_native_response_on_success(self):
        native = MagicMock(status_code=200, text='{"ok": true}', headers={})
        session = MagicMock()
        session.get.return_value = native
        client = _adafruit_client(session)

        with patch("scrollkit.network.http_client.logger"):
            resp = client.get_sync("https://example.com/api", max_retries=1)

        native.close.assert_called_once()
        assert resp is not native
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    @pytest.mark.asyncio
    async def test_no_socket_leak_over_many_fetches(self):
        """Every one of N successful fetches must close its native response — the
        leak that exhausted the pool was one un-closed socket PER successful get."""
        session = MagicMock()
        natives = [MagicMock(status_code=200, text="{}", headers={}) for _ in range(10)]
        session.get.side_effect = natives
        client = _adafruit_client(session)

        with patch("scrollkit.network.http_client.logger"):
            for _ in range(10):
                await client.get("https://example.com/api", max_retries=1)

        assert all(n.close.call_count == 1 for n in natives)

    @pytest.mark.asyncio
    async def test_post_closes_native_response_and_passes_timeout(self):
        """post() has the same socket contract as get(): close the native response
        on success AND pass a timeout so a hung POST can't block the loop."""
        native = MagicMock(status_code=201, text='{"created": true}', headers={})
        session = MagicMock()
        session.post.return_value = native
        client = _adafruit_client(session)

        with patch("scrollkit.network.http_client.logger"):
            resp = await client.post("https://example.com/api", data={"a": 1})

        native.close.assert_called_once()
        assert resp is not native
        assert resp.status_code == 201
        assert resp.json() == {"created": True}
        _, kwargs = session.post.call_args
        assert kwargs.get("timeout") == client.timeout

    @pytest.mark.asyncio
    async def test_post_failure_is_recorded_for_session_rebuild(self):
        """A POST failure must feed _note_failure (surface the cause + count toward
        a session rebuild), even though POST itself is single-shot."""
        boom = OSError("connection reset")
        session = MagicMock()
        session.post.side_effect = boom
        client = _adafruit_client(session, session_rebuild_threshold=99)

        with patch("scrollkit.network.http_client.logger"):
            resp = await client.post("https://example.com/api", data={"a": 1})

        assert resp.status_code == 500
        assert resp.error is boom
        assert client.last_error is boom
        assert client._failures_since_rebuild == 1


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
