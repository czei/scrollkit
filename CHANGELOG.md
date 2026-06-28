# Changelog

All notable changes to ScrollKit are recorded here. This project loosely follows
[Keep a Changelog](https://keepachangelog.com/).

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
