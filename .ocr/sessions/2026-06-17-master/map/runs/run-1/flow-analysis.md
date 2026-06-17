# Flow Analysis: ScrollKit Library Integration

## Dependency Flow
1. **SLDK Simulator** (sldk/) → **Type hints + exceptions** → Library consumers
2. **ScrollKit Library** (src/scrollkit/) → **GenericDisplay** → ThemePark Display
3. **GenericDisplay** → SLDK desktop simulator OR CircuitPython hardware
4. **UnifiedDisplay** → extends GenericDisplay → adds ride-specific methods
5. **ThemeParkApp** → uses UnifiedDisplay via display_factory

## Key Design Decisions
- Display initialization moved from UnifiedDisplay to GenericDisplay (DRY)
- Font paths fixed to correctly resolve sldk font directory
- Factory now prefers GenericDisplay-based UnifiedDisplay
- SLDK simulator path properly tracked (3 levels up from scrollkit/display/)

## Upstream Dependencies
- `unified_display.py` → `GenericDisplay` → SLDK simulator / CircuitPython hardware
- `MessageQueue` → display methods (show_scroll_message, etc.)
- `ThemeParkApp` → `MessageQueue` + `GenericDisplay` primitives
