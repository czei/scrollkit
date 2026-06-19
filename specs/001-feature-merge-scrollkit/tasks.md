# Tasks: Merge ScrollKit Library and SLDK into a Single Unified Library

**Input**: Design documents from `/specs/001-feature-merge-scrollkit/`
**Prerequisites**: plan.md, research.md, data-model.md, contracts/, quickstart.md

## Context

This is a **migration/consolidation**, not greenfield. SLDK (`sldk/src/sldk/`) is the architectural base; its modules move into `src/scrollkit/` and their internal `sldk.*` imports become `scrollkit.*`. ScrollKit's existing `config/`, `network/wifi_manager.py`, `network/http_client.py`, and `utils/` are **kept**. ScrollKit's `display/*`, `ota/ota_updater.py`, and superseded `network/server_adapters.py` are **retired**. ThemeParkWaits app code in `src/` is **untouched (out of scope)**.

**Key source → destination map**
| Source | Destination | Action |
|--------|-------------|--------|
| `sldk/src/sldk/app/` | `src/scrollkit/app/` | migrate |
| `sldk/src/sldk/display/` | `src/scrollkit/display/` | migrate (replaces old display/) |
| `sldk/src/sldk/effects/` | `src/scrollkit/effects/` | migrate |
| `sldk/src/sldk/web/` | `src/scrollkit/web/` | migrate |
| `sldk/src/sldk/ota/` | `src/scrollkit/ota/` | migrate (replaces ota_updater.py) |
| `sldk/src/sldk/simulator/` | `src/scrollkit/simulator/` | migrate |
| `src/scrollkit/config/` | (in place) | keep |
| `src/scrollkit/network/wifi_manager.py`, `http_client.py` | (in place) | keep |
| `src/scrollkit/utils/` | (in place) | keep |

## Format: `[ID] [P?] Description`
- **[P]**: Can run in parallel (different files, no dependencies)
- All paths absolute from repo root: `/Users/czei/Documents/Projects/ScrollKit/ScrollKit Library/`

---

## Phase 3.1: Setup

- [X] **T001** Create the merged package directory skeleton under `src/scrollkit/`: ensure `app/`, `effects/`, `web/`, `simulator/` exist (new), and `display/`, `ota/` are ready to be replaced. Add empty `__init__.py` placeholders for `app/`, `effects/`, `web/`. Keep existing `config/`, `network/`, `utils/`. Create test dirs `test/unit/contract/`, `test/unit/app/`, `test/unit/effects/`, `test/unit/web/`, `test/unit/ota/`, `test/unit/simulator/`.
- [X] **T002** Update `pyproject.toml` for the merged `scrollkit` package: declare package `scrollkit` at `src/scrollkit`, add desktop dev extras (`pygame`, `aiohttp`, `requests`, `pytest`, `pytest-cov`, `mkdocs`, `mkdocs-material`, `mkdocstrings`). Confirm `pytest.ini` `testpaths`/`pythonpath` include `src` and `test`.
- [X] **T003** [P] Confirm `make lint-errors` (ruff) covers `src/scrollkit/` and passes on the current tree; record any pre-existing failures so post-migration regressions are distinguishable.

---

## Phase 3.2: Contract Tests First (TDD) ⚠️ MUST FAIL BEFORE 3.3

**CRITICAL: Write/copy these tests and confirm they FAIL (import errors / missing symbols) before any migration in Phase 3.3.**

