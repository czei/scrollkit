# Phase 0 Research: Merge ScrollKit + SLDK

## Decision Log

---

### D-001: Which framework's architecture to base the merge on

**Decision**: Use SLDK's architecture as the foundation. ScrollKit's utilities and WiFi/config modules are migrated in; ScrollKit's display queue, server adapters, and simple OTA are retired.

**Rationale**: SLDK is the more complete and production-hardened framework. It has a proper async app lifecycle, priority-based content queuing with duration tracking, an effects engine, a full displayio emulation layer for the simulator, a layered display abstraction, and a web server. ScrollKit's display queue (`MessageQueue`) and OTA updater are simpler but provide less capability. Merging the other direction would mean adding all of SLDK's features piecemeal on top of ScrollKit's simpler skeleton — more churn for less result.

**Alternatives considered**:
- Keep both frameworks as separate packages in the repo. Rejected: user's explicit goal is a single package with no divergence.
- Use ScrollKit as the base and graft SLDK features in. Rejected: SLDK's async architecture is not easily bolted on — it would require rewriting the core.

---

### D-002: Package name and install location

**Decision**: The merged package is named `scrollkit` and lives at `src/scrollkit/` — the existing location. The `sldk` directory is retired after migration.

**Rationale**: `scrollkit` is the established name. ThemeParkWaits and any future apps already import from `scrollkit`. Renaming would break existing code with no benefit.

**Alternatives considered**:
- Keep `sldk` as the package name. Rejected: breaks existing imports and the stated goal is `scrollkit`.

---

### D-003: OTA mechanism for GitHub

**Decision**: The merged OTA system uses SLDK's manifest-based `OTAClient`, but the manifest URL is constructed from GitHub raw content or release assets. The server-URL constructor argument accepts a GitHub URL pointing to a manifest.json in a `releases` branch or release asset.

**Rationale**: SLDK's OTA client already supports arbitrary HTTP servers. GitHub serves static files. The manifest.json can be committed to a dedicated `releases` branch (or attached to a GitHub Release tag), and the device fetches it directly via raw.githubusercontent.com. The ScrollKit `OTAUpdater`'s GitHub releases API approach (two-round-trip: list release → download files) is replaced by one-round-trip: fetch manifest → download listed files.

**Alternatives considered**:
- Keep ScrollKit's `OTAUpdater` (GitHub Releases API). Rejected: requires two API calls per update check, no checksums, no pre/post scripts, no rollback.
- Use GitHub Actions to push manifests to a separate update server. Rejected: unnecessary infrastructure.

**How it works**: 
```
manifest.json (in repo at releases/ branch or GitHub Release asset)
  → device fetches via: https://raw.githubusercontent.com/{owner}/{repo}/{branch}/manifest.json
  → manifest lists files + checksums + version
  → device downloads only changed files from:
    https://raw.githubusercontent.com/{owner}/{repo}/{tag}/{file_path}
```

**Recovery model (clarified)**: There is NO contradiction with the "never modify boot.py" rule. `boot.py` is deliberately frozen and holds the boot + update systems; OTA only ever writes into `/src`. Because `boot.py` and the update system are never touched by OTA, a bad `/src` payload cannot disable the update mechanism — on the next boot the (intact) update system can re-fetch a known-good version. The OTA client additionally keeps a backup of the previous `/src` version so a validated-but-bad update can be restored. The library does NOT, and MUST NOT, write a `boot.py` supervisor of its own — the existing frozen `boot.py` already is the supervisor.

---

### D-004: WiFi management

**Decision**: Keep ScrollKit's `WiFiManager` verbatim in `src/scrollkit/network/wifi_manager.py`. SLDK has no equivalent.

**Rationale**: WiFiManager is 781 lines of CircuitPython-specific logic (WPA2, AP mode, network scanning, web-based WiFi config, adafruit_requests session creation). SLDK simply assumes a network connection exists. The merged library needs to provide connection management.

---

### D-005: Settings persistence

**Decision**: Keep ScrollKit's `SettingsManager` verbatim in `src/scrollkit/config/settings_manager.py`. SLDK has no equivalent.

**Rationale**: SLDK has no runtime settings persistence. Applications need to read/write JSON config that survives reboots. SettingsManager handles CircuitPython's bool serialization quirks (bools stored as strings), which is a real compat issue.

---

### D-006: MessageQueue vs DisplayQueue

**Decision**: Retire ScrollKit's `MessageQueue`. The merged library exposes SLDK's `DisplayQueue` + `DisplayContent` system as the primary queuing mechanism.

