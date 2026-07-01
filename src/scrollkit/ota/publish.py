# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""OTA release publishing — desktop / CI only.

This is the *producer* side of OTA, the mirror image of ``scrollkit.ota.client``.
The device only ever **reads** ``manifest.json`` + ``files/`` from one fixed
channel branch over ``raw.githubusercontent.com`` (see ``OTAClient.for_github``);
this module is how that payload is *built and published* from a workstation or CI.

Two pieces:

- :func:`build_manifest` walks a source tree, computes per-file size + SHA-256,
  writes ``manifest.json`` and mirrors each file under ``files/<device-path>`` so
  the layout matches exactly what ``OTAClient`` downloads.
- :func:`publish_to_branch` replaces a channel branch's contents with that payload
  as a single fresh (parentless) commit and force-pushes it — or, with
  ``dry_run=True``, prints the git commands for a CI job to run instead.

Recommended release model (see ``docs/guide/ota.md``): a maintainer cuts a
release on an immutable ``release-MAJOR.MINOR`` branch (or a tag); automation
runs this tool to publish the generated payload to a fixed channel branch
(default ``live``) that devices read. Branch selection stays **off-device** — the
device never enumerates branches (that path is deliberately omitted; see the doc).

It is **desktop/CI only**: like ``scrollkit.dev`` it raises ``ImportError`` on
CircuitPython so device code can never depend on it. It uses ``os.walk``,
``subprocess`` and the ``git`` CLI, none of which exist on the device.
"""

from __future__ import annotations

import sys

# Hard stop on CircuitPython — this is a desktop/CI publishing tool by design.
if getattr(sys, "implementation", None) is not None \
        and getattr(sys.implementation, "name", None) == "circuitpython":
    raise ImportError(
        "scrollkit.ota.publish is a desktop/CI-only OTA publishing tool and "
        "cannot run on CircuitPython. Run it from a workstation or CI job to "
        "build and publish an update; the device only reads the published "
        "manifest.json + files/ from its channel branch."
    )

import hashlib
import json
import os
import shlex
import shutil
import subprocess
import tempfile

try:
    from typing import Any, Dict, Iterable, List, Optional  # noqa: F401
except ImportError:  # pragma: no cover - desktop always has typing
    pass


# --- Exclusion allowlist: things that must never be published --------------
#
# These keep secrets and machine-local state out of a public release payload.
# Matched against each file's path relative to ``src`` (posix separators).
EXCLUDED_FILENAMES = frozenset({"secrets.py", "settings.json"})
# A path component named any of these (a directory or a bare file) is excluded
# wherever it appears in the tree.
EXCLUDED_COMPONENTS = frozenset({"__pycache__", ".git", "credentials"})
# Exact relative paths to drop.
EXCLUDED_RELPATHS = frozenset({"logs/error_log"})
# Filename suffixes to drop.
EXCLUDED_SUFFIXES = (".pyc",)


__all__ = ['build_manifest', 'publish_to_branch', 'PublishPlan', 'main']

def _is_excluded(rel_posix, extra=()):
    """Return True if a file (path relative to ``src``, posix) must not ship."""
    extra = set(extra)
    parts = rel_posix.split("/")
    name = parts[-1]
    if rel_posix in EXCLUDED_RELPATHS:
        return True
    if name in EXCLUDED_FILENAMES or name in extra:
        return True
    if name.endswith(EXCLUDED_SUFFIXES):
        return True
    for part in parts:
        if part in EXCLUDED_COMPONENTS or part in extra:
            return True
    return False


def _join_device_path(device_root, rel_posix):
    """Map a path relative to ``src`` onto an absolute on-device path.

    ``device_root="/src"`` + ``"main.py"`` -> ``"/src/main.py"``;
    ``device_root="/"`` (or "") + ``"code.py"`` -> ``"/code.py"``.
    """
    root = "/" + (device_root or "").strip("/")
    if root == "/":
        return "/" + rel_posix
    return root + "/" + rel_posix


def build_manifest(src, out_dir, *, device_root, version, extra_excludes=()):
    """Build an OTA payload (``manifest.json`` + ``files/``) from a source tree.

    Walks ``src``, computing each file's size and SHA-256, and writes:

    - ``out_dir/manifest.json`` — the manifest ``OTAClient`` consumes, with
      absolute on-device paths as keys::

          {"version": "<semver>",
           "files": {"<device-path>": {"size": <int>,
                                       "checksum": "<sha256hex>",
                                       "required": true}, ...},
           "pre_update_scripts": [], "post_update_scripts": []}

      (``required`` is included because the device's ``UpdateManifest.validate()``
      requires it; ``OTAClient`` fetches each file at ``{base}/files/{path}``.)
    - ``out_dir/files/<device-path>`` — a byte-for-byte mirror of every listed
      file, at the path the device downloads from.

    Files matching the exclusion allowlist (``secrets.py``, ``settings.json``,
    ``logs/error_log``, ``__pycache__``, ``*.pyc``, ``.git``, ``credentials``,
    plus any names in ``extra_excludes``) are never published.

    Args:
        src: Source tree to publish (a directory).
        out_dir: Output directory for the manifest and mirrored files.
        device_root: Absolute on-device path the files install under (e.g. ``/src``).
        version: Release version (semver string).
        extra_excludes: Additional filenames/path components to exclude.

    Returns:
        The manifest as a dict (also written to ``out_dir/manifest.json``).
    """
    src = os.path.abspath(src)
    if not os.path.isdir(src):
        raise NotADirectoryError("src is not a directory: %s" % src)

    out_dir = os.path.abspath(out_dir)
    files_root = os.path.join(out_dir, "files")
    os.makedirs(files_root, exist_ok=True)

    extra = set(extra_excludes)
    files = {}  # type: Dict[str, Dict[str, Any]]

    for dirpath, dirnames, filenames in os.walk(src):
        # Prune excluded directories so we never descend into them.
        dirnames[:] = [d for d in dirnames
                       if d not in EXCLUDED_COMPONENTS and d not in extra]
        for filename in filenames:
            abs_path = os.path.join(dirpath, filename)
            if os.path.islink(abs_path):
                # Don't follow/ship symlinks — the device has a flat FS.
                continue
            rel_posix = os.path.relpath(abs_path, src).replace(os.sep, "/")
            if _is_excluded(rel_posix, extra):
                continue

            with open(abs_path, "rb") as handle:
                data = handle.read()

            device_path = _join_device_path(device_root, rel_posix)
            files[device_path] = {
                "size": len(data),
                "checksum": hashlib.sha256(data).hexdigest(),
                "required": True,
            }

            mirror = os.path.join(files_root, *device_path.lstrip("/").split("/"))
            os.makedirs(os.path.dirname(mirror), exist_ok=True)
            with open(mirror, "wb") as handle:
                handle.write(data)

    manifest = {
        "version": str(version),
        "files": {path: files[path] for path in sorted(files)},
        "pre_update_scripts": [],
        "post_update_scripts": [],
    }

    with open(os.path.join(out_dir, "manifest.json"), "w") as handle:
        json.dump(manifest, handle, indent=2, sort_keys=True)
        handle.write("\n")

    return manifest


class PublishPlan:
    """The result of (or the plan for) a :func:`publish_to_branch` call.

    Always carries the ``script`` that publishes the payload; ``executed`` says
    whether it was run (``False`` for a dry run).
    """

    def __init__(self, *, repo_path, channel_branch, remote, commit_message,
                 staging_dir, script, force, push, executed):
        self.repo_path = repo_path
        self.channel_branch = channel_branch
        self.remote = remote
        self.commit_message = commit_message
        self.staging_dir = staging_dir
        self.script = script
        self.force = force
        self.push = push
        self.executed = executed

    def __repr__(self):
        return ("PublishPlan(channel=%r, remote=%r, push=%r, force=%r, "
                "executed=%r)" % (self.channel_branch, self.remote, self.push,
                                  self.force, self.executed))


def _build_script(*, repo_path, worktree, out_dir, remote, channel_branch,
                  commit_message, push, force):
    """Render the git command sequence that publishes ``out_dir`` to a branch.

    The payload is published as a single **parentless** commit (built in a
    throwaway detached worktree, so the caller's checkout and current branch are
    never touched) and the channel ref is reset to it — this is what "replace the
    channel branch's contents" means. The same text is both printed for a dry run
    and executed for real, so the two can never drift.
    """
    q = shlex.quote
    repo, work_tree, out = q(repo_path), q(worktree), q(out_dir)
    force_flag = " --force" if force else ""

    lines = [
        "set -euo pipefail",
        "# Publish OTA payload to the '%s' channel branch." % channel_branch,
        "git -C %s worktree add --force --detach %s" % (repo, work_tree),
        # Clear the worktree's tracked files, then drop in only the payload.
        "git -C %s rm -rf --quiet --ignore-unmatch . || true" % work_tree,
        "cp -R %s/. %s/" % (out, work_tree),
        "git -C %s add -A" % work_tree,
        'TREE=$(git -C %s write-tree)' % work_tree,
        'COMMIT=$(git -C %s commit-tree "$TREE" -m %s)'
        % (work_tree, q(commit_message)),
    ]
    if push:
        lines.append('git -C %s push%s %s "$COMMIT:refs/heads/%s"'
                     % (work_tree, force_flag, q(remote), channel_branch))
    else:
        lines.append('git -C %s update-ref refs/heads/%s "$COMMIT"'
                     % (repo, channel_branch))
    lines.append("git -C %s worktree remove --force %s" % (repo, work_tree))
    return "\n".join(lines)


def publish_to_branch(out_dir, *, repo_path, channel_branch="live",
                      commit_message, remote="origin", push=True, force=True,
                      dry_run=False):
    """Publish a built payload (``out_dir``) to a channel branch via git.

    Replaces the channel branch's contents with ``out_dir``'s ``manifest.json``
    and ``files/`` as one fresh parentless commit and force-pushes it. The work
    happens in a temporary detached worktree, so the caller's working tree and
    current branch are left untouched.

    With ``dry_run=True`` nothing is executed: the git commands are printed (and
    returned on the plan) for a CI job to run, with the payload left staged in
    ``out_dir``. No GitHub API is used — this is pure git.

    Args:
        out_dir: Directory holding ``manifest.json`` + ``files/`` (from
            :func:`build_manifest`).
        repo_path: Path to the git repository to publish from.
        channel_branch: The branch devices read (default ``"live"``).
        commit_message: Commit message for the published snapshot.
        remote: Git remote to push to (default ``"origin"``).
        push: If False, update the local channel ref but don't push.
        force: If True (default), force-push (the channel is an overwritten
            snapshot, so this is expected).
        dry_run: If True, print/return the commands without running them.

    Returns:
        A :class:`PublishPlan` describing what was (or would be) run.
    """
    out_dir = os.path.abspath(out_dir)
    manifest_path = os.path.join(out_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise FileNotFoundError(
            "No manifest.json in %s — run build_manifest() first." % out_dir)

    repo_path = os.path.abspath(repo_path)
    if not os.path.exists(os.path.join(repo_path, ".git")):
        raise ValueError("%s is not a git repository (no .git)." % repo_path)

    # A path that does not yet exist (git worktree add creates it), inside a
    # temp parent we can clean up wholesale.
    tmp_parent = tempfile.mkdtemp(prefix="scrollkit-ota-")
    worktree = os.path.join(tmp_parent, "wt")

    script = _build_script(
        repo_path=repo_path, worktree=worktree, out_dir=out_dir, remote=remote,
        channel_branch=channel_branch, commit_message=commit_message,
        push=push, force=force)

    plan = PublishPlan(
        repo_path=repo_path, channel_branch=channel_branch, remote=remote,
        commit_message=commit_message, staging_dir=out_dir, script=script,
        force=force, push=push, executed=False)

    if dry_run:
        # CI path: leave the payload staged in out_dir and print the commands.
        os.rmdir(tmp_parent)  # nothing was created in it; don't leave litter
        print(script)
        return plan

    try:
        result = subprocess.run(
            ["bash", "-c", script], capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(
                "git publish failed (exit %d):\n%s\n%s"
                % (result.returncode, result.stdout, result.stderr))
        plan.executed = True
        return plan
    finally:
        shutil.rmtree(tmp_parent, ignore_errors=True)
        # The worktree should already be removed by the script; prune any
        # leftover registration so a later run starts clean.
        subprocess.run(["git", "-C", repo_path, "worktree", "prune"],
                       capture_output=True)


def main(argv=None):
    """CLI: ``python -m scrollkit.ota.publish <src> --version X.Y --root /src``."""
    import argparse

    parser = argparse.ArgumentParser(
        prog="python -m scrollkit.ota.publish",
        description="Build an OTA manifest from a source tree and publish it to "
                    "a channel branch the device reads.")
    parser.add_argument("src", help="source tree to publish")
    parser.add_argument("--version", required=True,
                        help="release version (semver)")
    parser.add_argument("--root", default="/",
                        help="absolute on-device root the files install under "
                             "(default /)")
    parser.add_argument("--channel", default="live",
                        help="channel branch the device reads (default live)")
    parser.add_argument("--repo", default=".",
                        help="git repository to publish into (default .)")
    parser.add_argument("--out", default=None,
                        help="staging/output dir (default <repo>/build/ota)")
    parser.add_argument("--remote", default="origin",
                        help="git remote to push to (default origin)")
    parser.add_argument("-m", "--message", default=None,
                        help="commit message (default auto-generated)")
    parser.add_argument("--no-push", action="store_true",
                        help="commit/update the local ref but do not push")
    parser.add_argument("--no-force", action="store_true",
                        help="do not force-push")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the git commands without running them")
    args = parser.parse_args(argv)

    out_dir = args.out or os.path.join(os.path.abspath(args.repo), "build", "ota")
    manifest = build_manifest(
        args.src, out_dir, device_root=args.root, version=args.version)
    print("Built manifest: %d files, version %s -> %s"
          % (len(manifest["files"]), manifest["version"],
             os.path.join(out_dir, "manifest.json")))

    message = args.message or ("Publish OTA %s to %s"
                               % (args.version, args.channel))
    plan = publish_to_branch(
        out_dir, repo_path=args.repo, channel_branch=args.channel,
        commit_message=message, remote=args.remote,
        push=not args.no_push, force=not args.no_force, dry_run=args.dry_run)

    if args.dry_run:
        print("# (dry run — nothing was pushed; payload staged in %s)" % out_dir)
    else:
        suffix = "" if plan.push else " (local ref only)"
        print("Published %s to branch '%s'%s."
              % (args.version, args.channel, suffix))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