- [X] **T004** [P] Copy `specs/001-feature-merge-scrollkit/contracts/display_contract.py` → `test/unit/contract/test_display_contract.py`. Tests `scrollkit.display.interface.DisplayInterface` and `scrollkit.display.unified.UnifiedDisplay` (abstractness, interface methods, 64×32 dims).
- [X] **T005** [P] Copy `contracts/app_contract.py` → `test/unit/contract/test_app_contract.py`. Tests `scrollkit.app.minimal.MinimalLEDApp` and `scrollkit.app.base.ScrollKitApp` (instantiation, `show_text`/`scroll_text`/`clear`, subclassing, `run` is coroutine).
- [X] **T006** [P] Copy `contracts/ota_contract.py` → `test/unit/contract/test_ota_contract.py`. Tests `scrollkit.ota.client.OTAClient` and `scrollkit.ota.manifest.UpdateManifest` (roundtrip, version compare, GitHub URL accepted, check returns tuple).
- [X] **T007** [P] Copy `contracts/content_queue_contract.py` → `test/unit/contract/test_content_queue_contract.py`. Tests `scrollkit.display.content` (StaticText/ScrollingText/DisplayContent), `scrollkit.display.queue.DisplayQueue`, `scrollkit.display.strategy.Priority` (priority order, expiry, eviction, `__len__`).
- [X] **T008** Run `PYTHONPATH=src python -m pytest test/unit/contract/ -v` and confirm **all contract tests FAIL** (missing modules/symbols). Record the failure list as the green-target for T027.

---

## Phase 3.3: Core Migration (ONLY after contract tests are failing)

### Utilities & Config (no internal deps — kept from ScrollKit)
- [X] **T009** [P] Audit `src/scrollkit/utils/` (`error_handler.py`, `color_utils.py`, `system_utils.py`, `timer.py`, `url_utils.py`, `image_processor.py`): ensure none import retired modules; confirm exports `rgb_to_hex`, `hex_to_rgb`, `scale_brightness` exist in `color_utils.py` (add thin aliases if names differ) and `ErrorHandler` in `error_handler.py`.
- [X] **T010** [P] Audit `src/scrollkit/config/settings_manager.py`: confirm `SettingsManager` (get/set/save_settings/load_settings/get_scroll_speed/get_pretty_name) is standalone and imports nothing being retired.

### Network (depends on utils/config)
- [X] **T011** Review and retire superseded ScrollKit network modules: delete `src/scrollkit/network/server_adapters.py` (replaced by SLDK web adapters). Inspect `async_http_request.py` and `http_response_patch.py` — keep ONLY if `http_client.py` imports them; otherwise retire. Update `src/scrollkit/network/__init__.py`.
- [X] **T012** Keep `src/scrollkit/network/wifi_manager.py` and `http_client.py`. In `http_client.py`, document the CircuitPython blocking-I/O reality (FR-029), add bounded socket timeouts, and ensure chunked reads `await asyncio.sleep(0)` between chunks where the path allows. Verify `WiFiManager` connect/scan loops yield (`await asyncio.sleep(0)`) so they don't starve the display loop.

### Simulator (no internal deps)
- [X] **T013** [P] Move `sldk/src/sldk/simulator/` → `src/scrollkit/simulator/` (use `git mv` to preserve history). Replace every internal `sldk.simulator` / `from sldk.` import with `scrollkit.` equivalents across `core/`, `displayio/`, `adafruit_bitmap_font/`, `adafruit_display_text/`, `terminalio/`, `devices/`. Keep `fonts/` (BDF) as-is. Verify `from scrollkit.simulator.devices.matrixportal_s3 import MatrixPortalS3` imports cleanly on desktop.

### Display (depends on utils/simulator) — replaces old ScrollKit display/
- [X] **T014** Migrate SLDK `display/interface.py`, `hardware.py`, `simulator.py`, `unified.py` → `src/scrollkit/display/`. Delete old `display_interface.py`, `generic_display.py`, `display_factory.py`. Rewrite the platform-detect branch in `unified.py`/`simulator.py` to import from `scrollkit.simulator` (no relative path hack). Confirm `UnifiedDisplay` reports `width==64`, `height==32` and implements the full `DisplayInterface`.
- [X] **T015** Migrate SLDK `display/content.py` + `enhanced_content.py` → `src/scrollkit/display/content.py` (+ `enhanced_content.py`). Ensure `DisplayContent`, `StaticText`, `ScrollingText` accept `color`, `priority`, and `duration` kwargs and expose `is_complete()`, `update()`, async `render(display)` per `content_queue_contract.py`.
- [X] **T016** Migrate SLDK `display/strategy.py` → `src/scrollkit/display/strategy.py`. Confirm the `Priority` enum exposes `IDLE, LOW, NORMAL, HIGH, SYSTEM` with explicit integer values (no `enum.auto()` — CircuitPython).
- [X] **T017** Migrate SLDK `display/queue.py` → `src/scrollkit/display/queue.py`. Implement the explicit eviction policy from data-model.md: on full queue, SYSTEM always admitted (evict lowest-priority oldest non-SYSTEM); higher-priority displaces lowest; lower-or-equal-than-all rejected (`add` returns `False`); SYSTEM never evicted by `add`. Implement `peek`, `pop`, `expire`, `__len__`.
- [X] **T018** Migrate SLDK `display/manager.py` and `display/devices/` → `src/scrollkit/display/`. Delete retired `message_queue.py`, `roller_coaster_animation.py`, `roller_coaster_animation_cp.py`. Update `src/scrollkit/display/__init__.py` to export the new surface.

