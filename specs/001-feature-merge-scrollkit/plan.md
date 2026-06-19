# Implementation Plan: Merge ScrollKit Library and SLDK into a Single Unified Library

**Branch**: `001-feature-merge-scrollkit` | **Date**: 2026-06-18 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/001-feature-merge-scrollkit/spec.md`

## Execution Flow (/plan command scope)
```
1. Load feature spec ✓
2. Fill Technical Context ✓
3. Fill Constitution Check ✓
4. Evaluate Constitution Check → PASS ✓
5. Execute Phase 0 → research.md ✓
6. Execute Phase 1 → contracts/, data-model.md, quickstart.md, CLAUDE.md update ✓
7. Re-evaluate Constitution Check → PASS ✓
8. Plan Phase 2 → Task generation approach described below ✓
9. STOP - Ready for /tasks command
```

---

## Summary

Merge two parallel LED matrix display frameworks (`src/scrollkit/` and `sldk/`) into a single `scrollkit` package. SLDK's async app architecture, priority-based display queue, effects engine, full displayio simulator, and manifest-based OTA become the foundation. ScrollKit's WiFi manager, settings persistence, HTTP client, and utility modules are integrated since SLDK lacks equivalents. The merged result lives at `src/scrollkit/`, the `sldk/` directory is retired, and a mkdocs documentation site plus an easy/medium/hard `demos/` directory round out the deliverable.

Porting the existing ThemeParkWaits application is explicitly out of scope — the library stands on its own and uses its own demos (run against the simulated scrolling LED hardware) as the demonstration vehicle. OTA recovery relies on the immutable `boot.py` + update system (frozen outside `/src`, never modified by OTA), so no `boot.py`/`code.py` changes are needed.

---

## Technical Context

**Language/Version**: Python 3.11 (desktop) + CircuitPython 8.x/9.x (hardware)  
**Primary Dependencies**: pygame (simulator), adafruit_httpserver (CircuitPython web), aiohttp (desktop web), pytest (testing)  
**Storage**: Filesystem JSON (settings), GitHub raw content (OTA manifests + firmware)  
**Testing**: pytest with MagicMock for hardware components  
**Target Platform**: Adafruit MatrixPortal S3 (CircuitPython) + macOS desktop (simulator)  
**Project Type**: Single standalone library package with its own demos (ThemeParkWaits porting out of scope)  
**Performance Goals**: 20 FPS display refresh; OTA check < 5s; web config response < 500ms  
**Constraints**: Same or better memory footprint vs SLDK baseline; CircuitPython 8.x compatibility; no Python standard library modules unavailable in CircuitPython  
**Scale/Scope**: Single embedded device; library is the output, not a service

---

## Constitution Check

*The project has no filled-in constitution (generic template only). Applying CLAUDE.md principles and general embedded software engineering principles:*

| Principle | Check | Status |
|-----------|-------|--------|
| No modification to `boot.py` or `code.py` | Merge touches only `src/scrollkit/` and adds `demos/`, `docs/`. OTA recovery deliberately relies on the immutable `boot.py` + update system staying frozen — central to the design, not a workaround | PASS |
| No new `.py` files in root directory | All new files go in `src/`, `demos/`, `docs/` | PASS |
| All application logic in `/src` | ThemeParkWaits app stays in `src/`; library in `src/scrollkit/` | PASS |
| CircuitPython compatibility | SLDK already uses correct patterns; SettingsManager/WiFiManager verified | PASS |
| One LED display for both environments | UnifiedDisplay provides single interface; simulator stays in sync | PASS |
| One web UI for both environments | ScrollKitWebServer uses adapter pattern (CircuitPython + desktop) | PASS |
| Tests after every code change | Contract tests written first; unit tests merged from both suites | PASS |
| Memory constraints respected | SLDK graduated feature ladder preserved; no feature raises baseline | PASS |
| No thread safety violations in web server | Web server cannot modify display queue directly (SLDK design) | PASS |

**No constitution violations identified.** No Complexity Tracking entries needed.

---

## Project Structure

### Documentation (this feature)
```
specs/001-feature-merge-scrollkit/
├── plan.md                        <- This file
├── spec.md                        <- Feature specification
├── research.md                    <- Phase 0: decisions + rationale
├── data-model.md                  <- Phase 1: package structure + entities
├── quickstart.md                  <- Phase 1: 3 tutorials
├── contracts/
│   ├── display_contract.py        <- Phase 1: DisplayInterface + tests
│   ├── app_contract.py            <- Phase 1: ScrollKitApp + MinimalLEDApp + tests
│   ├── ota_contract.py            <- Phase 1: OTAClient + UpdateManifest + tests
│   └── content_queue_contract.py  <- Phase 1: DisplayContent + DisplayQueue + tests
└── tasks.md                       <- Phase 2: created by /tasks command
```

### Source Code (repository root)
```
src/scrollkit/          <- Merged library (SLDK-based + ScrollKit utilities)
├── app/
├── display/
├── effects/
├── web/
├── ota/
├── network/            <- WiFiManager + HttpClient from ScrollKit
├── config/             <- SettingsManager from ScrollKit
├── simulator/          <- SLDK simulator (displayio emulation)
└── utils/              <- ScrollKit utilities

