# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Main OTA updater class for SLDK applications.

Provides easy-to-use OTA update functionality.
"""

from __future__ import annotations

import gc
try:
    from typing import Any, Callable, Dict, Optional, Tuple, Union
except ImportError:  # CircuitPython has no 'typing' module
    pass

from ..exceptions import OTAError, UpdateError
from .client import OTAClient
from .server import OTAServer
from .manifest import UpdateManifest


class OTAUpdater:
    """High-level OTA updater for SLDK applications.

    Provides a simple interface for OTA updates:
    - Automatic update checking
    - Progress tracking
    - Error handling
    - Integration with SLDK apps
    """

    app: Any
    server_url: Optional[str]
    current_version: str
    auto_check: bool
    check_interval: int
    client: Optional[OTAClient]
    last_check_time: float
    update_available: bool
    available_manifest: Optional[UpdateManifest]
    update_status: str
    update_progress: float
    update_error: Optional[str]
    on_update_available: Optional[Callable[[UpdateManifest], None]]
    on_update_progress: Optional[Callable[[str, float], None]]
    on_update_complete: Optional[Callable[[str], None]]
    on_update_error: Optional[Callable[[str], None]]

    def __init__(
        self,
        app: Any,
        server_url: Optional[str] = None,
        current_version: Optional[str] = None,
        auto_check: bool = True,
        check_interval: int = 3600,
    ) -> None:
        """Initialize OTA updater.

        Args:
            app: SLDK application instance
            server_url: Update server URL
            current_version: Current app version
            auto_check: Enable automatic update checking
            check_interval: Check interval in seconds
        """
        self.app = app
        self.server_url = server_url
        self.current_version = current_version or getattr(app, 'version', '0.5.0')
        self.auto_check = auto_check
        self.check_interval = check_interval

        self.client = None
        if server_url:
            self.client = OTAClient(server_url, self.current_version)
            self._setup_client_callbacks()

        self.last_check_time = 0
        self.update_available = False
        self.available_manifest = None
        self.update_status = "idle"
        self.update_progress = 0.0
        self.update_error = None

        self.on_update_available = None
        self.on_update_progress = None
        self.on_update_complete = None
        self.on_update_error = None

    def _setup_client_callbacks(self) -> None:
        """Setup OTA client callbacks."""
        if not self.client:
            return

        def on_available(manifest: UpdateManifest) -> None:
            self.update_available = True
            self.available_manifest = manifest
            print(f"Update available: {manifest.version}")

            if self.on_update_available:
                self.on_update_available(manifest)

        def on_progress(message: str, progress: float) -> None:
            self.update_progress = progress
            print(f"Update progress: {message} ({progress*100:.1f}%)")

            if self.on_update_progress:
                self.on_update_progress(message, progress)

        def on_complete(version: str) -> None:
            self.update_status = "idle"
            self.update_progress = 1.0
            self.current_version = version
            print(f"Update complete: {version}")

            if self.on_update_complete:
                self.on_update_complete(version)

        def on_error(error: str) -> None:
            self.update_status = "idle"
            self.update_error = error
            print(f"Update error: {error}")

            if self.on_update_error:
                self.on_update_error(error)

        self.client.set_callbacks(
            on_available=on_available,
            on_progress=on_progress,
            on_complete=on_complete,
            on_error=on_error,
        )

    def set_callbacks(
        self,
        on_available: Optional[Callable[[UpdateManifest], None]] = None,
        on_progress: Optional[Callable[[str, float], None]] = None,
        on_complete: Optional[Callable[[str], None]] = None,
        on_error: Optional[Callable[[str], None]] = None,
    ) -> None:
        """Set update callbacks.

        Args:
            on_available: Called when update is available
            on_progress: Called during update progress
            on_complete: Called when update completes
            on_error: Called on error
        """
        if on_available:
            self.on_update_available = on_available
        if on_progress:
            self.on_update_progress = on_progress
        if on_complete:
            self.on_update_complete = on_complete
        if on_error:
            self.on_update_error = on_error

    async def check_for_updates(self) -> Tuple[bool, Union[str, UpdateManifest]]:
        """Check for available updates.

        Returns:
            tuple: (has_update, manifest_or_error)
        """
        if not self.client:
            return False, "No update server configured"

        try:
            self.update_status = "checking"
            self.update_error = None

            try:
                import time
                self.last_check_time = time.monotonic()
            except Exception:
                pass

            has_update, result = self.client.check_for_updates()

            if has_update:
                self.update_available = True
                self.available_manifest = result

            self.update_status = "idle"
            return has_update, result

        except OTAError:
            raise
        except Exception as e:
            self.update_status = "idle"
            self.update_error = str(e)
            return False, str(e)
        finally:
            gc.collect()

    async def download_update(self, manifest: Optional[UpdateManifest] = None) -> Tuple[bool, str]:
        """Download available update.

        Args:
            manifest: Update manifest (uses available if None)

        Returns:
            tuple: (success, error_message)
        """
        if not self.client:
            return False, "No update client available"

        if not manifest and not self.available_manifest:
            return False, "No update available"

        try:
            self.update_status = "downloading"
            self.update_error = None

            success, error = self.client.download_update(manifest)

            if not success:
                self.update_status = "idle"
                self.update_error = error

            return success, error

        except OTAError:
            raise
        except Exception as e:
            self.update_status = "idle"
            self.update_error = str(e)
            return False, str(e)
        finally:
            gc.collect()

    async def install_update(self, manifest: Optional[UpdateManifest] = None, reboot: bool = True) -> Tuple[bool, str]:
        """Install downloaded update.

        Args:
            manifest: Update manifest (uses available if None)
            reboot: Whether to reboot after install

        Returns:
            tuple: (success, error_message)
        """
        if not self.client:
            return False, "No update client available"

        try:
            self.update_status = "installing"
            self.update_error = None

            success, error = self.client.apply_update(manifest)

            if success:
                self.update_available = False
                self.available_manifest = None

                if reboot:
                    print("Rebooting to complete update...")
                    try:
                        import time
                        time.sleep(2)
                    except Exception:
                        pass

                    self.client.reboot_device()
            else:
                self.update_status = "idle"
                self.update_error = error

            return success, error

        except OTAError:
            raise
        except UpdateError:
            raise
        except Exception as e:
            self.update_status = "idle"
            self.update_error = str(e)
            return False, str(e)
        finally:
            gc.collect()

    async def update_now(self, reboot: bool = True) -> Tuple[bool, str]:
        """Download and install update immediately.

        Args:
            reboot: Whether to reboot after install

        Returns:
            tuple: (success, error_message)
        """
        try:
            if not self.available_manifest:
                has_update, result = await self.check_for_updates()
                if not has_update:
                    return False, f"No updates available: {result}"

            success, error = await self.download_update()
            if not success:
                return False, f"Download failed: {error}"

            success, error = await self.install_update(reboot=reboot)
            if not success:
                return False, f"Install failed: {error}"

            return True, ""

        except OTAError:
            raise
        except UpdateError:
            raise
        except Exception as e:
            return False, str(e)

    async def auto_update_check(self) -> None:
        """Perform automatic update check."""
        if not self.auto_check or not self.client:
            return

        try:
            import time
            current_time = time.monotonic()

            if current_time - self.last_check_time < self.check_interval:
                return

            await self.check_for_updates()

        except Exception as e:
            print(f"Auto update check error: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get current update status.

        Returns:
            dict: Status information
        """
        return {
            'current_version': self.current_version,
            'update_available': self.update_available,
            'available_version': self.available_manifest.version if self.available_manifest else None,
            'status': self.update_status,
            'progress': self.update_progress,
            'error': self.update_error,
            'last_check': self.last_check_time,
            'auto_check': self.auto_check,
        }

    def enable_auto_check(self, enabled: bool = True, interval: Optional[int] = None) -> None:
        """Enable/disable automatic update checking.

        Args:
            enabled: Whether to enable auto-check
            interval: Check interval in seconds
        """
        self.auto_check = enabled
        if interval is not None:
            self.check_interval = interval