### Effects (depends on display)
- [X] **T019** [P] Migrate SLDK `effects/` (`base.py`, `effects.py`, `transitions.py`, `basic_transitions.py`, `particles.py`, `reveal.py`) → `src/scrollkit/effects/`. Replace `sldk.*` imports with `scrollkit.*`. Confirm `EffectsEngine` keeps the max-2-concurrent / pre-allocated-color-table memory behavior.

### Web (depends on network/config)
- [X] **T020** [P] Migrate SLDK `web/` (`server.py`, `adapters.py`, `handlers.py`, `forms.py`, `templates.py`) → `src/scrollkit/web/`. Rename `SLDKWebServer` → `ScrollKitWebServer` (keep `SLDKWebServer` as a deprecated alias). Replace `sldk.*` imports. Confirm the CircuitPython (`adafruit_httpserver`) and desktop (async) adapters both select via the platform check, with no app-layer code changes.

### OTA (depends on network/utils)
- [X] **T021** Migrate SLDK `ota/` (`client.py`, `manifest.py`, `server.py`, `updater.py`) → `src/scrollkit/ota/`. Delete retired `ota_updater.py`. Replace `sldk.*` imports. Confirm `UpdateManifest.from_dict/to_json/compare_version/validate` and `OTAClient.check_for_updates/download_update/apply_update` match `ota_contract.py`.
- [X] **T022** Wire `OTAClient` for GitHub raw-content delivery (research D-003): accept a `https://raw.githubusercontent.com/{owner}/{repo}/{branch}` base, fetch `manifest.json`, download only changed files by checksum. Retain the previous `/src` version in `backup_dir` for restore. Add a docstring/comment stating recovery relies on the immutable `boot.py` + update system (never modify `boot.py`/`code.py`).

### App (depends on everything above)
- [X] **T023** Migrate SLDK `app/base.py` → `src/scrollkit/app/base.py`. Expose `ScrollKitApp` (rename `SLDKApp`, keep `SLDKApp` as alias). Wire `display` (UnifiedDisplay), effects, web, ota, network, config submodules with `scrollkit.*` imports. Preserve the three-process memory ladder (display always; data ≥30KB; web ≥50KB) and add the effects-engine guard (≥80KB per data-model).
- [X] **T024** Migrate SLDK `app/minimal.py` → `src/scrollkit/app/minimal.py`. Confirm `MinimalLEDApp` instantiates with no args and provides `show_text`, `scroll_text`, `clear` per `app_contract.py`. Replace `sldk.*` imports.
- [X] **T025** In `src/scrollkit/app/base.py`, implement the FR-029 behavior: before yielding to a blocking network call in the data-update path, render a static/loading frame; document that long transfers should chunk + `await asyncio.sleep(0)` (the pattern the hard demo shows).

### Public API
- [X] **T026** Write `src/scrollkit/__init__.py` as the lightweight surface (research D-011): `__version__` only, **no eager submodule imports**. Verify `import scrollkit` does not transitively import `app`/`display`/`effects`/`web`/`ota`.

### Contract Gate
- [X] **T027** Run `PYTHONPATH=src python -m pytest test/unit/contract/ -v`. All four contract test files must be **GREEN**. Fix import paths, class names, and signature mismatches surfaced by T004–T008.

---

## Phase 3.4: Integration & Validation

