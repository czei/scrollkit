# OTA Updates

`scrollkit.ota` delivers over-the-air firmware updates from GitHub using a
manifest, with checksums and a recovery guarantee.

## How it works

<!-- Source: ota/client.py (check_for_updates/download_update/apply_update), ota/display_progress.py -->
```mermaid
sequenceDiagram
    participant OTA as OTAClient
    participant GH as GitHub (raw.githubusercontent.com)
    participant FS as Device filesystem

    OTA->>GH: check_for_updates() — GET manifest.json
    GH-->>OTA: manifest (version + files + checksums)
    Note over OTA: UpdateManifest.validate()<br/>+ compare_version
    OTA->>FS: download_update() — statvfs free-space check
    loop each changed file
        OTA->>GH: GET file
        GH-->>OTA: bytes
        Note over OTA: verify SHA-256, stage under /updates
    end
    OTA->>FS: apply_update() — backup → install<br/>(restore backup on failure)
    OTA->>OTA: reboot_device()
```

`OTAProgressDisplay` (in `ota.display_progress`) wraps this with on-panel status
and two lifecycle hooks: `install_pending()` runs **on boot, before the display
loop starts** (applies a staged update, then reboots), and `schedule_update()`
runs **from a web route** (checks + downloads to the staging dir; the caller
must then reboot — the applied update runs after `install_pending()` picks it
up on the next boot). Both keep the blocking work off the running display loop.

```python
from scrollkit.ota.client import OTAClient

ota = OTAClient.for_github(
    owner="OWNER", repo="REPO", branch="live",
    current_version="1.0.0",
)
has_update, manifest = ota.check_for_updates()
if has_update:
    ota.download_update(manifest)
    ota.apply_update()   # does not reboot on its own — see below
    ota.reboot_device()  # reboot to run the newly-installed code
```

## Fixed branch, version in the manifest

`OTAClient.for_github(owner, repo, branch, current_version)` builds **one fixed
base URL** — `https://raw.githubusercontent.com/{owner}/{repo}/{branch}` — and
only ever reads from it:

- It fetches `manifest.json` **from that single branch**. It does **not** discover
  or enumerate branches, list tags, or call the GitHub API — see
  [Why branch selection stays off the device](#why-branch-selection-stays-off-the-device).
- "Is there an update?" is decided purely by comparing the manifest's `version`
  to `current_version`. A newer version means update; nothing else is consulted.
- Each listed file is downloaded from `{base}/files/{device-path}` and verified
  by SHA-256 + size before install.

So choosing *which* release a device runs is done by controlling **what
`manifest.json` on that one branch says** — not by pointing the device somewhere
new. That branch is the device's *channel*.

## Publishing a release (desktop / CI)

`scrollkit.ota.publish` is the library-blessed producer side — use it instead of
hand-rolling a manifest script. It is **desktop/CI only** (it shells out to
`git` and raises `ImportError` on CircuitPython).

```python
from scrollkit.ota.publish import build_manifest, publish_to_branch

# 1. Walk a source tree -> manifest.json + a files/ mirror, with per-file
#    size + SHA-256. Keys are absolute on-device paths under device_root.
build_manifest("src/", "build/ota", device_root="/src", version="1.4.0")

# 2. Replace the channel branch's contents with that payload (a single fresh,
#    parentless commit) and force-push it. Devices read this branch.
publish_to_branch("build/ota", repo_path=".", channel_branch="live",
                  commit_message="Publish OTA 1.4.0")
```

`build_manifest` never publishes secrets or machine-local state: `secrets.py`,
`settings.json`, `logs/error_log`, `__pycache__`, `*.pyc`, `.git`, and
`credentials` are always excluded (extend with `extra_excludes=`).

The same thing from the command line:

```bash
python -m scrollkit.ota.publish src/ --version 1.4.0 --root /src --channel live --repo .
# add --dry-run to print the git commands (and stage the payload) without pushing
```

`publish_to_branch(..., dry_run=True)` (and `--dry-run`) is the CI-friendly mode:
it stages the payload and **prints the exact git commands** for a workflow to run,
without touching any git state itself. It's pure git — no GitHub API, no tokens.

## Recommended release model

A single public repo serves both development and releases, using a **hybrid** of
immutable archives and one mutable channel the device tracks:

| Ref | Mutability | Who reads it |
|-----|-----------|--------------|
| `release-MAJOR.MINOR` branch (or a tag) | **immutable** archive of a cut release | humans, CI, `git` history |
| `live` channel branch | **overwritten** on each publish (force-push) | the **device**, over `raw.githubusercontent.com` |

The flow: a maintainer cuts a release by creating a `release-1.4` branch (or
pushing a tag); CI runs `scrollkit.ota.publish` to generate the payload and
publish it to the `live` channel branch; devices pointed at `branch="live"` see
the new `version` in `manifest.json` and update. The channel name is configurable
(`--channel` / `channel_branch=`) — `live` is just the default, chosen to avoid
confusion with the `release-*` archive branches. CI/script is the bridge between
the immutable archives and the channel.

## Why branch selection stays off the device

The device **must not** enumerate or discover branches (e.g. calling GitHub's
REST `/branches` API). Branch/version selection is a desktop/CI concern — the
device only reads one fixed channel branch. This is deliberate:

- **Rate limits.** Unauthenticated GitHub API is 60 requests/hour per IP. A
  boot-loop, or several devices behind one NAT, hits `403` and **starves
  updates** exactly when you need them. `raw.githubusercontent.com` is a CDN
  without that per-IP API budget.
- **RAM.** CircuitPython's `json.loads` needs one contiguous buffer; a growing
  `/branches` array eventually `MemoryError`s on the ~2 MB ESP32-S3 heap.
- **Latency.** The API is slower and un-CDN'd, stalling the cooperative asyncio
  display loop while it blocks.

Keep the answer to "which release?" in the published `manifest.json`, not in
on-device branch logic.

## The recovery guarantee

OTA only ever writes into `/src`. **`boot.py` and the update system are frozen
and never modified by OTA.** Because they stay intact regardless of any `/src`
payload failure, the update system can always re-fetch a known-good version on
the next boot — a bad update can't disable the updater. The previous `/src`
version is also kept as a backup so a validated-but-bad update can be restored.

!!! danger "Never modify boot.py or code.py"
    The recovery design depends on `boot.py`/`code.py` staying frozen. The
    library must never write a `boot.py` supervisor of its own — the existing
    frozen one *is* the supervisor.

## On-device install UI

`OTAClient` is headless — it reports progress through callbacks but knows nothing
about a display. `scrollkit.ota.display_progress.OTAProgressDisplay` wraps an
already-configured client to add the on-panel UX and the staged-install flow, so the
client stays decoupled from the display and the update *source* stays your concern:

```python
from scrollkit.ota.client import OTAClient
from scrollkit.ota.display_progress import OTAProgressDisplay

client = OTAClient.for_github("owner", "repo", branch="live", current_version="1.0.0")
ota = OTAProgressDisplay(client, display=app.display)

# On boot, before the display loop owns the screen: apply anything staged.
await ota.install_pending()        # shows "Installing… DO NOT UNPLUG!", applies, reboots

# From a web "update" route (synchronous, safe off the display loop):
if ota.schedule_update():          # checks + downloads to the staging dir
    ...                            # then reboot; install_pending() applies it next boot
```

Status frames are stacked short lines (a 64px panel clips a long single line), and
every method swallows display/client errors rather than propagating them into the
boot/OTA flow.

## Pieces

| Module | Role |
|--------|------|
| `ota.client` | `OTAClient` — check / download / apply (auto-restores backup on install failure) / reboot_device (device) |
| `ota.manifest` | `UpdateManifest` — version, file list, checksums, requirements |
| `ota.display_progress` | `OTAProgressDisplay` — display-progress + staged-install UI over a client (device) |
| `ota.publish` | `build_manifest` / `publish_to_branch` — produce + publish a release (**desktop / CI only**) |

## No pre/post-update scripts (trust model)

Older manifests could carry `pre_update_scripts` / `post_update_scripts` —
Python snippets that the device `exec()`'d around an update. That feature has
been **removed**: the snippets ran with full device privileges from an unsigned
downloaded manifest (remote code execution for anyone who could publish to your
update URL), and no publisher ever emitted one. Updates are file swaps only.

- Manifests that still contain the (always-empty) script keys are accepted and
  the keys are silently ignored — old manifests stay compatible.
- If a future migration genuinely needs a hook (e.g. moving a settings file
  between schema versions), ship the migration as *code in the update itself*
  that runs on next boot — it is then checksummed like every other file —
  rather than reintroducing manifest-carried snippets.
