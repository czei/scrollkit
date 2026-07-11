# Copyright (c) 2024-2026 Michael Czeiszperger
"""OTA update client for CircuitPython devices.

Handles downloading and applying updates safely.

Acknowledgement: the idea for on-device OTA updates was inspired by Ronald
Dehuysser's micropython-ota-updater
(https://github.com/rdehuyss/micropython-ota-updater). This is a clean,
manifest-based reimplementation and contains none of that project's code.
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


__all__ = ['OTAClient', 'UP_TO_DATE', 'APPLY_STARTED', 'BACKUP_COMPLETE',
           'CREATED_PATHS']

# The ONE genuine "device is current" outcome from check_for_updates(). Callers
# (e.g. display_progress.schedule_update) compare against this to distinguish
# "up to date" from a failed check — every failure keeps its specific reason,
# so a fetch/parse/validate error can never masquerade as "no update".
UP_TO_DATE = "No updates available"

# Zero-byte transaction markers, created inside ``update_dir`` during apply.
# The app's frozen boot.py mirrors these names (a cross-repo contract) to
# recover from a power cut mid-apply, before the possibly-torn app code runs:
#   APPLY_STARTED   — an apply began; the live tree may be torn.
#   BACKUP_COMPLETE — backup_dir holds a complete pre-update snapshot.
APPLY_STARTED = "apply_started"
BACKUP_COMPLETE = "backup_complete"
# Newline-separated device paths of files this update CREATES (no prior live
# copy). They have no backup, so rollback must DELETE them — otherwise a
# power-cut "rollback" leaves future files orphaned on a reverted tree. boot.py
# reads this too, for boot-time rollback.
CREATED_PATHS = "created_paths"


def _key_allowed(key):
    """Whether a manifest key may install to the device.

    Install is path-agnostic (writes the key verbatim), so a malformed or hostile
    manifest could otherwise overwrite unrelated flash (``/secrets.py``) or escape
    via ``..``. Restrict to the roots a release legitimately ships to.
    """
    if not key or ".." in key.split("/"):
        return False
    if key in ("/code.py", "/boot.py"):
        return True
    return key.startswith("/src/") or key.startswith("/lib/scrollkit/")


def _sha256():
    """A fresh sha256 object on BOTH platforms.

    CircuitPython's built-in ``hashlib`` exposes only ``new(name)`` — there is
    no ``hashlib.sha256()`` constructor, so that call raised
    "'module' object has no attribute 'sha256'" on the device (found live: it
    failed the very first OTA file download to reach checksumming).
    """
    try:
        return hashlib.sha256()
    except AttributeError:
        return hashlib.new("sha256")


def _hexdigest(hash_obj):
    """Hex digest on BOTH platforms (CircuitPython Hash may lack hexdigest)."""
    try:
        return hash_obj.hexdigest()
    except AttributeError:
        import binascii
        return binascii.hexlify(hash_obj.digest()).decode()

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

        # FAST PATH: the channel publishes a ~6-byte version.txt next to the
        # manifest. Comparing versions needs those bytes, not the ~31 KB / 176-
        # entry manifest (which the old check fetched, flash-streamed and JSON-
        # parsed every time — slow, and pure waste when the answer is "up to
        # date", i.e. almost always). Only a NEWER version proceeds to the full
        # manifest fetch below (needed then anyway for staging). Any miss —
        # 404 on an older channel, junk content, transport error — falls
        # through to the manifest path unchanged.
        try:
            v_resp = self._http_get(f"{self.server_url}/version.txt")
            try:
                if v_resp.status_code == 200:
                    remote_version = str(v_resp.text).strip()
                    # Trust ONLY a strict MAJOR.MINOR[.PATCH] shape: parse_version
                    # maps junk to (0,0,0), so an unvalidated error page would
                    # compare as "older" and fake an up-to-date answer.
                    parts = remote_version.split(".")
                    if 2 <= len(parts) <= 3 and all(p.isdigit() for p in parts):
                        probe = UpdateManifest(version=remote_version)
                        if probe.compare_version(self.current_version) <= 0:
                            return False, UP_TO_DATE
            finally:
                try:
                    v_resp.close()
                except Exception:
                    pass
        except Exception:
            pass  # fall through to the manifest fetch
        gc.collect()

        try:
            url = f"{self.server_url}/manifest.json"
            response = self._http_get(url)

            if response.status_code != 200:
                return False, f"Server error: {response.status_code}"

            try:
                # Avoid response.json() when the body can be streamed: .json()
                # needs the whole body as ONE contiguous allocation, and a
                # ~30 KB manifest routinely exceeds the largest free block on a
                # hot CircuitPython heap (the intermittent "Check for Update ...
                # MemoryError"). Stream the body to flash in small chunks, then
                # json.load the FILE — the parser reads it incrementally, so the
                # RAM cost is many small allocations instead of one big one.
                if getattr(response, "iter_content", None) is None:
                    manifest_data = response.json()   # desktop mocks/shims
                else:
                    part_path = f"{self.update_dir}/manifest.part"
                    self._stream_body_to_file(response, part_path)
                    gc.collect()
                    try:
                        with open(part_path) as f:
                            manifest_data = json.load(f)
                    finally:
                        self._remove(part_path)
                manifest = UpdateManifest.from_dict(manifest_data)
            except ValueError as e:  # CircuitPython: json raises ValueError
                return False, f"Invalid manifest: {e}"

            is_valid, error = manifest.validate()
            if not is_valid:
                return False, f"Invalid manifest: {error}"

            if manifest.compare_version(self.current_version) > 0:
                self.available_update = manifest
                if self.on_update_available:
                    self.on_update_available(manifest)
                return True, manifest

            return False, UP_TO_DATE

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

        # Path-safety: reject a manifest that would install outside the release
        # roots or escape via ``..`` before touching the filesystem. Device-only
        # — desktop tests/simulator legitimately stage into temp dirs; the
        # publisher preflight enforces the same allowlist off-device.
        if PLATFORM == 'circuitpython':
            bad = [k for k in manifest.files if not _key_allowed(k)]
            if bad:
                return False, "Unsafe manifest path(s): %s" % ", ".join(sorted(bad)[:3])

        try:
            self.update_in_progress = True

            self._ensure_directory(self.update_dir)

            # A fresh download is a fresh transaction: stale markers left by an
            # interrupted cleanup must not suppress the backup of a NEW update,
            # and stale staged files from a FAILED download must not eat the
            # free space the check below demands (seen live: a failed run left
            # ~530 KB staged and every retry then failed "Insufficient storage").
            self._remove(self._marker(APPLY_STARTED))
            self._remove(self._marker(BACKUP_COMPLETE))
            self._remove(self._marker(CREATED_PATHS))
            self._rmtree_contents(self.update_dir)

            # DELTA: only files whose live copy is missing or has a different
            # sha256 need downloading. A release changes a handful of files, so
            # staging + backup stay small regardless of total manifest size —
            # which is what lets a combined app + /lib/scrollkit manifest fit the
            # device's thin free space (a full-manifest download would not).
            overwritten, created, _unchanged = self._delta(manifest)
            changed = overwritten + created

            if PLATFORM == 'circuitpython':
                try:
                    import os
                    stat = os.statvfs('/')
                    free_space = stat[1] * stat[3]
                    # Size to the delta: staged copy + backup of the overwritten
                    # subset ≈ 2× delta, plus a fixed headroom cushion for FS
                    # slack + markers (NOT 2× the whole manifest).
                    delta_bytes = sum(manifest.files[k]['size'] for k in changed)
                    required_space = delta_bytes * 2 + 51200
                    if free_space < required_space:
                        return False, f"Insufficient storage: {free_space} < {required_space}"
                except Exception:
                    pass

            total = len(changed)
            for i, file_path in enumerate(changed):
                if self.on_update_progress:
                    progress = (i / total) * 0.8 if total else 0.8
                    self.on_update_progress(f"Downloading {file_path}", progress)

                try:
                    self._download_file(file_path, manifest.files[file_path])
                except (NetworkError, OTAError) as e:
                    return False, f"Failed to download {file_path}: {e}"

                gc.collect()

            manifest_path = f"{self.update_dir}/manifest.json"
            try:
                with open(manifest_path, 'w') as f:
                    f.write(manifest.to_json())
            except OSError as e:
                # OSError only: CircuitPython has no IOError name (it's an
                # OSError alias in CPython 3 anyway) — naming it here raised
                # NameError on-device, masking the real write failure.
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

            # Stream to flash while hashing per chunk — response.content would
            # need the whole file as one contiguous allocation (same hot-heap
            # MemoryError class as the manifest fetch above). Verify AFTER the
            # write and delete the staged file on any mismatch, so a bad body
            # never survives in the staging area.
            digest = _sha256()
            local_path = f"{self.update_dir}/{file_path.lstrip('/')}"
            total = self._stream_body_to_file(response, local_path, digest)

            if total != file_info['size']:
                self._remove(local_path)
                raise OTAError("Size mismatch for %s: %d != %d"
                               % (file_path, total, file_info['size']))

            if _hexdigest(digest) != file_info['checksum']:
                self._remove(local_path)
                raise OTAError("Checksum mismatch for %s" % file_path)
        finally:
            if response is not None:
                try:
                    response.close()
                except Exception:
                    pass

    def apply_update(self, manifest: Optional[UpdateManifest] = None) -> Tuple[bool, str]:
        """Apply downloaded update as a crash-safe transaction.

        Protocol (markers live in ``update_dir``; the app's frozen ``boot.py``
        uses them to recover if power is lost mid-apply, BEFORE the possibly-torn
        app code would run):

          1. touch ``APPLY_STARTED``            — the live tree may be torn after this
          2. backup once → touch ``BACKUP_COMPLETE``. A completed backup is never
             overwritten by a retry, so a torn live tree can't poison the last
             known-good snapshot.
          3. install every file EXCEPT the version file, in sorted order
          4. re-verify each installed file's size + sha256 against the manifest
          5. write the version file LAST         — the commit marker
          6. tear down in order: APPLY_STARTED, BACKUP_COMPLETE, manifest.json,
             then the rest of the staging dir — every intermediate crash point
             lands in a recoverable state.

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

        if PLATFORM == 'circuitpython':
            bad = [k for k in manifest.files if not _key_allowed(k)]
            if bad:
                return False, "Unsafe manifest path(s): %s" % ", ".join(sorted(bad)[:3])

        version_key = None
        for key in sorted(manifest.files.keys()):
            if key.endswith('/.version'):
                version_key = key
                break

        try:
            if self.on_update_progress:
                self.on_update_progress("Preparing update", 0.8)

            try:
                self._touch(self._marker(APPLY_STARTED))
                self._sync()
            except Exception as e:
                # Read-only filesystem (boot button state) or missing staging dir:
                # abort before touching ANY live file.
                return False, f"Cannot start update transaction: {e}"

            # Backup once per transaction: on a retry after a mid-install power
            # cut, the pristine backup must NOT be overwritten with the torn tree.
            have_backup = (self._exists(self._marker(BACKUP_COMPLETE))
                           and self._dir_non_empty(self.backup_dir))
            if not have_backup:
                self._remove(self._marker(BACKUP_COMPLETE))
                # Clear stale snapshot files from an older release so a later
                # rollback can't resurrect files this release removed.
                self._rmtree_contents(self.backup_dir)
                backup_success, backup_error = self._create_backup(
                    manifest, version_key=version_key)
                if not backup_success:
                    self._remove(self._marker(APPLY_STARTED))
                    return False, f"Backup failed: {backup_error}"
                self._touch(self._marker(BACKUP_COMPLETE))
                self._sync()

            if self.on_update_progress:
                self.on_update_progress("Installing files", 0.85)

            install_success, install_error = self._install_files(
                manifest, skip=version_key)
            if not install_success:
                self._fail_and_rollback(manifest)
                return False, f"Install failed: {install_error}"

            verify_success, verify_error = self._verify_install(
                manifest, skip=version_key)
            if not verify_success:
                self._fail_and_rollback(manifest)
                return False, f"Verify failed: {verify_error}"

            if self.on_update_progress:
                self.on_update_progress("Finalizing update", 0.95)

            # Commit: the version file is written only after everything else is
            # installed AND verified, so an interrupted apply can never leave a
            # new version stamp on a mixed tree.
            if version_key is not None:
                install_success, install_error = self._install_files(
                    manifest, only=version_key)
                if not install_success:
                    self._fail_and_rollback(manifest)
                    return False, f"Version write failed: {install_error}"
                self._sync()

            self.current_version = manifest.version

            # Ordered teardown — see the protocol note in the docstring.
            self._remove(self._marker(APPLY_STARTED))
            self._remove(self._marker(BACKUP_COMPLETE))
            self._remove(self._marker(CREATED_PATHS))
            self._remove(f"{self.update_dir}/manifest.json")
            self._sync()
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

    def _fail_and_rollback(self, manifest: UpdateManifest) -> None:
        """Restore the backup and clear the whole transaction.

        Clearing the staged manifest is deliberate: a payload that failed to
        install or verify must not auto-retry (and reboot-loop) on every boot —
        the user re-triggers the update explicitly.
        """
        self._restore_backup(manifest)
        self._delete_created()          # new files have no backup — erase them
        self._remove(f"{self.update_dir}/manifest.json")
        self._remove(self._marker(BACKUP_COMPLETE))
        self._remove(self._marker(APPLY_STARTED))
        self._remove(self._marker(CREATED_PATHS))
        self._sync()
        self._cleanup_update_files()

    def _create_backup(self, manifest: UpdateManifest,
                       version_key: Optional[str] = None) -> Tuple[bool, str]:
        """Create backup of current files.

        Args:
            manifest: Update manifest
            version_key: The manifest key of the version file, if any

        Returns:
            tuple: (success, error_message)
        """
        try:
            self._ensure_directory(self.backup_dir)

            created = []
            for file_path in sorted(manifest.files.keys()):
                # Only back up files this update actually installs (i.e. were
                # staged/changed). Unchanged files stay put — no backup needed.
                if not self._is_staged(file_path):
                    continue
                backup_path = f"{self.backup_dir}/{file_path.lstrip('/')}"
                if self._file_exists(file_path):
                    self._ensure_directory_for_file(backup_path)

                    with open(file_path, 'rb') as src:
                        with open(backup_path, 'wb') as dst:
                            while True:
                                chunk = src.read(self.chunk_size)
                                if not chunk:
                                    break
                                dst.write(chunk)
                elif file_path == version_key:
                    # No live version file (fresh dev deploy leaves .version
                    # untracked): back up the in-memory current version, so a
                    # rollback can't leave the NEW stamp on OLD code — which
                    # would suppress ever re-offering this update.
                    self._ensure_directory_for_file(backup_path)
                    with open(backup_path, 'w') as dst:
                        dst.write(self.current_version + "\n")
                else:
                    # A brand-new file with no backup: record it so rollback
                    # deletes it (leaving it would orphan future code on a
                    # reverted tree). The version file is handled above, never here.
                    created.append(file_path)

            # Write the created-paths record BEFORE install so boot.py can act on
            # it even if power is lost mid-install.
            if created:
                with open(self._marker(CREATED_PATHS), 'w') as f:
                    f.write("\n".join(created) + "\n")

            return True, ""

        except Exception as e:
            return False, str(e)

    def _install_files(self, manifest: UpdateManifest, skip: Optional[str] = None,
                       only: Optional[str] = None) -> Tuple[bool, str]:
        """Install files from update directory, in sorted (deterministic) order.

        Args:
            manifest: Update manifest
            skip: Manifest key to leave out (the version file, written last
                by ``apply_update`` as the commit marker)
            only: Install just this one key (the commit write)

        Returns:
            tuple: (success, error_message)
        """
        try:
            # Only install what was staged (the delta). Unchanged files were not
            # downloaded, so their staging source doesn't exist — skip them.
            if only is not None:
                keys = [only] if self._is_staged(only) else []
            else:
                keys = [k for k in sorted(manifest.files.keys())
                        if k != skip and self._is_staged(k)]

            for file_path in keys:
                source_path = f"{self.update_dir}/{file_path.lstrip('/')}"

                self._ensure_directory_for_file(file_path)
                self._remove_mpy_sibling(file_path)

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

    def _verify_install(self, manifest: UpdateManifest,
                        skip: Optional[str] = None) -> Tuple[bool, str]:
        """Re-verify installed live files against the manifest before commit.

        Download-time checks proved the STAGED bytes; this proves the INSTALLED
        bytes (a torn/failed copy would otherwise be committed). Chunked reads
        bound RAM to ``chunk_size``.
        """
        try:
            for file_path in sorted(manifest.files.keys()):
                if file_path == skip:
                    continue
                info = manifest.files[file_path]
                digest = _sha256()
                size = 0
                try:
                    with open(file_path, 'rb') as f:
                        while True:
                            chunk = f.read(self.chunk_size)
                            if not chunk:
                                break
                            size += len(chunk)
                            digest.update(chunk)
                except OSError as e:
                    return False, f"Missing after install: {file_path} ({e})"
                if size != info['size']:
                    return False, (f"Size mismatch after install: {file_path}: "
                                   f"{size} != {info['size']}")
                if _hexdigest(digest) != info['checksum']:
                    return False, f"Checksum mismatch after install: {file_path}"
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

    # ---- delta apply -------------------------------------------------------
    # Only files whose live copy differs from the manifest are downloaded /
    # backed up / installed. Files this update CREATES (no prior live copy) have
    # no backup, so a rollback must DELETE them, not skip them — tracked via the
    # CREATED_PATHS record.

    def _live_checksum(self, path):
        """Streaming sha256 of a live file, or None if it doesn't exist.

        Reads in ``chunk_size`` blocks and collects afterwards, so hashing the
        whole tree at check time stays O(1) heap and yields to the VM's
        USB/WiFi background task between files on CircuitPython.
        """
        try:
            digest = _sha256()
            with open(path, 'rb') as f:
                while True:
                    chunk = f.read(self.chunk_size)
                    if not chunk:
                        break
                    digest.update(chunk)
            return _hexdigest(digest)
        except OSError:
            return None
        finally:
            gc.collect()

    def _delta(self, manifest):
        """Partition manifest keys vs the live tree.

        Returns ``(overwritten, created, unchanged)`` — sorted lists of keys
        whose live file (respectively) differs, is absent, or already matches.
        """
        overwritten, created, unchanged = [], [], []
        for key in sorted(manifest.files.keys()):
            want = manifest.files[key].get('checksum')
            have = self._live_checksum(key)
            if have is None:
                created.append(key)
            elif have == want:
                unchanged.append(key)
            else:
                overwritten.append(key)
        return overwritten, created, unchanged

    def _is_staged(self, file_path):
        """True if this file was downloaded into the staging dir (i.e. changed)."""
        return self._exists(f"{self.update_dir}/{file_path.lstrip('/')}")

    def _stream_body_to_file(self, response, path, digest=None):
        """Write a response body to ``path`` in small chunks; return the byte count.

        The point is to never hold the whole body in RAM: on a hot CircuitPython
        heap the largest free block is often smaller than a 30 KB manifest or
        source file, so ``response.content`` / ``response.json()`` fail with
        MemoryError while chunked writes sail through. Feeds ``digest`` per
        chunk when given. Falls back to ``response.content`` when the response
        has no ``iter_content`` (desktop mocks / simple session shims).
        """
        self._ensure_directory_for_file(path)
        total = 0
        iter_content = getattr(response, "iter_content", None)
        with open(path, "wb") as f:
            if iter_content is None:
                content = response.content
                f.write(content)
                total = len(content)
                if digest is not None:
                    digest.update(content)
            else:
                for chunk in iter_content(chunk_size=1024):
                    f.write(chunk)
                    total += len(chunk)
                    if digest is not None:
                        digest.update(chunk)
        return total

    def _remove_mpy_sibling(self, file_path):
        """Delete a same-basename ``.mpy`` before writing a ``.py`` under /lib.

        CircuitPython prefers ``.mpy`` over ``.py``; a stale ``.mpy`` left by a
        manual copy would silently shadow the freshly installed source. Cheap
        insurance (scrollkit ships as ``.py`` today, so normally a no-op).
        """
        if file_path.endswith('.py'):
            self._remove(file_path[:-3] + '.mpy')

    def _read_created(self):
        try:
            with open(self._marker(CREATED_PATHS)) as f:
                return [ln.strip() for ln in f if ln.strip()]
        except OSError:
            return []

    def _delete_created(self):
        """Remove files this transaction created (they have no backup)."""
        for path in self._read_created():
            self._remove(path)

    # ---- device-safe filesystem helpers -------------------------------------
    # CircuitPython's ``os`` has no ``path``, ``makedirs`` or ``walk`` — the old
    # versions of these helpers silently no-opped on device (staging directories
    # were never created; staged files were never cleaned up after an apply, so
    # the surviving manifest would re-trigger the install on every boot). Only
    # listdir/mkdir/stat/remove/rmdir/sync are used, which exist on both platforms.

    def _cleanup_update_files(self) -> None:
        """Clean up downloaded update files (device-safe; no ``os.walk``)."""
        try:
            self._rmtree_contents(self.update_dir)
        except Exception as e:
            print("OTA cleanup failed:", e)

    def _ensure_directory(self, path: str) -> None:
        """Ensure directory exists."""
        try:
            self._makedirs(path)
        except Exception:
            pass

    def _ensure_directory_for_file(self, file_path: str) -> None:
        """Ensure directory exists for file path."""
        try:
            directory = file_path.rsplit('/', 1)[0] if '/' in file_path else ''
            if directory:
                self._makedirs(directory)
        except Exception:
            pass

    def _makedirs(self, path: str) -> None:
        """``mkdir -p`` using only ``os.mkdir`` (CircuitPython has no makedirs)."""
        import os
        current = '' if path.startswith('/') else '.'
        for part in path.split('/'):
            if not part:
                continue
            current = current + '/' + part
            try:
                os.mkdir(current)
            except OSError:
                pass  # already exists (a real failure surfaces at the next write)

    def _rmtree_contents(self, path: str) -> None:
        """Delete a directory's contents, keeping the directory itself."""
        import os
        try:
            names = os.listdir(path)
        except OSError:
            return
        for name in names:
            child = path + '/' + name
            if self._is_dir(child):
                self._rmtree_contents(child)
                try:
                    os.rmdir(child)
                except OSError:
                    pass
            else:
                self._remove(child)

    def _exists(self, path: str) -> bool:
        """Whether a file OR directory exists (``os.stat``, not ``open``)."""
        try:
            import os
            os.stat(path)
            return True
        except OSError:
            return False

    def _is_dir(self, path: str) -> bool:
        try:
            import os
            return bool(os.stat(path)[0] & 0x4000)
        except OSError:
            return False

    def _dir_non_empty(self, path: str) -> bool:
        try:
            import os
            return len(os.listdir(path)) > 0
        except OSError:
            return False

    def _marker(self, name: str) -> str:
        return f"{self.update_dir}/{name}"

    def _touch(self, path: str) -> None:
        with open(path, 'wb'):
            pass

    def _remove(self, path: str) -> None:
        try:
            import os
            os.remove(path)
        except OSError:
            pass

    def _sync(self) -> None:
        """Flush filesystem buffers where supported (CircuitPython has os.sync)."""
        try:
            import os
            os.sync()
        except (AttributeError, OSError):
            pass

    def _file_exists(self, path: str) -> bool:
        """Check if file exists."""
        return self._exists(path)

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