- [X] **T028** Migrate SLDK unit tests into `test/unit/` (`app/`, `display/`, `effects/`, `content/`, `web/`, `simulator/`). Replace `sldk.*` imports with `scrollkit.*`. (Source: SLDK `test/unit/` tree — `test_sldk_app.py`, `test_minimal_app.py`, `test_content_classes.py`, `test_content_queue.py`, `test_effects_engine.py`, `test_particles.py`, `test_template_engine.py`, `test_simulator_imports.py`, `test_circuitpython_compat.py`.)
- [X] **T029** Confirm retained ScrollKit unit tests for `config/`, `network/`, `utils/` still pass against the merged package; update any imports that referenced retired modules (`message_queue`, `server_adapters`, `ota_updater`, `generic_display`).
- [X] **T030** Write `test/memory_baseline.py`: runs `gc.collect()` then prints `gc.mem_free()` (a) after `import scrollkit` and (b) after constructing a `ScrollKitApp`. Capture the SLDK pre-merge numbers, commit `test/fixtures/memory_baseline.json`, and assert merged readings are ≤ baseline (FR-046). Mark the device-only path with a skip when `gc.mem_free` is absent (desktop).
- [X] **T031** Run the full unit suite: `make test-unit` (`python -m pytest test/unit -v`). Iterate until green. Then `make lint-errors`.
- [X] **T032** Retire the `sldk/` directory (`git rm -r sldk/`) ONLY after T027–T031 are green. Grep the repo for stray `import sldk` / `from sldk` and fix any remaining references.

---

## Phase 3.5: Demos & Documentation

- [X] **T033** [P] Create `demos/easy/hello_world.py` (FR-037): `MinimalLEDApp().scroll_text("Hello, World!", ...)`, no network, runs on the simulator. Add a comment header (what it shows, no data source).
- [X] **T034** [P] Create `demos/medium/temperature.py` (FR-038): `ScrollKitApp` fetching current temperature from open-meteo (no API key) via `HttpClient`, scrolled with periodic refresh. Comment header names the data source. (Mirror quickstart Tutorial 2.)
- [X] **T035** Create `demos/hard/full_app.py` (FR-039/FR-042/FR-042b): full app — web config (`SettingsManager` + `ScrollKitWebServer`), priority queue, effects/transitions, OTA check at startup, and CoinGecko crypto prices fetched **in chunks of 3 with `await asyncio.sleep(0)` between chunks** (the blocking-HTTP workaround). Comment the trade-off. (Mirror quickstart Tutorial 3.)
- [X] **T036** [P] Migrate/adapt remaining useful SLDK examples (`effects_demo.py`, `reveal_effect_*`, `enhanced_content_demo.py`, `animation_demo.py`) into `demos/medium/` or `demos/hard/`, updating imports to `scrollkit.*`. Ensure each demonstrates content-queue prioritization or effects per FR-042.
- [X] **T037** [P] Create `mkdocs.yml` (material theme) at repo root and `docs/` structure: `index.md`, per-module pages (display, effects, web, ota, network, config, utils, simulator) explaining what each does (FR-036).
- [X] **T038** [P] Write `docs/tutorials/easy.md`, `medium.md`, `hard.md` from quickstart.md (FR-037–FR-039), including the chunked-fetch explanation in the hard tutorial.
- [X] **T039** [P] Configure `mkdocstrings` and add `docs/reference.md` auto-generating the API reference for all public classes/functions (FR-040).
- [X] **T040** Validate: run each demo on the simulator (`PYTHONPATH=src python demos/easy/hello_world.py`, etc.) and confirm no errors; run `mkdocs build` and confirm it succeeds (FR-041, FR-036).
- [ ] **T041** Hardware smoke test (requires MatrixPortal S3): `make copy_to_circuitpy`, confirm boot + display works and run `test/memory_baseline.py` on-device to verify FR-046. *(Manual / device-dependent — may be deferred to the user.)*

---

## Phase 3.6: Deferred Polish (P2 — handle last)

