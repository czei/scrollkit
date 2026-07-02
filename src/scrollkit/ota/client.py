# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""OTA update client for CircuitPython devices.

Handles downloading and applying updates safely.
"""

from __future__ import annotations

import gc
import json
import hashlib
try:
    from typing import Any, Callable, Dict, Optional, Tuple, Union
except ImportError:  # CircuitPython has no 'typing' module
    pass

from ..exceptions import NetworkError, OTAError
from .manifest import UpdateManifest

import sys

# Decide the platform by the interpreter, not by which HTTP module happens to be
# importable: ``adafruit_requests`` is pip-installable on desktop but exposes no
# module-level ``get`` (it is Session-based), so keying off its mere presence
# mis-detected desktop as CircuitPython and crashed the update check.
if getattr(sys.implementation, "name", "") == "circuitpython":
    import adafruit_requests as requests
    import storage
    import microcontroller
    import supervisor
    PLATFORM = 'circuitpython'
else:
    try:
        import requests
        PLATFORM = 'desktop'
    except ImportError:
        requests = None
        PLATFORM = 'unknown'


__all__ = ['OTAClient']

class OTAClient:
    """OTA update client for CircuitPython devices.

    Handles the client side of OTA updates:
    - Check for updates
    - Download update packages
    - Verify integrity
    - Apply updates safely
    """

    server_url: str
    current_version: str
    update_dir: str
    backup_dir: str
    download_timeout: int
    chunk_size: int
    session: Any
    last_check: Any
    available_update: Optional[UpdateManifest]
    update_in_progress: bool
    on_update_available: Optional[Callable[[UpdateManifest], None]]
    on_update_progress: Optional[Callable[[str, float], None]]
    on_update_complete: Optional[Callable[[str], None]]
    on_update_error: Optional[Callable[[str], None]]

    @classmethod
    def for_github(cls, owner, repo, branch="releases", current_version="0.0.0",
                   update_dir="/updates", backup_dir="/backup", session=None):
        """Build an OTAClient that fetches updates from GitHub raw content.

        Constructs the base URL
        ``https://raw.githubusercontent.com/{owner}/{repo}/{branch}`` from which
        ``manifest.json`` and the files it lists are downloaded. Publish an update
        by committing a ``manifest.json`` (and the new ``/src`` files) to that
        branch — e.g. a dedicated ``releases`` branch or a tag.

        Recovery does not depend on this: the frozen ``boot.py`` + update system
        stay intact regardless of any ``/src`` payload, so a bad update can always
        be re-fetched on the next boot.

        ``session`` is an optional Session-style HTTP client (anything exposing
        ``.get(url, timeout=...)``) — on CircuitPython the app injects its
        ``adafruit_requests.Session`` here, since modern ``adafruit_requests`` has
        no module-level ``get``.
        """
        url = "https://raw.githubusercontent.com/{}/{}/{}".format(owner, repo, branch)
        return cls(url, current_version=current_version,
                   update_dir=update_dir, backup_dir=backup_dir, session=session)

    def __init__(
        self,
        update_server_url: str,
        current_version: str = "0.5.0",
        update_dir: str = "/updates",
        backup_dir: str = "/backup",
        session: Any = None,
    ) -> None:
        """Initialize OTA client.

        Args:
            update_server_url: URL of update server
            current_version: Current application version
            update_dir: Directory for downloaded updates
            backup_dir: Directory for backups
            session: Optional Session-style HTTP client (exposing
                ``.get(url, timeout=...)``). On CircuitPython modern
                ``adafruit_requests`` is Session-based and has no module-level
                ``get``, so the app injects its existing
                ``adafruit_requests.Session`` here. Read live at each request
                (see ``_http_get``), so it may be assigned/replaced after
                construction. When ``None`` the module-level ``requests.get`` is
                used (desktop, where the PyPI ``requests`` module has ``.get``).
        """
        self.server_url = update_server_url.rstrip('/')
        self.current_version = current_version
        self.update_dir = update_dir
        self.backup_dir = backup_dir
        self.download_timeout = 30
        self.chunk_size = 1024
        self.session = session

        self.last_check = None
        self.available_update = None
        self.update_in_progress = False

        self.on_update_available = None
        self.on_update_progress = None
        self.on_update_complete = None
        self.on_update_error = None

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
            on_progress: Called during download/install
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

    def _http_get(self, url: str) -> Any:
        """Perform an HTTP GET, preferring an injected Session.

        ``self.session`` is read live (never cached) so the app can create or
        rebuild the session during WiFi connect and assign ``client.session``
        right before use. When a session is present, its ``.get`` is used (modern
        ``adafruit_requests`` is Session-based and exposes no module-level
        ``get``); otherwise the module-level ``requests.get`` is used (desktop).
        """
        try:
            if self.session is not None:
                return self.session.get(url, timeout=self.download_timeout)
            return requests.get(url, timeout=self.download_timeout)
        except Exception as e:
            # Typed boundary error (no `from e` chaining: heap fragmentation on
            # CircuitPython). The public check/download methods catch it and
            # return their (ok, reason) tuple.
            raise NetworkError("OTA GET %s failed: %s: %s" % (url, type(e).__name__, e))

    def check_for_updates(self) -> Tuple[bool, Union[str, UpdateManifest]]:
        """Check if updates are available.

        Returns:
            tuple: (has_update, manifest_or_error)
        """
        if self.session is None and not requests:
            return False, "Requests library not available"

        try:
            url = f"{self.server_url}/manifest.json"
            response = self._http_get(url)

            if response.status_code != 200:
                return False, f"Server error: {response.status_code}"

            try:
                manifest_data = response.json()
                manifest = UpdateManifest.from_dict(manifest_data)
            except ValueError as e:  # CircuitPython: json.loads raises ValueError
                return False, f"Invalid manifest: {e}"

            is_valid, error = manifest.validate()
            if not is_valid:
                return False, f"Invalid manifest: {error}"

            if manifest.compare_version(self.current_version) > 0:
                self.available_update = manifest
                if self.on_update_available:
                    self.on_update_available(manifest)
                return True, manifest

            return False, "No updates available"

        except Exception as e:
            # A NetworkError from _http_get on an unreachable server lands here and
            # becomes the (False, reason) tuple the public contract promises.
            error_msg = f"Update check failed: {e}"
            if self.on_update_error:
                self.on_update_error(error_msg)
            return False, error_msg
        finally:
            if 'response' in locals():
                try:
                    response.close()
                except Exception:
                    pass
            gc.collect()

    def download_update(self, manifest: Optional[UpdateManifest] = None) -> Tuple[bool, str]:
        """Download update package.

        Args:
            manifest: Update manifest (uses available_update if None)

        Returns:
            tuple: (success, error_message)
        """
        if manifest is None:
            manifest = self.available_update

        if not manifest:
            return False, "No update manifest available"

        if self.session is None and not requests:
            return False, "Requests library not available"

        try:
            self.update_in_progress = True

            self._ensure_directory(self.update_dir)

            if PLATFORM == 'circuitpython':
                try:
                    import os
                    stat = os.statvfs('/')
                    free_space = stat[1] * stat[3]

                    required_space = manifest.calculate_total_size() * 2
                    if free_space < required_space:
                        return False, f"Insufficient storage: {free_space} < {required_space}"
                except Exception:
                    pass

            total_files = len(manifest.files)
            completed_files = 0

            for file_path, file_info in manifest.files.items():
                if self.on_update_progress:
                    progress = (completed_files / total_files) * 0.8
                    self.on_update_progress(f"Downloading {file_path}", progress)

                try:
                    self._download_file(file_path, file_info)
                except (NetworkError, OTAError) as e:
                    return False, f"Failed to download {file_path}: {e}"

                completed_files += 1
                gc.collect()

            manifest_path = f"{self.update_dir}/manifest.json"
            try:
                with open(manifest_path, 'w') as f:
                    f.write(manifest.to_json())
            except (OSError, IOError) as e:
                return False, f"Failed to save manifest: {e}"

            if self.on_update_progress:
                self.on_update_progress("Download complete", 0.8)

            return True, ""

        except Exception as e:
            error_msg = f"Download failed: {e}"
            if self.on_update_error:
                self.on_update_error(error_msg)
            return False, error_msg
        finally:
            gc.collect()

    def _download_file(self, file_path: str, file_info: Dict[str, Any]) -> None:
        """Download and verify a single file.

        Returns None on success. Raises ``OTAError`` on a server error, size
        mismatch, or checksum mismatch, and propagates ``NetworkError`` from the
        HTTP GET. ``download_update`` catches both and turns them into its
        ``(False, reason)`` tuple. The native response is always closed
        (``finally``) so its socket is released.

        Args:
            file_path: Target file path
            file_info: File metadata dict
        """
        response = None
        try:
            url = f"{self.server_url}/files/{file_path.lstrip('/')}"
            response = self._http_get(url)

            if response.status_code != 200:
                raise OTAError("Server error %d for %s"
                               % (response.status_code, file_path))

            content = response.content

            if len(content) != file_info['size']:
                raise OTAError("Size mismatch for %s: %d != %d"
                               % (file_path, len(content), file_info['size']))

            actual_checksum = hashlib.sha256(content).hexdigest()
            if actual_checksum != file_info['checksum']:
                raise OTAError("Checksum mismatch for %s" % file_path)

            local_path = f"{self.update_dir}/{file_path.lstrip('/')}"
            self._ensure_directory_for_file(local_path)

            with open(local_path, 'wb') as f:
                f.write(content)
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass

    def apply_update(self, manifest: Optional[UpdateManifest] = None) -> Tuple[bool, str]:
        """Apply downloaded update.

        Args:
            manifest: Update manifest (loads from file if None)

        Returns:
            tuple: (success, error_message)
        """
        if not manifest:
            manifest_path = f"{self.update_dir}/manifest.json"
            try:
                with open(manifest_path, 'r') as f:
                    manifest_data = json.loads(f.read())
                manifest = UpdateManifest.from_dict(manifest_data)
            except Exception as e:
                return False, f"Cannot load manifest: {e}"

        try:
            if self.on_update_progress:
                self.on_update_progress("Preparing update", 0.8)

            backup_success, backup_error = self._create_backup(manifest)
            if not backup_success:
                return False, f"Backup failed: {backup_error}"

            if self.on_update_progress:
                self.on_update_progress("Installing files", 0.85)

            install_success, install_error = self._install_files(manifest)
            if not install_success:
                self._restore_backup(manifest)
                return False, f"Install failed: {install_error}"

            if self.on_update_progress:
                self.on_update_progress("Finalizing update", 0.95)

            self.current_version = manifest.version
            self._cleanup_update_files()

            if self.on_update_progress:
                self.on_update_progress("Update complete", 1.0)

            if self.on_update_complete:
                self.on_update_complete(manifest.version)

            return True, ""

        except Exception as e:
            error_msg = f"Update failed: {e}"
            if self.on_update_error:
                self.on_update_error(error_msg)
            return False, error_msg
        finally:
            self.update_in_progress = False
            gc.collect()

    def _create_backup(self, manifest: UpdateManifest) -> Tuple[bool, str]:
        """Create backup of current files.

        Args:
            manifest: Update manifest

        Returns:
            tuple: (success, error_message)
        """
        try:
            self._ensure_directory(self.backup_dir)

            for file_path in manifest.files.keys():
                if self._file_exists(file_path):
                    backup_path = f"{self.backup_dir}/{file_path.lstrip('/')}"
                    self._ensure_directory_for_file(backup_path)

                    with open(file_path, 'rb') as src:
                        with open(backup_path, 'wb') as dst:
                            while True:
                                chunk = src.read(self.chunk_size)
                                if not chunk:
                                    break
                                dst.write(chunk)

            return True, ""

        except Exception as e:
            return False, str(e)

    def _install_files(self, manifest: UpdateManifest) -> Tuple[bool, str]:
        """Install files from update directory.

        Args:
            manifest: Update manifest

        Returns:
            tuple: (success, error_message)
        """
        try:
            for file_path in manifest.files.keys():
                source_path = f"{self.update_dir}/{file_path.lstrip('/')}"

                self._ensure_directory_for_file(file_path)

                with open(source_path, 'rb') as src:
                    with open(file_path, 'wb') as dst:
                        while True:
                            chunk = src.read(self.chunk_size)
                            if not chunk:
                                break
                            dst.write(chunk)

            return True, ""

        except Exception as e:
            return False, str(e)

    def _restore_backup(self, manifest: UpdateManifest) -> None:
        """Restore files from backup.

        Args:
            manifest: Update manifest
        """
        try:
            for file_path in manifest.files.keys():
                backup_path = f"{self.backup_dir}/{file_path.lstrip('/')}"

                if self._file_exists(backup_path):
                    with open(backup_path, 'rb') as src:
                        with open(file_path, 'wb') as dst:
                            while True:
                                chunk = src.read(self.chunk_size)
                                if not chunk:
                                    break
                                dst.write(chunk)
        except Exception as e:
            print(f"Backup restore failed: {e}")

    def _cleanup_update_files(self) -> None:
        """Clean up downloaded update files."""
        try:
            import os

            for root, dirs, files in os.walk(self.update_dir):
                for file in files:
                    try:
                        os.remove(os.path.join(root, file))
                    except Exception:
                        pass

        except Exception:
            pass

    def _ensure_directory(self, path: str) -> None:
        """Ensure directory exists."""
        try:
            import os
            os.makedirs(path, exist_ok=True)
        except Exception:
            pass

    def _ensure_directory_for_file(self, file_path: str) -> None:
        """Ensure directory exists for file path."""
        try:
            import os
            directory = os.path.dirname(file_path)
            if directory:
                os.makedirs(directory, exist_ok=True)
        except Exception:
            pass

    def _file_exists(self, path: str) -> bool:
        """Check if file exists."""
        try:
            with open(path, 'r'):
                return True
        except Exception:
            return False

    def reboot_device(self) -> None:
        """Reboot the device to complete update."""
        if PLATFORM == 'circuitpython':
            try:
                microcontroller.reset()
            except Exception:
                try:
                    supervisor.reload()
                except Exception:
                    print("Cannot reboot - please manually restart")
        else:
            print("Reboot not supported on this platform")