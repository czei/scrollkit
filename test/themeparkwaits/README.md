# ThemeParkWaits tests (separate project)

These are the unit tests for the **ThemeParkWaits application** — a DIY project
built *on top of* the ScrollKit library, not part of the library itself.

They were moved here out of `test/unit/` (the library's test suite) because:

- ThemeParkWaits is a separate project and belongs in its own git repository.
- After the SLDK→scrollkit merge, these tests reference retired pre-merge modules
  (`scrollkit.display.message_queue`, `scrollkit.ota.ota_updater`, the old
  `GenericDisplay`, etc.), so they do **not** pass against the merged library.
  Porting ThemeParkWaits onto the merged library is a separate effort.

They are intentionally **not** in `pytest.ini`'s `testpaths`, so `make test-unit`
runs only the library suite. When ThemeParkWaits is extracted to its own repo,
these move with it (alongside `src/app.py`, `src/main.py`, `src/themeparkwaits.py`,
`src/models/`, `src/api/`, `src/ui/`).

Contents: `models/`, `ui/`, `api/`, `ota/` (the retired GitHub-releases OTA test).
