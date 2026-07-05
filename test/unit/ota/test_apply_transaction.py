# Copyright (c) 2024-2026 Michael Czeiszperger
"""Crash-safe apply transaction (markers, backup-once, verify, version-last).

Real filesystem under ``tmp_path`` (no mocks): manifest keys are absolute
tmp-paths, exactly as the client installs them verbatim on the device.
"""
import hashlib
import json
import os
import types

from scrollkit.ota.client import (OTAClient, APPLY_STARTED, BACKUP_COMPLETE,
                                  UP_TO_DATE)
from scrollkit.ota.manifest import UpdateManifest


def _make_client(tmp_path):
    updates = tmp_path / "updates"
    backup = tmp_path / "backup"
    updates.mkdir()
    return OTAClient("http://example.invalid", current_version="1.0",
                     update_dir=str(updates), backup_dir=str(backup))


def _stage(client, files, version="2.0"):
    """Stage ``{live_abs_path: bytes}`` under update_dir + write manifest.json."""
    entries = {}
    for live_path, content in files.items():
        staged = client.update_dir + "/" + live_path.lstrip("/")
        os.makedirs(os.path.dirname(staged), exist_ok=True)
        with open(staged, "wb") as f:
            f.write(content)
        entries[live_path] = {"size": len(content),
                              "checksum": hashlib.sha256(content).hexdigest()}
    manifest = {"version": version, "files": entries}
    with open(client.update_dir + "/manifest.json", "w") as f:
        json.dump(manifest, f)
    return manifest


def _live(tmp_path, rel):
    return str(tmp_path / "live" / rel)


def test_apply_success_installs_and_clears_all_state(tmp_path):
    client = _make_client(tmp_path)
    app_key = _live(tmp_path, "src/app.py")
    ver_key = _live(tmp_path, "src/.version")
    os.makedirs(os.path.dirname(app_key))
    with open(app_key, "wb") as f:
        f.write(b"OLD")
    with open(ver_key, "w") as f:
        f.write("1.0\n")
    _stage(client, {app_key: b"NEW", ver_key: b"2.0\n"})

    ok, err = client.apply_update()

    assert ok, err
    assert open(app_key, "rb").read() == b"NEW"
    assert open(ver_key).read() == "2.0\n"
    # Transaction fully torn down...
    assert not os.path.exists(client.update_dir + "/manifest.json")
    assert not os.path.exists(client.update_dir + "/" + APPLY_STARTED)
    assert not os.path.exists(client.update_dir + "/" + BACKUP_COMPLETE)
    assert os.listdir(client.update_dir) == []
    # ...and the backup holds the PRE-update bytes.
    assert open(client.backup_dir + "/" + app_key.lstrip("/"), "rb").read() == b"OLD"


def test_retry_never_overwrites_completed_backup(tmp_path):
    """Regression: after a mid-install power cut, the retry used to re-backup the
    TORN live tree over the pristine snapshot, destroying the only rollback."""
    client = _make_client(tmp_path)
    app_key = _live(tmp_path, "src/app.py")
    os.makedirs(os.path.dirname(app_key))
    with open(app_key, "wb") as f:
        f.write(b"TORN")                      # live tree corrupted by power cut
    backup_file = client.backup_dir + "/" + app_key.lstrip("/")
    os.makedirs(os.path.dirname(backup_file))
    with open(backup_file, "wb") as f:
        f.write(b"OLD")                       # pristine pre-update snapshot
    _stage(client, {app_key: b"NEW"})
    # Markers say: transaction started, backup completed.
    open(client.update_dir + "/" + APPLY_STARTED, "wb").close()
    open(client.update_dir + "/" + BACKUP_COMPLETE, "wb").close()

    ok, err = client.apply_update()

    assert ok, err
    assert open(app_key, "rb").read() == b"NEW"
    assert open(backup_file, "rb").read() == b"OLD"   # never overwritten


def test_failed_verify_rolls_back_and_clears_staging(tmp_path):
    client = _make_client(tmp_path)
    app_key = _live(tmp_path, "src/app.py")
    ver_key = _live(tmp_path, "src/.version")
    os.makedirs(os.path.dirname(app_key))
    with open(app_key, "wb") as f:
        f.write(b"OLD")
    with open(ver_key, "w") as f:
        f.write("1.0\n")
    manifest = _stage(client, {app_key: b"NEW", ver_key: b"2.0\n"})
    # Corrupt the contract: manifest promises different bytes than staged.
    manifest["files"][app_key]["checksum"] = "0" * 64
    with open(client.update_dir + "/manifest.json", "w") as f:
        json.dump(manifest, f)

    ok, err = client.apply_update()

    assert not ok and "Verify failed" in err
    assert open(app_key, "rb").read() == b"OLD"       # rolled back
    assert open(ver_key).read() == "1.0\n"            # version NOT committed
    # A bad payload must not auto-retry (and reboot-loop) on every boot.
    assert not os.path.exists(client.update_dir + "/manifest.json")
    assert not os.path.exists(client.update_dir + "/" + APPLY_STARTED)
    assert not os.path.exists(client.update_dir + "/" + BACKUP_COMPLETE)


