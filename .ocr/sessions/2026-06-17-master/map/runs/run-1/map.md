# Code Review Map: ThemeParkWaits ScrollKit Library Integration

## Executive Summary
This changeset makes ThemeParkWaits properly use the ScrollKit Library. The core change is refactoring `UnifiedDisplay` to extend `GenericDisplay` from `scrollkit.display.generic_display` instead of duplicating all hardware/SLDK initialization logic. This eliminates ~600 lines of duplicated code and ensures the app uses the library's abstractions.

## Sections

### Section 1: ScrollKit GenericDisplay (library foundation)
Files in this section establish the generic display layer.
- [ ] `src/scrollkit/display/generic_display.py` - Fixed font paths (3 levels up)
- [ ] `src/scrollkit/display/display_factory.py` - Now creates UnifiedDisplay (GenericDisplay subclass)

**Flow context:** Upstream: used by all display implementations. Downstream: UnifiedDisplay extends this.

### Section 2: ThemePark Waits Display (application layer)
Files that extend ScrollKit with theme-park-specific content.
- [ ] `src/ui/unified_display.py` - Now extends GenericDisplay, removes 600+ duplicated lines

**Flow context:** Inherits hardware/SLDK init from GenericDisplay. Adds ride methods.

### Section 3: SLDK Library Improvements
- [ ] `sldk/src/sldk/exceptions.py` - 12 exception classes (NEW)
- [ ] `sldk/src/sldk/**/*.py` - Type hints on all 36 modules
- [ ] `sldk/test/integration/` - 60 integration tests (NEW)

## File Index
- `sldk/src/sldk/exceptions.py` - New exception hierarchy
- `sldk/src/sldk/display/*.py` - Type hints + exception imports
- `sldk/src/sldk/effects/*.py` - Type hints + exception imports
- `sldk/src/sldk/web/*.py` - Type hints + exception imports
- `sldk/src/sldk/ota/*.py` - Type hints + exception imports
- `sldk/src/sldk/tools/*.py` - Type hints + exception imports
- `sldk/test/integration/` - Integration test suite
- `src/scrollkit/display/generic_display.py` - Font path fixes
- `src/scrollkit/display/display_factory.py` - GenericDisplay path
- `src/ui/unified_display.py` - Extends GenericDisplay
