# Changelog

All notable changes to ScrollKit are recorded here. This project loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## [0.9.2] - 2026-07-16

Field-resilience APIs from two days of on-hardware incident work (ESP32-S3,
CircuitPython 10.2.1, a two-node mesh network; the full falsification trail
lives in the ThemeParkWaits repo's docs/ota-check-failure-ledger.md).

### Changed
- **The hardware watchdog now arms even when a USB serial console is
  attached.** The old guard silently skipped arming whenever a host held the
  CDC port open, so a board living next to a computer ran with NO watchdog at
  all. Boards that were silently unprotected become protected on upgrade:
  size `watchdog_timeout` ABOVE your longest legitimate event-loop block
  (e.g. a synchronous HTTP call inside a web handler) or the board will
  reset-loop. Opt out for interactive debugging by creating a `/no_watchdog`
  file on the device (do it BEFORE rebooting into the debug session).
  `ScrollKitApp.watchdog_state` reports the arming outcome.
- The display loop stops feeding the watchdog after
  `MAX_CONSECUTIVE_RENDER_ERRORS` (10) consecutive render errors, so a
  permanently-broken render path hardware-resets instead of sitting frozen
  behind a fed watchdog; one successful frame resumes feeding.
- Every deliberate reboot in the library — OTA apply, the auto-reboot
  watchdog, `WiFiManager.reset()` — is now a COLD reset (radio disabled
  first): a reset issued while the station is associated degrades the next
  session until new outbound connects fail `OSError: 16` while pooled
  keep-alive flows still work.

### Added
- `OTAClient(check_url=...)` (also on `for_github`): point the frequent
  update CHECK at a ~6-byte `version.txt` on a host you control. With it set
  a check never handshakes with `server_url` — useful when the download host
  serves an RSA-2048 chain whose mbedTLS verification needs more internal
  SRAM than a running app has free (`-0x3F80 PK_ALLOC_FAILED`); the manifest
  fetch defers to download time, which can run at early boot with maximal
  headroom.
- `WiFiManager.bounce()` / `bounce_sync()`: forced radio restart + fresh
  association that acts even while the link LOOKS up. Complete every bounce
  with `HttpClient.rebuild_session()` (below) — reassociation alone leaves
  the session's stale socket plumbing failing.
- `HttpClient.rebuild_session()`: public full session rebuild (fresh
  SocketPool + ssl context + Session).
- `scrollkit.utils.system_utils.cold_reset()`: radio-off-then-reset, for app
  code that reboots deliberately.
- `ScrollKitApp.watchdog_state` and `ScrollKitApp.frames_rendered`
  diagnostics attributes (surface them in your status page: a frozen frame
  counter means the display loop died; an advancing counter with a dark
  panel means the output path died below Python).

### Fixed
- OTA: installing `X.mpy` now removes a stale `X.py` sibling (a device
  USB-deployed as source then OTA-updated to compiled accumulated both
  generations interleaved).
- `bounce_sync()` keeps `WiFiManager.is_connected` truthful.

## [0.9.1] - 2026-07-15

First-run developer experience, from a clean-room audit of what
`pip install "scrollkit[simulator]"` actually delivers to a new user.

### Fixed
- Simulator `displayio.FourWire(reset=...)` no longer overwrites its callable
  `reset()` method with the reset pin.
- `StaticText`/`ScrollingText` now accept `(r, g, b)` tuple colors — previously
  a tuple silently rendered the wrong color (the docs' own
  `color=(0, 255, 128)` example drew blue instead of green).
- The `[web]` extra now installs `adafruit-circuitpython-httpserver` — the
  dependency `SettingsWebServer` actually imports — instead of `aiohttp`,
  which nothing in the library uses. `pip install "scrollkit[web]"` gives a
  working browser settings UI on desktop.
- The README / docs Quick Start now opens the simulator window
  (`create_display()` → `SimulatorDisplay`); the previous snippet ran headless
  and invisible on desktop. Dropped the leftover `sys.path.insert(0, "src")`
  repo-ism from the getting-started example.

### Changed
- Quieter, friendlier desktop startup: a missing `adafruit_httpserver` prints
  one actionable line instead of a stack of failures; the meaningless desktop
  "Free memory: 100000 bytes" placeholder is no longer printed (real device
  and hardware-sim numbers still are); "Starting SLDK application" is now
  "Starting ScrollKit application"; and importing the library on desktop no
  longer creates an empty `error_log` in the working directory (the file
  appears on first actual write).

### Added
- Focused simulator primitive, URL utility, and MP4 recording tests, including
  a real ffmpeg/ffprobe H.264 smoke check.
- A non-writing MatrixPortal S3 raw-REPL smoke probe (`make test-device-s3
  PORT=...`) for deployed-library, panel, painter, text, refresh, and memory
  validation.
- CI changed-line coverage on pull requests plus clean-wheel and media-encode
  smoke jobs, so package data and MP4 support are verified before release.

## [0.9.0] - 2026-07-14

The DarkOwl promotion: the effect mechanisms invented for the DarkOwl LED
logo sign — a 24/7 show on a MatrixPortal S3 — generalized into the library.
The headline is palette-partition animation: bake a mark's pixels into an
indexed layer once, then animate purely with palette writes.

### Added
- `effects/palette_partition.py`: `PalettePartition` (indexed layer with
  reserved identity slots) plus ten partition builders (diagonal, anchor
  distance, radial, angular, rain phase, checker, exposure, Voronoi regions,
  stroke topology, BFS route) and `bfs_paths`.
- `effects/palette_treatments.py`: thirteen frame-driven dwell treatments
  (VelvetSweep, AnchorWake, HaloPulse, SonarSweep, CipherRain, InkShimmer,
  RimLight, HeatmapDrift, EclipseCross, GradientDwell, StrokeAnatomy,
  RouteCircuit, PacketTrace) with a 5-stop theme contract, caller-owned
  blink beats (`blink_now`), `TREATMENT_CLASSES` + `treatments_for()`.
- `effects/swirl_in.py`: `SwirlIn` — sprites spiral in around a center onto
  exact target positions (deliberately NOT a named Transition: it needs a
  per-sprite target list).
- `SwarmReveal` true-color and reverse modes: `index_map=` / `pixel_colors=`
  paint an arbitrary source image's exact colors; `reverse=True` pre-lights
  the image and the flock carries it away pixel by pixel.
- `utils/scheduler.py`: `ActScheduler` — weighted-age, family-aware deck
  picking for 24/7 variety (least-recently-seen leads, no family repeats,
  `force=` for openers).
- Visual Reference: a `treatments` gallery category with a sample for every
  treatment class (coverage-gated); `capabilities()` gains a
  `palette_treatments` section.

## [0.8.5] - 2026-07-13

A hardening release forged by a fielded MatrixPortal S3: three of these fixes
were found because a real device failed in the field, not because a test went
red. Detailed post-mortem in the ThemeParkWaits app repo
(`docs/ota-check-failure-ledger.md`).

### Fixed
- `RegionRotateAnimator` now works on real hardware: `math.hypot` does not
  exist on CircuitPython (start() raised, hosts silently fell back to a still
  image), and the erase-everything-then-redraw restamp flickered against the
  panel's continuous refresh — restamps are now pose diffs, byte-identical to
  the old poses.
- OTA client streams manifest and file bodies to flash in small chunks instead
  of `response.json()` / `response.content` — a ~31 KB body needed one
  contiguous allocation that a hot heap often cannot provide (intermittent
  `MemoryError` on update checks).
- `HttpClient._rebuild_session` closes the old pool's sockets before building
  the replacement (new public `close_pooled_sockets()`). Dropping the pool to
  the GC orphaned its native mbedtls TLS contexts (~40 KB of ESP32-S3 internal
  SRAM each); with a rebuild threshold of 2, multi-day uptime starved every
  TLS handshake (`PK_ALLOC_FAILED` / `MemoryError` / `Out of sockets`).
- Update checks use a dedicated 8 s `check_timeout` (downloads keep 30 s): the
  check runs inside a synchronous handler that freezes the display for its
  duration, so one stalled read must not cost 30 frozen seconds.
- OTA takeover messages ("Updating — DO NOT UNPLUG") blank the screen properly:
  new `GraphicsMixin.clear_layers()` strips persistent bitmap layers that
  `clear()` deliberately leaves alone (the message used to paint on top of the
  interrupted content), resetting the bounded painter so it self-heals.

### Added
- ~6-byte update checks: `check_for_updates` reads the channel's `version.txt`
  first and answers "up to date" without fetching the manifest (strict
  MAJOR.MINOR[.PATCH] validation so an error page can never fake the answer;
  404 falls back to the manifest for older channels). Publishers ship
  `version.txt` beside `manifest.json`.
- `WiFiManager(ap_name=...)`: apps brand the onboarding portal's access point
  (e.g. `ThemeParkWaits-XXXX`); the library owns only the MAC-derived
  uniqueness tail and never hardwires a product name.
- Interstate 75 W bring-up: named-matrix-pin fallback coverage, a host-side
  smoke probe, and `--port`-aware device calibration/benchmark tooling.
- CircuitPython math-surface guard test: device-path code is statically checked
  against the REAL board's `math` module (no `hypot`, `tau`, `inf`, `nan`,
  `isclose`, `log2`, `log10`, ...), the same trap class as `random.shuffle`.
