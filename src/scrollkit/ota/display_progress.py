# Copyright (c) 2024-2026 Michael Czeiszperger
"""Display-progress + staged-install flow around an ``OTAClient``.

``OTAClient`` is headless: it downloads/applies updates and reports progress
through callbacks, but knows nothing about a display. This adapter wires those
callbacks to an on-panel status frame and owns the staged-install UX (show
"Installing… DO NOT UNPLUG!", apply, reboot), so an app gets a complete on-device
update experience without coupling the client to the display.

It takes an ALREADY-CONFIGURED client (e.g. ``OTAClient.for_github(...)``), so the
update source/channel stays the app's concern — this layer is source-agnostic::

    from scrollkit.ota.client import OTAClient
    from scrollkit.ota.display_progress import OTAProgressDisplay

    client = OTAClient.for_github("owner", "repo", branch="live",
                                  current_version="1.0.0")
    ota = OTAProgressDisplay(client, display=app.display)
    # on boot, before the display loop starts:
    await ota.install_pending()
    # from a web "update" route (synchronous, safe off the display loop):
    ota.schedule_update()      # then reboot; install_pending() applies it next boot

Every method is defensive — a display or client error is swallowed rather than
propagated into the boot/OTA flow.
"""
from __future__ import annotations

import os


__all__ = ['OTAProgressDisplay']

class OTAProgressDisplay:
    """Display-progress adapter + staged-install flow over an ``OTAClient``."""

    def __init__(self, client, display=None):
        self.client = client
        self.display = display
        self._last_msg = None
        self.client.set_callbacks(on_progress=self._on_progress,
                                  on_error=self._on_error)

    def attach_display(self, display):
        """Attach (or replace) the display used for progress frames."""
        self.display = display

    # ---- callbacks (sync; the OTAClient calls these) ----
    def _on_progress(self, message, progress):
        self._last_msg = message
        print("OTA: %s (%.0f%%)" % (message, (progress or 0) * 100))

    def _on_error(self, message):
        print("OTA error:", message)

    # ---- staged install flow ----
    def has_pending(self):
        """True if an update has been downloaded to the staging dir.

        ``os.stat`` (not ``os.path.exists``) — CircuitPython has no ``os.path``.
        """
        try:
            os.stat("%s/manifest.json" % self.client.update_dir)
            return True
        except OSError:
            return False

    def schedule_update(self):
        """Check for + download a newer release. Returns True if one is staged.

        Synchronous (callable from the web request thread). The caller reboots so
        ``install_pending()`` applies it on the next boot.
        """
        try:
            has_update, info = self.client.check_for_updates()
            if not has_update:
                return False
            ok, _err = self.client.download_update(info)
            return bool(ok)
        except Exception as e:  # never crash the request/app
            print("OTA schedule failed:", e)
            return False

    async def install_pending(self):
        """If an update is staged, show progress, apply it, and reboot. Returns bool."""
        if not self.has_pending():
            return False
        await self._show(["Installing", "DO NOT", "UNPLUG!"])
        try:
            ok, err = self.client.apply_update()
        except Exception as e:
            print("OTA apply failed:", e)
            return False
        if ok:
            await self._show(["Updated!", "Reboot..."])
            self.client.reboot_device()
            return True
        print("OTA apply error:", err)
        return False

    async def _show(self, lines, color=0xFFAA00):
        """Paint a short multi-line status frame, vertically centered.

        Keep each line <= ~10 chars: a 64px panel fits ~10 glyphs at the default
        font, so a single long "Installing update... Do not unplug!" line runs off
        the edge and clips — exactly the message the user must be able to read. The
        install is one blocking call (no display loop), so a horizontal scroll
        couldn't animate; stacked short lines keep it legible. ``lines`` may be a
        single string. Defensive — never raises into the OTA flow.
        """
        if not self.display:
            return
        if isinstance(lines, str):
            lines = [lines]
        try:
            await self.display.clear()
            line_h = 9                      # ~8px glyphs + 1px gap
            height = getattr(self.display, "height", 32)
            top = max(0, (height - len(lines) * line_h) // 2)
            for i, line in enumerate(lines):
                # draw_text y is the BASELINE; sit it near the bottom of each band.
                await self.display.draw_text(line, 1, top + i * line_h + 7, color)
            await self.display.show()
        except Exception:
            pass
