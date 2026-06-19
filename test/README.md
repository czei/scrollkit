# ScrollKit tests

The test suite for the ScrollKit library. Tests run headlessly against the
desktop pygame simulator (SDL dummy driver), so they need no display and no
hardware.

## Layout

- `unit/` — the test suite (run by CI), organized by area: `app/`, `display/`,
  `simulator/`, `dev/`, `network/`, `config/`, `content/`, `effects/`, `utils/`.
- `claude/` — host-side device tooling (not collected as tests): `cpy_repl.py`
  (CircuitPython raw-REPL driver), `calibrate_device.py` (captures the hardware
  timing/RAM baseline), and `device_benchmarks.py` (per-operation microbenchmarks).
- `helpers.py` — shared test utilities (`MockHardwareContext`, `with_temp_file`,
  `mock_network_response`).
- `conftest.py` — forces the headless SDL driver before pygame loads.
- `memory_baseline.py` — checks free RAM after `import scrollkit` (spec FR-046).

## Running

```bash
make test-unit                 # or: PYTHONSAFEPATH=1 PYTHONPATH=src python -m pytest test/unit
make lint-errors               # critical-error lint (run before deploying)
```

`PYTHONSAFEPATH=1 PYTHONPATH=src` is needed because the repo's package lives under
`src/` and `PYTHONSAFEPATH` keeps the CWD off `sys.path`.

## Writing tests

- Mirror the source layout under `test/unit/`.
- Drive the real loop headlessly via `scrollkit.dev.run_headless(app, frames=N)`
  and assert on the returned `RunResult` (see `test/unit/dev/`).
- Use `MockHardwareContext` from `helpers.py` when exercising code that touches
  CircuitPython-only hardware modules.