**Rationale**: `MessageQueue` is function-based (takes callables + params); `DisplayQueue` is content-based (takes `DisplayContent` objects with priorities and durations). The content-based approach is more inspectable, testable, and extensible. The merged library exposes only `DisplayQueue`; a thin `FunctionContent` wrapper can be added later if a callable-style convenience is wanted. (Migrating the existing ThemeParkWaits app onto this queue is out of scope — see D-013.)

---

### D-007: Simulator strategy

**Decision**: Use SLDK's simulator unchanged as `src/scrollkit/simulator/`. ScrollKit's `GenericDisplay` currently loads SLDK's simulator via a relative path hack; after the merge the simulator is a first-class submodule.

**Rationale**: SLDK's simulator is a complete displayio emulation stack (displayio, bitmap fonts, adafruit_display_text, terminalio, pygame-based window). It's already the only simulator both frameworks use. Making it a proper submodule removes the path hack and makes imports clean.

---

### D-008: Test consolidation

**Decision**: Merge SLDK's tests into `test/unit/` alongside ScrollKit's existing unit tests. SLDK's tests move to `test/unit/sldk/` initially, then rename to match the new module paths.

**Rationale**: One test runner (`pytest`), one coverage report. The existing `test/` structure already has a good hierarchy (unit/, integration/, fixtures/).

---

### D-009: Documentation toolchain

**Decision**: mkdocs with the `material` theme in the `docs/` directory. `mkdocs.yml` at repo root.

**Rationale**: mkdocs is the standard Python library documentation tool. The material theme is the most-used, well-documented choice. It supports code tabs (useful for showing hardware vs simulator variants), admonitions, and auto-generated API reference via `mkdocstrings`.

---

### D-010: Demo organization

**Decision**: `demos/` directory at repo root, split into three complexity tiers: `demos/easy/`, `demos/medium/`, `demos/hard/`. Each demo is a standalone Python file runnable with `PYTHONPATH=src python demos/<tier>/<demo>.py`, rendered on the simulated scrolling LED hardware. The SLDK `examples/` directory is migrated and consolidated here.

**Rationale**: Single place for runnable examples at graded difficulty. Since this is ScrollKit (scrolling displays), every demo can exercise the simulated scrolling hardware. The `PYTHONPATH=src` pattern already works. Demos run on desktop via the simulator with no extra setup and no physical device.

**Data sources** (must be no-API-key public sources so any user can run them):
- Easy: no network — pure scrolling text.
- Medium: current temperature via **open-meteo** (`https://api.open-meteo.com/v1/forecast?...&current=temperature_2m`) — no key required.
- Hard: combine open-meteo temperature with a second source such as **CoinGecko** crypto prices (`https://api.coingecko.com/api/v3/simple/price?...`) — no key required — plus web config, priority queue, effects, OTA.

Stock-price APIs are intentionally avoided because the free ones require API keys; temperature + crypto give key-free live data that demonstrates the same patterns.

---

### D-011: Lightweight package `__init__.py`

**Decision**: The top-level `src/scrollkit/__init__.py` exposes only version metadata (and at most a tiny curated surface), NOT eager imports of every submodule. Users import from submodules directly (`from scrollkit.app.minimal import MinimalLEDApp`).

**Rationale**: On CircuitPython every imported module allocates a globals dict + bytecode overhead. Eagerly importing app/display/effects/web/ota/network/utils at `import scrollkit` time could cost 50–100 KB of SRAM before the app starts — a direct memory regression. Submodule imports keep the footprint pay-as-you-go, which is also what the quickstart already demonstrates.

---

### D-012: HTTP execution model on CircuitPython

**Decision**: Do NOT promise "transparent" sync/async HTTP. The client exposes a consistent API, but on CircuitPython `adafruit_requests` blocks the asyncio event loop. The app framework renders a static/loading frame before yielding to a blocking call; long transfers (OTA) are chunked with `await asyncio.sleep(0)` between reads where the library allows.

**Rationale**: `adafruit_requests` wraps blocking C-level sockets; you cannot inject `await` into its internal `socket.recv()`. Pretending otherwise produces a leaky abstraction that silently freezes the 20 FPS display loop. Honest, documented blocking with a loading-state UX is correct for this target. (True non-blocking would require dropping to raw non-blocking sockets + a custom HTTP parser — out of scope.)

