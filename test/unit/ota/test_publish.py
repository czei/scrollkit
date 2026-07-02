"""Tests for the desktop/CI OTA publishing tool (``scrollkit.ota.publish``).

Covers the producer side: building a manifest (correct sizes/checksums, the
exclusion allowlist), that the produced payload round-trips cleanly through the
device's ``OTAClient`` consumption path, a dry-run publish that touches no git
state, a real git publish to a throwaway remote, and the CircuitPython import
guard.
"""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import types

import pytest

from scrollkit.ota.publish import build_manifest, publish_to_branch


# --- helpers ---------------------------------------------------------------

def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    mode = "wb" if isinstance(data, bytes) else "w"
    with open(path, mode) as handle:
        handle.write(data)


def _make_src(root):
    """A source tree mixing publishable files with every excluded kind."""
    _write(os.path.join(root, "code.py"), b"print('hi')\n")
    _write(os.path.join(root, "lib", "util.py"), b"X = 1\n")
    _write(os.path.join(root, "data", "waits.json"), b'{"ok": true}\n')
    # --- everything below must be excluded ---
    _write(os.path.join(root, "secrets.py"), b"WIFI = 'p'\n")
    _write(os.path.join(root, "settings.json"), b"{}\n")
    _write(os.path.join(root, "logs", "error_log"), b"boom\n")
    _write(os.path.join(root, "__pycache__", "code.cpython-39.pyc"), b"\x00")
    _write(os.path.join(root, "lib", "util.pyc"), b"\x00")
    _write(os.path.join(root, ".git", "config"), b"[core]\n")
    _write(os.path.join(root, "credentials", "token"), b"sekrit\n")


def _git(repo, *args, env=None):
    return subprocess.run(["git", "-C", repo, *args],
                          capture_output=True, text=True, check=True, env=env)


# --- build_manifest --------------------------------------------------------

