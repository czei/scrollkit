# OTA Updates

`scrollkit.ota` delivers over-the-air firmware updates from GitHub using a
manifest, with checksums and a recovery guarantee.

## How it works

```
manifest.json  (committed to a releases branch or attached to a GitHub Release)
   │  device fetches via raw.githubusercontent.com
   ▼
OTAClient.check_for_updates()   compares versions
   ▼
OTAClient.download_update()     downloads only changed files (by checksum)
   ▼
OTAClient.apply_update()        swaps files into /src, keeping a backup
```

```python
from scrollkit.ota.client import OTAClient

ota = OTAClient(
    update_server_url="https://raw.githubusercontent.com/OWNER/REPO/releases",
    current_version="1.0.0",
)
has_update, manifest = ota.check_for_updates()
if has_update:
    ota.download_update(manifest)
    ota.apply_update()   # reboots on CircuitPython
```

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

## Pieces

| Module | Role |
|--------|------|
| `ota.client` | `OTAClient` — check / download / apply / rollback |
| `ota.manifest` | `UpdateManifest` — version, file list, checksums, requirements |
| `ota.server` | `OTAServer` — host manifests/packages (desktop / CI) |
| `ota.updater` | thin orchestration over the client |

## Pre/post-update scripts (trust model)

A manifest may carry `pre_update_scripts` and `post_update_scripts` — Python
snippets run before/after an update is applied. They are powerful (they run with
full device privileges) and therefore a trust decision, not a convenience:

- **Treat them as remote code execution.** Whoever can publish a manifest to your
  update URL can run arbitrary code on the device. Only point a device at a
  manifest source you control.
- **Recommended default: disabled.** Unless you specifically need migration
  hooks (e.g. moving a settings file between schema versions), ship manifests
  with empty script lists. The library applies file updates without them.
- **If you enable them**, serve the manifest only over a channel you control
  (a private `releases` branch / signed release), and keep the snippets minimal
  and auditable. There is no sandbox on CircuitPython — a script can touch the
  filesystem, network, and hardware.
- **They do not gate recovery.** A failed or malicious script cannot disable the
  updater itself, because `boot.py` and the update system are frozen outside
  `/src` (see the recovery guarantee above) — but a malicious script *can* still
  damage `/src` and your data, which is why the source must be trusted.