**App-level workaround (demonstrated in the hard demo, FR-042b)**: when an app needs a lot of data (e.g. prices for many tickers), it should split the fetch into sizable chunks — one short blocking request each — and `await asyncio.sleep(0)` between chunks. One big request that returns everything blocks the scroll for the whole transfer; many small requests keep each blocking window short enough that the scrolling display keeps moving between them. Total latency goes up, but the screen never locks up. This is the practical pattern users should copy.

---

### D-013: ThemeParkWaits is out of scope

**Decision**: This project delivers a standalone `scrollkit` library + demos. Porting the existing ThemeParkWaits application onto the merged library is explicitly NOT part of this work. ThemeParkWaits files in `src/` are left untouched.

**Rationale**: ThemeParkWaits is a substantial application; migrating it (especially off the retired `MessageQueue` onto `DisplayQueue`) is too large to fold into the merge. The library must stand on its own and prove itself through its own demos. ThemeParkWaits porting can be a separate follow-on effort.

---

## Summary: What Gets Migrated vs Retired vs Kept

| Component | Source | Action | Destination |
|-----------|--------|---------|-------------|
| App base classes (`SLDKApp`, `MinimalLEDApp`) | SLDK `app/` | Migrate | `src/scrollkit/app/` |
| Display interface, hardware, simulator, unified | SLDK `display/` | Migrate | `src/scrollkit/display/` |
| DisplayQueue, DisplayManager, DisplayStrategy | SLDK `display/` | Migrate | `src/scrollkit/display/` |
| DisplayContent, ScrollingText, StaticText | SLDK `display/` | Migrate | `src/scrollkit/display/` |
| EffectsEngine, transitions, particles | SLDK `effects/` | Migrate | `src/scrollkit/effects/` |
| Web server + adapters | SLDK `web/` | Migrate | `src/scrollkit/web/` |
| OTA client + manifest | SLDK `ota/` | Migrate + update for GitHub | `src/scrollkit/ota/` |
| Simulator (displayio emulation) | SLDK `simulator/` | Migrate | `src/scrollkit/simulator/` |
| SettingsManager | ScrollKit `config/` | Keep | `src/scrollkit/config/` |
| WiFiManager | ScrollKit `network/` | Keep | `src/scrollkit/network/` |
| HttpClient | ScrollKit `network/` | Keep | `src/scrollkit/network/` |
| ErrorHandler, color_utils, system_utils, timer, url_utils | ScrollKit `utils/` | Keep | `src/scrollkit/utils/` |
| MessageQueue | ScrollKit `display/` | **Retire** | — |
| ScrollKit's `GenericDisplay`, `DisplayInterface` | ScrollKit `display/` | **Retire** | replaced by SLDK versions |
| ScrollKit's `OTAUpdater` | ScrollKit `ota/` | **Retire** | replaced by SLDK OTA |
| ScrollKit's `server_adapters.py` | ScrollKit `network/` | **Retire** | replaced by SLDK web server |
| ThemeParkWaits app (`app.py`, `main.py`, etc.) | `src/` | **Untouched (out of scope)** | `src/` — not ported, not modified |
| App models, API client, UI modules | `src/models/`, `src/api/`, `src/ui/` | **Untouched (out of scope)** | unchanged, not ported |
| SLDK examples | `sldk/examples/` | Migrate + adapt | `demos/easy/`, `demos/medium/`, `demos/hard/` |
| SLDK tests | `sldk/tests/` | Migrate | `test/unit/` |

---

## CircuitPython Compatibility Notes

All code merged from SLDK has been verified to use CircuitPython-safe patterns:
- `ValueError` instead of `json.JSONDecodeError` ✓
- `OSError` instead of `FileNotFoundError` ✓
- `gc.mem_free() if hasattr(gc, 'mem_free') else 100000` for memory checks ✓
- try/except ImportError guards for all CircuitPython-only modules ✓
- `asyncio.create_task` and `asyncio.gather` (both platforms have asyncio) ✓
- No `typing` module imports at runtime ✓
- No `match/case` statements ✓

One issue to resolve in SLDK's OTA client: it uses `import requests` (desktop) vs `import adafruit_requests as requests` (CircuitPython). The try/except is correct but uses the desktop `requests` library for file downloading, which requires `requests` to be installed. This is fine for desktop dev but should be documented.

---

## Memory Thresholds (from SLDK app/base.py)

| Feature | Minimum Free Memory |
|---------|---------------------|
| Display process | Always on |
| Data update process | 30 KB free |
| Web server | 50 KB free |
| Skip a single data update | 20 KB free |

These thresholds are the SLDK baseline. The merge must not increase them.
