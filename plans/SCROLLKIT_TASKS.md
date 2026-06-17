# ScrollKit Separation Tasks

## Phase 1: Create Generic ScrollKit Library — ✅ COMPLETE

- [x] Package structure with 25 files in `src/scrollkit/`
- [x] All utilities, config, network, OTA, display, animations moved
- [x] GenericDisplay with SLDK lazy-loading
- [x] Generic MessageQueue
- [x] Generic HttpClient with pluggable mock_provider
- [x] Generic SettingsManager with set_defaults() / add_bool_keys()
- [x] All cross-refs use `scrollkit.*` prefix

## Phase 2: Refactor Theme Park Waits to Use ScrollKit — ✅ COMPLETE

- [x] app.py, main.py, all src/ui/, src/network/, src/models/, src/api/ files updated
- [x] Bridge module (themeparkwaits.py) updated for CircuitPython path
- [x] Legacy files archived

## Phase 3: Packaging and Distribution

- [x] pyproject.toml created for ScrollKit
- [x] Deployment verified (rsync/makefile already covers scrollkit/)
- [ ] ScrollKit README and examples (nice-to-have)

## Phase 4: Verification — ✅ COMPLETE

- [x] Unit tests: 142 passed, 10 skipped, 7 pre-existing failures (zero regressions)
- [x] No stale `src.*` imports remaining
- [ ] Hardware deployment test (requires physical device)
- [ ] Dev mode simulator test (requires pygame)
