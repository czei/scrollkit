# Copyright (c) 2024-2026 Michael Czeiszperger
"""Display-progress + staged-install adapter over an OTAClient.

Uses a fake client (no network/filesystem) and the shared ``mock_display``
fixture (async clear/draw_text/show). The adapter must never propagate an error
into the OTA/boot flow.
"""
from unittest.mock import MagicMock

from scrollkit.ota.display_progress import OTAProgressDisplay


def _fake_client(**overrides):
    client = MagicMock()
    client.update_dir = "/updates"
    client.check_for_updates.return_value = (False, "up to date")
    client.download_update.return_value = (True, "")
    client.apply_update.return_value = (True, "")
    for k, v in overrides.items():
        setattr(client, k, v)
    return client


def test_wires_progress_and_error_callbacks():
    client = _fake_client()
    OTAProgressDisplay(client)
    client.set_callbacks.assert_called_once()
    kwargs = client.set_callbacks.call_args.kwargs
    assert callable(kwargs["on_progress"])
    assert callable(kwargs["on_error"])


def test_has_pending_false_when_nothing_staged(tmp_path):
    client = _fake_client(update_dir=str(tmp_path))   # empty dir, no manifest.json
    ota = OTAProgressDisplay(client)
    assert ota.has_pending() is False


def test_has_pending_true_when_manifest_present(tmp_path):
    (tmp_path / "manifest.json").write_text("{}")
    ota = OTAProgressDisplay(_fake_client(update_dir=str(tmp_path)))
    assert ota.has_pending() is True


def test_schedule_update_returns_false_when_no_update():
    ota = OTAProgressDisplay(_fake_client())
    assert ota.schedule_update() is False


def test_schedule_update_downloads_when_update_available():
    client = _fake_client()
    client.check_for_updates.return_value = (True, {"version": "2.0"})
    ota = OTAProgressDisplay(client)
    assert ota.schedule_update() is True
    client.download_update.assert_called_once_with({"version": "2.0"})


def test_schedule_update_swallows_client_errors():
    client = _fake_client()
    client.check_for_updates.side_effect = RuntimeError("network down")
    ota = OTAProgressDisplay(client)
    assert ota.schedule_update() is False     # no propagation


async def test_install_pending_noop_when_nothing_staged(tmp_path, mock_display):
    ota = OTAProgressDisplay(_fake_client(update_dir=str(tmp_path)), display=mock_display)
    assert await ota.install_pending() is False
    mock_display.draw_text.assert_not_called()


async def test_install_pending_shows_frame_applies_and_reboots(tmp_path, mock_display):
    (tmp_path / "manifest.json").write_text("{}")
    client = _fake_client(update_dir=str(tmp_path))
    ota = OTAProgressDisplay(client, display=mock_display)

    assert await ota.install_pending() is True
    client.apply_update.assert_called_once()
    client.reboot_device.assert_called_once()
    # The "Installing / DO NOT / UNPLUG!" frame must have been drawn.
    drawn = [c.args[0] for c in mock_display.draw_text.call_args_list]
    assert "Installing" in drawn and "UNPLUG!" in drawn


async def test_show_centers_multiline_and_swallows_display_errors(mock_display):
    ota = OTAProgressDisplay(_fake_client(), display=mock_display)
    await ota._show(["A", "B"])
    assert mock_display.draw_text.call_count == 2
    mock_display.clear.assert_awaited()
    mock_display.show.assert_awaited()

    # A display that raises must not propagate out of the OTA flow.
    mock_display.draw_text.side_effect = RuntimeError("panel gone")
    await ota._show(["X"])     # no raise