- [ ] **T042** [P] Add an `.mpy` build pipeline: `make mpy` target using `mpy-cross` to pre-compile `src/scrollkit/`, and document `circup` for managing Adafruit bundle deps.
- [ ] **T043** [P] Evaluate optional PCF font track while preserving BDF parity (FR-015); document the memory trade-off. Do not remove BDF support.
- [ ] **T044** [P] Document the OTA pre/post-update script trust model (enabled vs sandboxed vs disabled-by-default on hardware) in `docs/`.

---

## Dependencies

- **Setup** (T001–T003) before everything.
- **Contract tests** (T004–T008) before all migration (T009–T026). They MUST fail first.
- **Dependency order** within Phase 3.3:
  - T009 (utils), T010 (config) → no deps.
  - T011–T012 (network) depend on utils/config.
  - T013 (simulator) → no deps.
  - T014–T018 (display) depend on utils (T009) + simulator (T013). T014→T015→T016→T017→T018 touch related files; treat as sequential.
  - T019 (effects) depends on display (T014–T018).
  - T020 (web) depends on network (T011–T012) + config (T010).
  - T021–T022 (ota) depend on network (T011–T012) + utils (T009).
  - T023–T025 (app) depend on display, effects, web, ota, network, config (everything above).
  - T026 (`__init__.py`) after app exists.
- **T027** (contract gate) after T026.
- **Integration** (T028–T032) after T027. T032 (retire sldk/) LAST in this phase.
- **Demos/docs** (T033–T040) after T031 (lib green). T035 depends on the full app + web + ota + effects.
- **T041** after T040 (and a physical device).
- **Polish** (T042–T044) last.

## Parallel Execution Examples

```
# Phase 3.2 — all four contract tests are independent files:
Task: "Copy display_contract.py → test/unit/contract/test_display_contract.py"   (T004)
Task: "Copy app_contract.py → test/unit/contract/test_app_contract.py"           (T005)
Task: "Copy ota_contract.py → test/unit/contract/test_ota_contract.py"           (T006)
Task: "Copy content_queue_contract.py → test/unit/contract/test_content_queue_contract.py" (T007)

# Phase 3.3 — utils, config, simulator are independent at the start:
Task: "Audit src/scrollkit/utils/ for retired imports + color/error exports"     (T009)
Task: "Audit src/scrollkit/config/settings_manager.py standalone"                (T010)
Task: "git mv sldk simulator → src/scrollkit/simulator, fix imports"             (T013)

# Phase 3.3 — once display is migrated, effects/web/ota touch separate trees:
Task: "Migrate SLDK effects/ → src/scrollkit/effects/"                           (T019)
Task: "Migrate SLDK web/ → src/scrollkit/web/, rename ScrollKitWebServer"        (T020)

# Phase 3.5 — demos and docs are independent files:
Task: "demos/easy/hello_world.py"                                                (T033)
Task: "demos/medium/temperature.py"                                              (T034)
Task: "mkdocs.yml + docs/ module pages"                                          (T037)
Task: "docs tutorials easy/medium/hard"                                          (T038)
```

## Notes
- `[P]` = different files, no dependencies. T014–T018 are NOT `[P]` (same `display/` package, sequential).
- Verify contract tests FAIL (T008) before migrating; verify GREEN (T027) after.
- Commit after each task. Use `git mv` for migrations to preserve history.
- Never touch `boot.py`, `code.py`, or any ThemeParkWaits file in `src/` (out of scope).
- After every code change run `make test-unit` per CLAUDE.md.

## Validation Checklist
- [x] All 4 contracts have test tasks (T004–T007)
- [x] All entities have migration tasks (DisplayContent/Queue/Priority T015–T017; UpdateManifest T021; SettingsManager T010; ScrollKitApp/MinimalLEDApp T023–T024; UnifiedDisplay T014; Effect T019)
- [x] All contract tests (T004–T008) come before implementation (T009+)
- [x] Parallel tasks are truly independent files
- [x] Each task specifies an exact file path
- [x] No `[P]` task modifies the same file as another `[P]` task
- [x] Memory baseline (FR-046), chunked-fetch (FR-042b), eviction policy, and lightweight `__init__` all have explicit tasks
