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
