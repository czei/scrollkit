# Changelog

All notable changes to ScrollKit are recorded here. This project loosely follows
[Keep a Changelog](https://keepachangelog.com/).

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
