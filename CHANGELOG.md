# Changelog

All notable changes to ScrollKit are recorded here. This project loosely follows
[Keep a Changelog](https://keepachangelog.com/).

## [Unreleased]

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

### Changed

- Transition names now have a single source of truth
  (`scrollkit.config.transition_names.TRANSITION_NAMES`), kept in lockstep with the
  dispatch factory in `scrollkit.effects.transitions` by a unit test. Selecting a
  transition can no longer silently fall back to no transition, and an unknown
  saved `transition_style` is now logged instead of silently ignored.

### Added

- `scrollkit.dev.capabilities()` now catalogs the built-in transitions and their
  per-frame feasibility budgets (and renders them in `as_text()`), so AI agents and
  contributors can discover what's available and its modeled cost.