def test_backup_redone_when_marker_present_but_backup_missing(tmp_path):
    client = _make_client(tmp_path)
    app_key = _live(tmp_path, "src/app.py")
    os.makedirs(os.path.dirname(app_key))
    with open(app_key, "wb") as f:
        f.write(b"OLD")
    _stage(client, {app_key: b"NEW"})
    open(client.update_dir + "/" + BACKUP_COMPLETE, "wb").close()  # lies: no backup

    ok, err = client.apply_update()

    assert ok, err
    assert open(client.backup_dir + "/" + app_key.lstrip("/"), "rb").read() == b"OLD"


def test_version_backup_placeholder_when_no_live_version(tmp_path):
    """A rollback must not leave the NEW version stamp on OLD code — that would
    suppress ever re-offering the update."""
    client = _make_client(tmp_path)
    ver_key = _live(tmp_path, "src/.version")
    os.makedirs(os.path.dirname(ver_key))                # live .version ABSENT
    manifest = _stage(client, {ver_key: b"2.0\n"})
    m = UpdateManifest.from_dict(manifest)

    ok, err = client._create_backup(m, version_key=ver_key)

    assert ok, err
    backed_up = open(client.backup_dir + "/" + ver_key.lstrip("/")).read()
    assert backed_up.strip() == "1.0"                    # current_version, not 2.0


def test_cleanup_and_dirs_work_without_cpython_only_os_api(tmp_path, monkeypatch):
    """CircuitPython's os has no walk/makedirs/path — the old helpers silently
    no-opped on device (staging never created, never cleaned up)."""
    client = _make_client(tmp_path)
    monkeypatch.delattr(os, "walk")
    monkeypatch.delattr(os, "makedirs")

    deep = tmp_path / "made" / "a" / "b"
    client._ensure_directory(str(deep))
    assert deep.is_dir()
    client._ensure_directory_for_file(str(tmp_path / "made2" / "c" / "f.txt"))
    assert (tmp_path / "made2" / "c").is_dir()

    nested = tmp_path / "updates" / "src" / "x"
    nested.mkdir(parents=True)
    (nested / "f.py").write_text("x")
    (tmp_path / "updates" / "manifest.json").write_text("{}")
    client._cleanup_update_files()
    assert os.listdir(client.update_dir) == []


def test_download_update_clears_stale_markers(tmp_path):
    client = _make_client(tmp_path)
    open(client.update_dir + "/" + APPLY_STARTED, "wb").close()
    open(client.update_dir + "/" + BACKUP_COMPLETE, "wb").close()

    content = b"payload"

    class _Resp:
        status_code = 200

        @property
        def content(self):
            return content

        def close(self):
            pass

    class _Session:
        def get(self, url, timeout=None):
            return _Resp()

    client.session = _Session()
    app_key = _live(tmp_path, "src/app.py")
    manifest = UpdateManifest.from_dict({
        "version": "2.0",
        "files": {app_key: {"size": len(content),
                            "checksum": hashlib.sha256(content).hexdigest()}}})

    ok, err = client.download_update(manifest)

    assert ok, err
    # Stale markers from an interrupted cleanup must not suppress the backup
    # of a NEW update.
    assert not os.path.exists(client.update_dir + "/" + APPLY_STARTED)
    assert not os.path.exists(client.update_dir + "/" + BACKUP_COMPLETE)


def test_sha256_works_with_circuitpython_hashlib_shape(tmp_path, monkeypatch):
    """Regression (found live on-device): CircuitPython's hashlib exposes ONLY
    ``new(name)`` — no ``sha256()`` constructor — and its Hash objects may lack
    ``hexdigest``. The first real OTA download died on this."""
    import hashlib as real_hashlib
    from scrollkit.ota import client as client_mod

    class _CpHash:                       # CircuitPython-shaped hash object
        def __init__(self):
            self._h = real_hashlib.sha256()

        def update(self, data):
            self._h.update(data)

        def digest(self):                # no hexdigest, digest only
            return self._h.digest()

    cp_hashlib = types.SimpleNamespace(new=lambda name: _CpHash())
    monkeypatch.setattr(client_mod, "hashlib", cp_hashlib)

    client = _make_client(tmp_path)
    app_key = _live(tmp_path, "src/app.py")
    os.makedirs(os.path.dirname(app_key))
    with open(app_key, "wb") as f:
        f.write(b"OLD")
    _stage(client, {app_key: b"NEW"})

    ok, err = client.apply_update()      # exercises _verify_install hashing

    assert ok, err
    assert open(app_key, "rb").read() == b"NEW"


def test_validator_accepts_files_without_required_key():
    m = UpdateManifest.from_dict({
        "version": "2.0",
        "files": {"/src/app.py": {"size": 3, "checksum": "a" * 64,
                                  "future_key": "ignored"}}})
    ok, err = m.validate()
    assert ok, err


def test_validator_rejects_unparseable_version():
    m = UpdateManifest.from_dict({"version": "not-a-version", "files": {}})
    ok, err = m.validate()
    assert not ok and "version" in err.lower()


def test_check_up_to_date_sentinel_is_exported():
    assert UP_TO_DATE == "No updates available"