def test_build_manifest_sizes_and_checksums(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _write(str(src / "code.py"), b"print('hi')\n")
    _write(str(src / "lib" / "util.py"), b"X = 1\n")
    out = tmp_path / "out"

    manifest = build_manifest(str(src), str(out), device_root="/src",
                              version="1.2.0")

    assert manifest["version"] == "1.2.0"
    # The exec()-based script hooks were removed (unsigned remote code
    # execution surface); the publisher must not emit the keys at all.
    assert "pre_update_scripts" not in manifest
    assert "post_update_scripts" not in manifest
    # Keys are absolute on-device paths under device_root.
    assert set(manifest["files"]) == {"/src/code.py", "/src/lib/util.py"}

    code = manifest["files"]["/src/code.py"]
    assert code["size"] == len(b"print('hi')\n")
    assert code["checksum"] == hashlib.sha256(b"print('hi')\n").hexdigest()

    # Each file is mirrored byte-for-byte at files/<device-path> (the layout
    # OTAClient downloads from: {base}/files/{path}).
    mirror = out / "files" / "src" / "code.py"
    assert mirror.read_bytes() == b"print('hi')\n"
    assert (out / "manifest.json").is_file()


def test_build_manifest_default_root_is_absolute(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _write(str(src / "code.py"), b"x\n")
    manifest = build_manifest(str(src), str(tmp_path / "out"),
                              device_root="/", version="0.1.0")
    assert set(manifest["files"]) == {"/code.py"}


def test_build_manifest_enforces_exclusions(tmp_path):
    src = tmp_path / "src"
    _make_src(str(src))
    out = tmp_path / "out"

    manifest = build_manifest(str(src), str(out), device_root="/", version="2.0.0")

    assert set(manifest["files"]) == {
        "/code.py", "/lib/util.py", "/data/waits.json"}

    # None of the excluded items leak into the mirror tree either.
    published = set()
    for dirpath, _dirs, files in os.walk(out / "files"):
        for name in files:
            published.add(os.path.relpath(os.path.join(dirpath, name),
                                          str(out / "files")).replace(os.sep, "/"))
    assert published == {"code.py", "lib/util.py", "data/waits.json"}
    for bad in ("secrets.py", "settings.json", "error_log", "token",
                "util.pyc", "config"):
        assert all(bad not in p for p in published), bad


def test_build_manifest_extra_excludes(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    _write(str(src / "code.py"), b"x\n")
    _write(str(src / "notes.md"), b"# notes\n")
    manifest = build_manifest(str(src), str(tmp_path / "out"), device_root="/",
                              version="0.1.0", extra_excludes=("notes.md",))
    assert set(manifest["files"]) == {"/code.py"}


# --- round-trip through OTAClient's consumption ----------------------------

class _Resp:
    def __init__(self, status, content=b"", json_obj=None):
        self.status_code = status
        self._content = content
        self._json = json_obj

    @property
    def content(self):
        return self._content

    def json(self):
        return self._json

    def close(self):
        pass


class _FakeRequests:
    """Serves a built payload the way raw.githubusercontent.com would."""

    def __init__(self, base, out_dir):
        self.base = base.rstrip("/")
        self.out_dir = out_dir

    def get(self, url, timeout=None):
        rel = url[len(self.base):].lstrip("/")
        path = os.path.join(self.out_dir, *rel.split("/"))
        if not os.path.isfile(path):
            return _Resp(404)
        with open(path, "rb") as handle:
            data = handle.read()
        if rel == "manifest.json":
            return _Resp(200, content=data, json_obj=json.loads(data))
        return _Resp(200, content=data)


def test_manifest_roundtrips_through_ota_client(tmp_path, monkeypatch):
    from scrollkit.ota import client as client_mod
    from scrollkit.ota.client import OTAClient
    from scrollkit.ota.manifest import UpdateManifest

    src = tmp_path / "src"
    _make_src(str(src))
    out = tmp_path / "out"
    build_manifest(str(src), str(out), device_root="/src", version="1.2.0")

    # The device parses + validates the manifest before trusting it.
    data = json.loads((out / "manifest.json").read_text())
    parsed = UpdateManifest.from_dict(data)
    assert parsed.validate() == (True, "")
    assert parsed.compare_version("0.0.0") > 0

    base = "https://raw.githubusercontent.com/owner/repo/live"
    monkeypatch.setattr(client_mod, "requests", _FakeRequests(base, str(out)))

    client = OTAClient(update_server_url=base, current_version="0.0.0",
                       update_dir=str(tmp_path / "updates"),
                       backup_dir=str(tmp_path / "backup"))

    has_update, manifest = client.check_for_updates()
    assert has_update is True
    assert isinstance(manifest, UpdateManifest)

    # download_update re-verifies every file's size + SHA-256 against the
    # manifest — the real proof the generator's metadata is correct.
    ok, err = client.download_update(manifest)
    assert ok is True, err


# --- publish_to_branch: dry run -------------------------------------------

def _init_repo(path):
    _git(str(path), "init", "-q")
    _git(str(path), "config", "user.email", "test@example.com")
    _git(str(path), "config", "user.name", "Test")


@pytest.mark.skipif(not shutil.which("git"), reason="git not available")
def test_publish_dry_run_touches_no_git_state(tmp_path, capsys):
    repo = tmp_path / "repo"
    repo.mkdir()
    _init_repo(repo)

    src = tmp_path / "src"
    src.mkdir()
    _write(str(src / "code.py"), b"x\n")
    out = tmp_path / "out"
    build_manifest(str(src), str(out), device_root="/", version="3.1.0")

    plan = publish_to_branch(str(out), repo_path=str(repo),
                             channel_branch="live",
                             commit_message="Publish OTA 3.1.0", dry_run=True)

    assert plan.executed is False
    assert plan.channel_branch == "live"
    printed = capsys.readouterr().out
    for needle in ("worktree add", "commit-tree", "push", "refs/heads/live"):
        assert needle in plan.script
        assert needle in printed
    assert str(out) in plan.script

    # Nothing was committed, pushed, or branched.
    branches = _git(str(repo), "branch", "--list").stdout.strip()
    assert branches == ""
    assert _git(str(repo), "worktree", "list").stdout.count("\n") <= 1
    # Payload remains staged for a CI job to pick up.
    assert (out / "manifest.json").is_file()


@pytest.mark.skipif(not (shutil.which("git") and shutil.which("bash")),
                    reason="git and bash required")
def test_publish_pushes_payload_to_channel_branch(tmp_path):
    remote = tmp_path / "remote.git"
    _git(str(tmp_path), "init", "--bare", "-q", str(remote))

    work = tmp_path / "work"
    work.mkdir()
    _init_repo(work)
    _write(str(work / "README.md"), b"# work\n")
    _git(str(work), "add", "README.md")
    _git(str(work), "commit", "-q", "-m", "init")
    head_before = _git(str(work), "rev-parse", "HEAD").stdout.strip()
    _git(str(work), "remote", "add", "origin", str(remote))

    src = tmp_path / "src"
    _make_src(str(src))
    out = tmp_path / "out"
    build_manifest(str(src), str(out), device_root="/src", version="4.2.0")

    plan = publish_to_branch(str(out), repo_path=str(work),
                             channel_branch="live",
                             commit_message="Publish OTA 4.2.0")
    assert plan.executed is True

    # The bare remote now has a 'live' branch carrying exactly the payload.
    listed = _git(str(remote), "ls-tree", "-r", "--name-only", "live").stdout
    assert "manifest.json" in listed
    assert "files/src/code.py" in listed
    assert "secrets.py" not in listed

    shown = _git(str(remote), "show", "live:manifest.json").stdout
    assert json.loads(shown)["version"] == "4.2.0"

    # The published commit is a fresh snapshot with no parent, and the work
    # repo's own checkout/branch is untouched.
    assert _git(str(remote), "rev-list", "--count", "live").stdout.strip() == "1"
    assert _git(str(work), "rev-parse", "HEAD").stdout.strip() == head_before
    assert _git(str(work), "status", "--porcelain").stdout.strip() == ""


# --- import guard ----------------------------------------------------------

def test_publish_import_raises_on_circuitpython(monkeypatch):
    for name in list(sys.modules):
        if name == "scrollkit.ota.publish":
            monkeypatch.delitem(sys.modules, name, raising=False)

    real = sys.implementation
    fake = types.SimpleNamespace(
        **{k: getattr(real, k) for k in dir(real) if not k.startswith("__")})
    fake.name = "circuitpython"
    monkeypatch.setattr(sys, "implementation", fake)

    with pytest.raises(ImportError):
        import scrollkit.ota.publish  # noqa: F401