- Cel-walk demo: nodding head.

### Docs
- New OTA guide section: shipping the library as `.mpy` — pinned
  CircuitPython-matched mpy-cross (the PyPI `mpy-cross` package is
  MicroPython's compiler and boards reject its bytecode), `-s` for
  deterministic builds, the free-space rule, and the updater's
  no-deletion-by-omission semantics.
- Corrected the `pip install mpy-cross` guidance in getting-started and the
  makefile.

## [0.8.4] - 2026-07-08

### Added
- `scrollkit.effects.image_animators` — twelve per-frame animators that decorate a
  static image layer already on screen (twinkle, tile motion, particle emitter,
  palette pulse, region shift with sine/ramp/ripple/hinge waves, orbiter, blink,
  sprite lift with automatic scene inpainting, cover, vanish, pre-baked frame
  cycling, and combos). Extracted up from the ThemeParkWaits app's ride-intro
  engine; start/step/detach contract, FEASIBILITY dicts on every class, and an
  ordered `ANIMATOR_CLASSES` catalog.
- `RegionRotateAnimator` — the thirteenth image animator: tilts the lit pixels
  inside a box about a pivot *point*, oscillating, for a real rotation (a nodding
  head, a waving arm, a see-sawing plank) rather than `RegionShift`'s upright
  `hinge` shear. Hole-free by inverse-mapping every destination pixel; an `exclude`
  box freezes the attached body it rotates on (no seam tears); cost-guarded
  (refuses >320 lit px or a >1600-cell scan box and falls back), and settles the
  region upright on `detach()`.
- `CelWalkAnimator` — a multi-pose cel walk-cycle primitive: plays an authored
  walk-cycle spritesheet (a sibling `<image>_walk.bmp` of N panel-sized tiles) via a
  tile-indexed `TileGrid` while translating the sprite across the panel, so the legs
  are genuinely different authored drawings frame to frame and the gait reads as real
  stepping. Pose change is a single tile write and travel is a `tile.x` write: no
  per-frame allocation, no layer churn.
- OTA **delta apply** — a device can consume a large combined manifest (app plus a
  bundled library under `/lib/scrollkit`) on thin free space: it hashes its live tree
  and downloads/backs up/installs only the files whose sha256 differs, sizing the
  free-space guard to the delta (`2*delta+50KB`) rather than the whole manifest. The
  full manifest is still verified after apply; a `created_paths` marker deletes
  newly-created files on rollback so an interrupted apply leaves no orphans; plus a
  device-side path-safety allowlist. Verified on hardware.
- `image_animators.read_indexed_bmp()` — decode an 8-bit indexed BMP straight into a
  writable `Bitmap`. On-device `OnDiskBitmap` is not subscriptable, so animators that
  read/rewrite image pixels need this; the demo and reference generator use it as the
  device-correct loader (`OnDiskBitmap` for the palette + `read_indexed_bmp` for pixels).
- Docs: an animated GIF for every image animator, in the **Effects** guide and the
  **Visual Reference** gallery, generated by `demos/render_reference.py` (a new
  `animators` route driven from the live `ANIMATOR_CLASSES`, guarded by
  `test_reference_coverage.py` so a new animator can't ship without a sample).
- `demos/medium/image_intro.py` — a runnable demo showing image animators in context:
  an animated image intro (twinkle / traverse / rocket-liftoff combo) handing off to a
  data screen, illustrating the self-driving display loop vs. the content queue. Added
  to the Demo Gallery.
- `capabilities()` gains a distinct `image_animators` category (its own key, not folded
  into `effects`) enumerated from `ANIMATOR_CLASSES`, with each class's FEASIBILITY
  budget; surfaced in `as_text()` and documented in `AGENTS.md`.

### Fixed
- The extracted twinkle animator now shuffles candidate pixels with a hand-rolled
  Fisher-Yates: the app original used `random.shuffle`, which does not exist on
  CircuitPython — on hardware those animations silently fell back to a still image.
- Composed animators clean up already-started parts when a later part fails to
  start (previously the survivors' overlay layers leaked on the display).
- **OTA now surfaces real failure reasons instead of "up to date."** A failed check,
  download, or apply was reported to the app as "device is current," so an invalid
  published manifest could hide a fleet-wide outage behind a lie. `OTAProgressDisplay`
  records every outcome in `last_error` (cleared only after a successful stage); only
  the genuine `UP_TO_DATE` sentinel reads as "current," and an apply failure now paints
  an "Update / failed" frame on the panel instead of rebooting.
- **OTA apply is now a crash-safe transaction, with real-CircuitPython fixes** found
  live on a MatrixPortal S3: route checksums through `hashlib.new()` (no `sha256()` on
  device), drop `json.dumps(indent=…)` and the `IOError` name (neither exists on
  device), and replace `os.walk`/`os.makedirs` with `listdir`/`mkdir` helpers. Apply
  writes `APPLY_STARTED`/`BACKUP_COMPLETE` markers, backs up once per transaction,
  re-verifies each installed file, writes the `.version` commit marker last, and rolls
  back staging on failure so a bad payload can't reboot-loop. Manifest validation now
  rejects an unparseable version loudly and drops the unused mandatory `required` key
  that had rejected every published manifest.
- The WiFi setup portal now boots on-device and re-scrolls its instructions:
  `import socket` moved into the desktop-only branch (CircuitPython has no stdlib
  `socket`, so the eager import crashed the portal), and the one-line status panel
  restarts its scroll so the AP name, password, and URL can all be read.

## [0.8.3] - 2026-07-02

The post-0.8.2 review fixes (a 4-agent + 3-model-panel code review, then five
fix tranches) plus the restored WiFi onboarding feature. Note that some fixes
change behavior code may have relied on (`ContentQueue` priority/loop are now
real contracts, the OTA manifest script hooks are gone). First release
published to PyPI: a tag push now builds and uploads via GitHub Actions
Trusted Publishing (`.github/workflows/publish.yml`), and the wheel/sdist now
declare the simulator's BDF fonts and hardware-calibration JSONs as package
data (previously only reachable via editable/source installs).

### Added

- **WiFi onboarding portal restored** — configure Wi-Fi from a phone, no file
  editing (`scrollkit.web.wifi_setup.WiFiSetupPortal`, entry point
  `WiFiManager.run_setup_portal(display=...)`). The device starts its own
  access point, scrolls join instructions on the panel, serves a setup page
  (scanned networks with signal bars + manual SSID + password) at
  `http://192.168.4.1`, saves through the `SettingsManager` into
  `settings.json`, and reboots to connect. The original feature had been
  silently unwired since the settings-server rewrite and was then deleted as
  dead code; this is a redesign, not a revert. `start_access_point` /
  `stop_access_point` / `ap_ip_address` are back on `WiFiManager`.
  *Needs hardware verification (AP mode on a real board).*
- WiFi credentials now resolve **settings-first**: portal-saved
  `wifi_ssid`/`wifi_password` in `settings.json` beat a stale `secrets.py`.
- Recording (`start_recording`/`save_gif`/`save_video`), `screenshot()`, and
  the `hardware_timing`/`throttle`/`strict` feasibility flags are now on
  `UnifiedDisplay` (no-ops returning `None` on hardware) — no need to bypass
  the auto-detecting display to record or gate.
- `ContentQueue` honors the documented contracts it previously ignored:
  `priority` (higher plays first, stable within equal priority) and
  `loop=False` (queue exhausts after the last item; `add()` re-arms it).

### Fixed

- **Interstate 75 W was unusable by construction**: `UnifiedDisplay` reached
  the displayio display via `self.hardware.display`, which only exists on the
  S3's Matrix wrapper — every frame raised a swallowed `AttributeError` and
  the panel never refreshed. All paths now use `self.display`.
- **Corrupt `settings.json` no longer bricks boot**: CircuitPython raises
  `ValueError` for bad JSON; `load_settings` caught only `OSError`.
- **`set_pixel`/`fill` now work on hardware and on desktop `UnifiedDisplay`**
  (previously the particle system rendered only on `SimulatorDisplay`): both
  render through the paint-canvas displayio layer, survive refresh, and are
  feasibility-accounted.
- **`run_headless(strict=True)` now exercises transitions**: the harness
  drives the app's own `step_frame()` (new, shared with `_display_process`)
  instead of a hand-copied loop that skipped the transition path.
- `RainDrop`/`Snow` no longer hardcode a 32-px panel height; wrong
  `pip install sldk[simulator]` hints corrected to `scrollkit[simulator]`;
  urllib POST records success for `last_error` bookkeeping; `run_headless`
  restores `SDL_VIDEODRIVER` so later live-window runs aren't silently
  headless.

### Removed / Security

- **OTA manifest scripts**: `OTAClient.apply_update` `exec()`'d
  `pre/post_update_scripts` from the downloaded manifest — unsigned remote
  code execution that no publisher ever used. The whole surface is gone;
  legacy manifests carrying the (empty) keys still parse.
- `SimulatorDisplay` is now a thin subclass of `UnifiedDisplay` — one
  per-frame pipeline for hardware and simulator (its private
  `_overlay_pixels` mechanism and duplicated render loop are gone).
- Zero-reference orphans: `simulator.adafruit_display_text.scrolling_label`,
  `simulator.core.display_manager` (+ `BaseDevice.run`/`run_once`),
  `WiFiManager.disconnect`/`is_available`/`get_ip_address`, all `ColorUtils`
  static helpers, and `UpdateManifest`'s unused builder half.

## [0.8.2] - 2026-07-01

A pre-1.0 legacy-cleanup release: remove dead code and trap APIs, fix real bugs,
and lock down the public surface before a 1.0 freeze. Contains breaking removals
(pre-1.0 semver permits them); the one downstream app (ThemeParkWaits) is
migrated in lockstep.

### Removed

- The entire dead pre-consolidation display pipeline: `scrollkit.content_classes`,
  the top-level `scrollkit.content` shim, `scrollkit.display.strategy` (its
  `DisplayStrategy`/`StrategyRegistry`/`DisplayItem`/`*Strategy` classes),
  `scrollkit.display.queue` (`DisplayQueue`), and `scrollkit.display.manager`
  (`DisplayManager`). These had zero production consumers; `content_classes`'
  `create_*`/`example_usage()` were a *trap* (they built `DisplayItem`s the live
  `ContentQueue` never consumed). **`Priority` survives, relocated to
  `scrollkit.display.content`.**
- `scrollkit.app.minimal` (`MinimalLEDApp`) — disjoint from `ScrollKitApp`,
  nothing built on it, and its desktop fallback was broken.
- `scrollkit.ota.updater` (`OTAUpdater`) and `scrollkit.ota.server` (`OTAServer`)
  — unused duplicates of `ota.client` / `ota.publish`.
- Zero-importer orphans: `scrollkit.utils.timer`, `scrollkit.utils.image_processor`,
  `scrollkit.simulator.devices.generic_matrix`,
  `scrollkit.simulator.adafruit_display_text.bitmap_label`,
  `scrollkit.simulator.terminalio.font_scaler`.
- `wifi_manager`'s unused captive-portal web server, `_save_to_secrets_file`, the
  no-op `update_http_clients`, and the unreachable (shadowed) `is_connected()`
  method.
- `DisplayInterface.scroll_text` / `SimulatorDisplay.scroll_text` — no callers;
  silently no-op'd on hardware.
- Nine caught-but-never-raised / dead exception classes (see below).

### Changed / Renamed

- `scrollkit.display.gradient_text._GradientTextLayer` → public `GradientTextLayer`
  (old name kept as an alias through 0.9.x).
- Exception base `SLDKError` → `ScrollKitError` (old name kept as an alias). The
  hierarchy is collapsed to only what the library raises: `ScrollKitError`,
  `NetworkError`, `OTAError`, `FeasibilityError`. `DisplayError`, `ContentError`,
  `ConfigurationError`, `WebServerError`, `DeploymentError`, `SimulatorError`,
  `ResourceNotFoundError`, `UpdateError`, `ValidationError` are removed.
- `HttpClient.get` / `get_sync` / `post` now **raise `NetworkError`** when every
  retry fails, instead of returning a synthesized `500` response.
  `HttpClient.last_error` retains the raw underlying cause. `OTAClient` raises
  `NetworkError`/`OTAError` internally but preserves its public `(ok, reason)`
  tuple contract.
- `scrollkit.dev.performance.as_text` → `performance_text` (removes a name
  collision with `dev.capabilities.as_text`).
- `MinimalLEDApp.COLORS` → `scrollkit.utils.color_utils.NAMED_COLORS`.
- `scrollkit.effects` is now import-free: import each effect from its submodule
  (`effects.transitions`, `effects.reveal_splash`, `effects.particles`, …) — a
  no-splash app no longer loads the particle/splash modules just to use a
  transition. No plugin/registry was added.

### Fixed

- The settings web server no longer mutates display/queue state from the request
  handler; it sets a flag the display loop applies via the new
  `ScrollKitApp.notify_settings_changed()`.
- `HttpClient` platform detection imported a retired module
  (`display.display_factory.is_dev_mode`), silently always falling back to
  production mode; it now uses `network.wifi_manager.is_dev_mode`.
- Import-time side effects removed: `config.settings_manager`,
  `network.http_client`, and `network.wifi_manager` no longer construct an
  `ErrorHandler` (which write-tests the filesystem) merely on import.
- Two banned `json.JSONDecodeError` uses in `ota.client` / `ota.manifest` (would
  raise `AttributeError` on CircuitPython) → `ValueError`.

### Internal

- `__all__` added to every public module; a new `test/unit/docs/` gate executes
  every `import` shown in the README/docs so advertised APIs can't drift.
- Simulator device setup shared between `UnifiedDisplay` and `SimulatorDisplay`
  via `display/_sim_backend.py`.
- Device deploy (`make copy-to-circuitpy` / `make mpy`) now excludes the
  desktop-only `dev/` and `simulator/` trees and the host-only `ota/publish.py`.

### Migration

| Old | New |
|-----|-----|
| `from scrollkit.app.minimal import MinimalLEDApp` | `from scrollkit.app.base import ScrollKitApp` |
| `from scrollkit.content import ...` | `from scrollkit.display.content import ...` |
| `from scrollkit.display.strategy import Priority` | `from scrollkit.display.content import Priority` |
| `from scrollkit.display.queue import DisplayQueue` | `from scrollkit.display.content import ContentQueue` |
| `from scrollkit.display.gradient_text import _GradientTextLayer` | `... import GradientTextLayer` |
| `from scrollkit.effects import SwarmReveal` | `from scrollkit.effects.swarm_reveal import SwarmReveal` |
| `from scrollkit.exceptions import SLDKError` | `... import ScrollKitError` (alias still works) |
| `resp = await client.get(url)` then check `resp.status_code == 500` | `try: resp = await client.get(url)` / `except NetworkError:` |

## [0.8.1] - 2026-06-28

### Added

#### Reusable infrastructure (extracted up from ThemeParkWaits)

These were app-local; they are generic enough that every ScrollKit app should get
them for free. All are additive — defaults preserve prior behaviour.

- `scrollkit.utils.diagnostics` — NVM-backed boot/crash diagnostics with a
  reboot-loop safe-mode breaker. `diagnostics.open()` binds to `microcontroller.nvm`
  on device and returns a no-op store on desktop (no platform check needed); the
  store takes an injectable backend so the boot-loop logic is unit-tested with a
  plain `bytearray`.
- `scrollkit.network.mdns.advertise(hostname, *, port=80, service_type, protocol)`
  — non-blocking `<hostname>.local` advertising. Returns the `mdns.Server` (the
  caller MUST retain it — GC stops resolution) or `None` on desktop / no radio;
  never raises.
- `scrollkit.ota.display_progress.OTAProgressDisplay` — a display-progress +
  staged-install adapter around an existing `OTAClient` (renders the
  "Installing… DO NOT UNPLUG!" frame, applies, reboots). The client stays headless;
  the update source/channel remains the app's concern.
- `ScrollKitApp.suspend_render()` / `resume_render()` / `suspended_render()` context
  manager + `render_suspended` property — pause queue rendering (queue preserved)
  while painting an off-queue status frame and blocking on a fetch, without
  overriding `prepare_display_content()`. Default: not suspended.
- `BitmapText(complete_after_passes=N)` — frame-based one-pass completion so a
  scrolling banner can advance a `ContentQueue` without subclassing. Keyed on scroll
  POSITION, not wall-clock, so a low frame rate never cuts the text off mid-scroll;
  `start()` now rebuilds the layer so a banner is queue-safe when it cycles back.
  Default `None` keeps the persistent-banner behaviour.

## [0.8.0] - 2026-06-28

First public release: an LED-matrix display framework that runs unchanged on the
Adafruit MatrixPortal S3 (CircuitPython 8.x/9.x/10.x) and a desktop pygame simulator.

### Added

- Opt-in hardware watchdog on `ScrollKitApp` (`enable_watchdog`, `watchdog_timeout`,
  default 8s) that resets the board if the display loop wedges — e.g. a hung
  synchronous fetch — and self-recovers instead of sitting frozen until a power
  cycle. Hardware-validated on CP 9.2.7 and 10.2.1 (`test/claude/RELIABILITY_TESTING.md`).
- Data-refresh memory floor `MIN_FREE_FOR_UPDATE` (default 25000) with a
  force-after-N-skips guard, so a low-memory device can't serve stale data forever.
- `scrollkit.dev.capabilities()` now catalogs the built-in transitions and their
  per-frame feasibility budgets (and renders them in `as_text()`), so AI agents and
  contributors can discover what's available and its modeled cost.

### Changed

- Transition names now have a single source of truth
  (`scrollkit.config.transition_names.TRANSITION_NAMES`), kept in lockstep with the
  dispatch factory in `scrollkit.effects.transitions` by a unit test. Selecting a
  transition can no longer silently fall back to no transition, and an unknown saved
  `transition_style` is now logged instead of silently ignored.
- Field reliability: `HttpClient` default per-request `timeout` 10s → 6s (kept below
  the watchdog window); `ErrorHandler` no longer deletes or truncates the log on boot
  (crash evidence is preserved) and rotates with a tail-preserving trim instead of
  blanking it; PRODUCTION persists only errors to flash; `ErrorHandler` is now a real
  per-file singleton so a read-only-filesystem detection is shared across callers.

### Removed (breaking)

- **Effect-attachment API.** `DisplayItem.add_effect()` / `with_effect()`,
  `BaseContent.with_effect()` / `with_effects()`,
  `DisplayManager.add_item(..., effects=...)`, and the `DisplayQueue._apply_effects`
  render path have been removed. They drove the old `Effect.apply()` contract,
  which no longer exists — the surface was a no-op (and internally buggy), and a
  trap for AI-authored code. Visual variety now comes from the `Transition` system
  (the `transition_style` setting) and the standalone splash/particle helpers.
- The dead `Effect` / `EffectRegistry` / `CompositeEffect` base classes
  (`scrollkit.effects.base`), the `SimpleEffect` / `EffectsEngine` system and its
  concrete effects (`scrollkit.effects.effects`), and the orphaned
  `EnhancedDisplayContent` family (`scrollkit.display.enhanced_content`) — none were
  wired into the display loop, and the latter violated the library's own
  per-frame-allocation / no-per-pixel-loop feasibility rules.