src/                    <- ThemeParkWaits application (untouched structure)
├── app.py
├── main.py
├── themeparkwaits.py
├── models/
├── api/
└── ui/

demos/                  <- Runnable demos (migrated from sldk/examples/)
docs/                   <- mkdocs documentation
test/                   <- Consolidated test suite
├── unit/
│   ├── display/
│   ├── effects/
│   ├── app/
│   ├── ota/
│   ├── config/
│   ├── network/
│   └── utils/
└── integration/
```

**Structure Decision**: Single project (Option 1). This is a Python library, not a web/mobile app.

---

## Phase 0: Outline & Research - COMPLETE

*See [research.md](research.md) for full findings.*

**Key decisions made:**
- D-001: SLDK architecture is the base
- D-002: Package name stays `scrollkit`
- D-003: SLDK OTA client + GitHub raw content URLs
- D-004: ScrollKit WiFiManager kept (SLDK has none)
- D-005: ScrollKit SettingsManager kept (SLDK has none)
- D-006: MessageQueue retired, replaced by DisplayQueue
- D-007: SLDK simulator becomes `src/scrollkit/simulator/`
- D-008: Tests consolidated into `test/`
- D-009: mkdocs + material theme
- D-010: `demos/` directory at repo root

**No NEEDS CLARIFICATION markers remain.**

---

## Phase 1: Design & Contracts - COMPLETE

*See [data-model.md](data-model.md), [contracts/](contracts/), and [quickstart.md](quickstart.md).*

### Entities designed
- `DisplayContent` (base) + `StaticText`, `ScrollingText`
- `DisplayQueue` (priority + expiry)
- `Priority` (enum: IDLE / LOW / NORMAL / HIGH / SYSTEM)
- `UpdateManifest` (version, files, checksums)
- `SettingsManager` (JSON persistence)
- `ScrollKitApp` (full-featured async base)
- `MinimalLEDApp` (lightweight entry point)

### Contracts written (as failing test files)
- `contracts/display_contract.py` — DisplayInterface + UnifiedDisplay tests
- `contracts/app_contract.py` — ScrollKitApp + MinimalLEDApp tests
- `contracts/ota_contract.py` — OTAClient + UpdateManifest tests
- `contracts/content_queue_contract.py` — DisplayContent + DisplayQueue tests

### Quickstart written
- Tutorial 1 (easy): Hello World scrolling text (10 lines, MinimalLEDApp, no network)
- Tutorial 2 (medium): Live temperature from open-meteo (no API key) scrolled with periodic refresh (ScrollKitApp)
- Tutorial 3 (hard): Full app with web config, priority queue, effects, multiple public data sources, and OTA

---

## Phase 2: Task Planning Approach

*This section describes what the /tasks command will do — NOT executed during /plan.*

**Task Generation Strategy**:
- Load `.specify/templates/tasks-template.md` as base
- Generate tasks from Phase 1 design (contracts, data-model, quickstart, research)

**Ordering (TDD order: tests before implementation; dependency order: dependencies migrated before dependents)**:

1. **Setup** (2 tasks): Create package skeleton with a lightweight `__init__.py` (version metadata only, no eager submodule imports), pyproject.toml, pytest config
2. **Contract tests** [P]: Copy contract test files to `test/unit/`; run → confirm all FAIL
3. **Utils module** [P]: Port ScrollKit utils into scrollkit.utils (no internal deps)
4. **Config module** [P]: Port ScrollKit settings_manager into scrollkit.config (depends on utils)
5. **Network module** (2 tasks): Port ScrollKit wifi_manager + http_client into scrollkit.network; document the CircuitPython blocking-I/O behavior and add chunked cooperative yields where the library allows (depends on utils/config)
6. **Simulator migration** [P]: Move `sldk/simulator/` to `src/scrollkit/simulator/`; update imports (no internal deps)
7. **Display module** (5 tasks): Migrate SLDK display/ to src/scrollkit/display/; implement the explicit DisplayQueue eviction policy; update imports (depends on utils/simulator)
8. **Effects module** [P]: Migrate SLDK effects/ to src/scrollkit/effects/ (depends on display)
9. **Web module** [P]: Migrate SLDK web/ to src/scrollkit/web/ (depends on network/config)
10. **OTA module** (2 tasks): Migrate SLDK ota/ to src/scrollkit/ota/; wire GitHub raw-content URLs; retain previous `/src` version for restore; rely on immutable boot.py for recovery (depends on network/utils)
11. **App module** (3 tasks): Migrate SLDK app/ to src/scrollkit/app/; wire all submodules; render a loading frame before yielding to blocking network calls (depends on everything)
12. **Public API** (1 task): Curate lightweight top-level exports / lazy access; verify `import scrollkit` does not eagerly pull in heavy submodules
13. **Contract tests pass** [P]: Run contract tests; all must be GREEN
14. **Migrate existing tests** (2 tasks): Move SLDK + ScrollKit unit tests to test/unit/; update imports
15. **Memory baseline gate** (1 task): Write a device/sim script that runs `gc.collect()` + records `gc.mem_free()` after `import scrollkit` and after full init; commit the baseline; this is the FR-046 acceptance gate
16. **Demos** (3+ tasks): `demos/easy/` (scrolling text, no network), `demos/medium/` (open-meteo temperature scrolled with periodic refresh), `demos/hard/` (full app: web config + priority queue + effects + multiple public data sources + OTA + the chunked-fetch workaround that keeps the scroll alive during blocking HTTP). All run on the simulated scrolling hardware
17. **Documentation** (5 tasks): mkdocs.yml, module docs pages, easy/medium/hard tutorials, API reference
18. **Retire SLDK** (1 task): Remove sldk/ directory after all tests pass
19. **Full test suite** (1 task): Run test-all; fix any remaining failures
20. **Smoke test on hardware** (1 task): make copy_to_circuitpy; confirm boot + display + memory baseline
21. **Deferred polish (P2 — last)** (3 tasks): `.mpy`/`mpy-cross` build pipeline + circup docs; optional PCF font evaluation (preserve BDF parity); document OTA pre/post-script trust model

**Estimated Output**: 35-40 numbered tasks in tasks.md  
**[P]** = can be executed in parallel (no inter-task file dependencies)  
**Note**: ThemeParkWaits compatibility is intentionally absent — porting it is out of scope (see spec Out of Scope).

**IMPORTANT**: This phase is executed by the /tasks command, NOT by /plan.

---

## Complexity Tracking

*No violations to document. The merged package consolidates two frameworks — no new abstractions added.*

---

## Progress Tracking

**Phase Status**:
- [x] Phase 0: Research complete (/plan command)
- [x] Phase 1: Design complete (/plan command)
- [x] Phase 2: Task planning approach described (/plan command)
- [ ] Phase 3: Tasks generated (/tasks command)
- [ ] Phase 4: Implementation complete
- [ ] Phase 5: Validation passed

**Gate Status**:
- [x] Initial Constitution Check: PASS
- [x] Post-Design Constitution Check: PASS
- [x] All NEEDS CLARIFICATION resolved
- [x] Complexity deviations documented (none needed)

---
*Based on Constitution v2.1.1 - See `/memory/constitution.md`*
