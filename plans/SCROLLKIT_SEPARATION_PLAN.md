# ScrollKit Library Separation Plan — Task-Level Detail

## Inventory Summary

| Category | Count | Files |
|---|---|---|
| **Fully generic** (library-ready) | **21** | `display_interface.py`, `display_factory.py`, `roller_coaster_animation*.py`, `wifi_manager.py`, `server_adapters.py`, `async_http_request.py`, `http_response_patch.py`, `timer.py`, `error_handler.py`, `color_utils.py`, `system_utils.py`, `url_utils.py`, `image_processor.py`, `ota_updater.py`, all `__init__.py` files |
| **Partially generic** (needs refactoring) | **8** | `http_client.py`, `settings_manager.py`, `simulator_display.py`, `display_base.py`, `unified_web_server.py`, `main.py`, `vacation.py`, `http_client_original.py` |
| **Application-specific** (stays in Theme Park Waits) | **17** | `app.py`, `themeparkwaits.py`, `theme_park_service.py`, `theme_park.py`, `theme_park_ride.py`, `theme_park_list.py`, `unified_display.py`, `hardware_display.py`, `sldk_simulator_display.py`, `message_queue.py`, `reveal_animation.py`, `web_server.py`, `dev_web_server.py`, `web_server_core.py`, `ota.py` |

---

## Phase 1: Create Generic ScrollKit Library

### Task 1.1 — Set up the ScrollKit package structure
Create directory structure with proper `__init__.py` files:

```
ScrollKit/
  src/scrollkit/
    __init__.py
    display/
      __init__.py
    network/
      __init__.py
    config/
      __init__.py
    utils/
      __init__.py
    ota/
      __init__.py
```

### Task 1.2 — Move fully generic utility files (no changes needed)

Copy these as-is into `src/scrollkit/utils/`:

| Source | Target |
|---|---|
| `src/utils/error_handler.py` | `scrollkit/utils/error_handler.py` |
| `src/utils/color_utils.py` | `scrollkit/utils/color_utils.py` |
| `src/utils/timer.py` | `scrollkit/utils/timer.py` |
| `src/utils/system_utils.py` | `scrollkit/utils/system_utils.py` |
| `src/utils/url_utils.py` | `scrollkit/utils/url_utils.py` |
| `src/utils/image_processor.py` | `scrollkit/utils/image_processor.py` |

Fix their internal imports: change `from src.utils.error_handler import ...` to `from scrollkit.utils.error_handler import ...`.

---

### Task 1.3 — Create generic display interface and factory

**`scrollkit/display/display_interface.py`** — Move as-is, no changes needed. It defines a pure abstraction with no domain coupling.

**`scrollkit/display/display_factory.py`** — Move as-is, but update the internal imports:
- `from src.ui.unified_display import` → This points to the THEME-PARK-SPECIFIC unified display. Replace with a new `GenericDisplay` (created in Task 1.4).
- `from src.ui.sldk_simulator_display import` → Replace with `GenericSLDKDisplay`.
- `from src.ui.hardware_display import` → Replace with `GenericHardwareDisplay`.
- `from src.ui.simulator_display import` → Replace with `GenericSimulatorDisplay`.
- `from src.utils.error_handler import` → `from scrollkit.utils.error_handler import`.

---

### Task 1.4 — Create generic display implementations (THE KEY TASK)

This is the hardest part. The current `unified_display.py`, `hardware_display.py`, and `sldk_simulator_display.py` are all structurally identical — they differ only in their platform-specific initialization, but their **display content is hardcoded to Theme Park Waits** (splash screens with "THEME PARK WAITS", ride name/wait time groups, "queue-times.com" attribution, "Closed" labels, etc.).

**Create `scrollkit/display/generic_display.py`** that:
1. Provides the **platform detection and initialization logic** (CircuitPython vs SLDK simulator)
2. Provides **basic display primitives only**:
   - `show_scroll_message(text, color)` — scrolling text
   - `show_static_text(text, color, x, y, scale)` — static text at any position
   - `show_image(image, x, y)` — image display
   - `clear()` — clear all
   - `set_brightness(brightness)` — brightness
   - `set_rotation(rotation)` — rotation
3. Exposes a `create_label(text, x, y, scale, color)` method so applications can build their own display groups
4. Exposes a `create_group()` and `add_to_main_group(group)` method so applications can build their own layouts
5. Does NOT include any theme-park-specific groups, labels, or text

The application would then build its own display layout using these primitives (e.g., `ThemeParkDisplay` extends or wraps `GenericDisplay`).

---

### Task 1.5 — Move network infrastructure files (no changes needed)

| Source | Target |
|---|---|
| `src/network/wifi_manager.py` | `scrollkit/network/wifi_manager.py` |
| `src/network/server_adapters.py` | `scrollkit/network/server_adapters.py` |
| `src/network/async_http_request.py` | `scrollkit/network/async_http_request.py` |
| `src/network/http_response_patch.py` | `scrollkit/network/http_response_patch.py` |

Fix internal imports to use `scrollkit.utils.error_handler` and `scrollkit.config.settings_manager`.

---

### Task 1.6 — Refactor `http_client.py` to remove mock data

1. Move the core HTTP client class (response wrappers, retry logic, dual-implementation pattern) to `scrollkit/network/http_client.py`
2. **Extract the mock data** (lines 174-248 in current file) into a separate mechanism:
   - Create a `MockDataProvider` protocol/interface in the library
   - Let applications register mock data providers
   - The hardcoded Disney/Universal/SeaWorld park data stays in the Theme Park Waits application, registered as a mock provider
3. Remove the `is_dev_mode` import — make mock data opt-in rather than automatic

---

### Task 1.7 — Make `settings_manager.py` generic

1. Move the core class to `scrollkit/config/settings_manager.py`
2. **Remove all theme-park-specific defaults** (lines 31-56):
   - Remove `"domain_name": "themeparkwaits"`, `"display_mode": "all_rides"`, `"sort_mode": "alphabetical"`, `"group_by_park": False`, color defaults for rides, `"skip_closed"`, `"skip_meet"`, `"scroll_speed"`, `"subscription_status"`, `"email"`
3. Keep only the generic JSON persistence mechanism (`load_settings`, `save_settings`, `get`, `set`)
4. Add a `set_defaults(defaults_dict)` method so applications can register their own defaults
5. Remove the `ColorUtils` import dependency by making color defaults a string rather than a ColorUtils lookup

---

### Task 1.8 — Move OTA updater

Move `src/ota/ota_updater.py` to `scrollkit/ota/ota_updater.py`. Fix the import: `from src.utils.error_handler import` → `from scrollkit.utils.error_handler import`.

Do NOT move `src/ota/ota.py` — it's legacy MicroPython code.

---

### Task 1.9 — Move generic animations

| Source | Target |
|---|---|
| `src/ui/roller_coaster_animation.py` | `scrollkit/display/roller_coaster_animation.py` |
| `src/ui/roller_coaster_animation_cp.py` | `scrollkit/display/roller_coaster_animation_cp.py` |

These have zero domain coupling.

---

## Phase 2: Refactor Theme Park Waits to Use ScrollKit

### Task 2.1 — Create `ThemeParkDisplay` extending `GenericDisplay`

In `themeparkwaits/src/ui/theme_park_display.py`:
1. Import `GenericDisplay` from ScrollKit
2. Override/extend it to add all the theme-park-specific groups:
   - `splash_group` with "THEME PARK"/"WAITS" labels
   - `wait_time_name_group` / `wait_time_group` / `closed_group` for ride display
   - `update_group`, `required_group`, `centered_group`, `queue_group` for various messages
3. Add methods: `show_splash()`, `show_ride_name()`, `show_ride_wait_time()`, `show_ride_closed()`
4. This effectively replaces the current `unified_display.py` / `hardware_display.py` / `sldk_simulator_display.py` trio with a single class that inherits generic behavior and adds domain-specific content

### Task 2.2 — Create `ThemeParkMessageQueue` extending `GenericMessageQueue`

1. Create `scrollkit/display/message_queue.py` — a generic message queue that:
   - Queues functions with parameters and delays
   - Has `add_message(func, params, delay)`, `show()`, `init()` methods
   - Has cycle tracking (`has_completed_cycle`)
   - Has NO park/ride/vacation/attribution references

2. In `themeparkwaits/src/ui/theme_park_message_queue.py`:
   - Extend `GenericMessageQueue`
   - Add `add_rides()`, `add_vacation()`, `add_required_message()`, `add_splash()` (all domain-specific logic)
   - Keep the `REQUIRED_MESSAGE = "queue-times.com"` constant

### Task 2.3 — Clean up the app domain models

Keep in `themeparkwaits/src/models/` (no changes needed):

| File | Status |
|---|---|
| `theme_park.py` | Application domain model — stays |
| `theme_park_ride.py` | Application domain model — stays |
| `theme_park_list.py` | Application domain model — stays |
| `vacation.py` | Application domain model — stays |

### Task 2.4 — Clean up the API service

Keep in `themeparkwaits/src/api/`:
- `theme_park_service.py` — no changes needed, it's pure application logic

### Task 2.5 — Update `app.py` imports

Update `app.py` to import from the new ScrollKit package:
- `from src.config.settings_manager import` → `from scrollkit.config.settings_manager import`
- `from src.ui.message_queue import` → `from src.ui.theme_park_message_queue import` (new app-specific class)
- `from src.utils.error_handler import` → `from scrollkit.utils.error_handler import`
- `from src.utils.timer import` → `from scrollkit.utils.timer import`
- `from src.network.wifi_manager import` → `from scrollkit.network.wifi_manager import`
- `from src.ota.ota_updater import` → `from scrollkit.ota.ota_updater import`
- `from src.ui.display_factory import` → `from scrollkit.display.display_factory import`

### Task 2.6 — Update `main.py` imports

Same import updates as `app.py`, plus:
- Remove the `create_display` import — Theme Park Waits will now create its own display
- Import `ThemeParkDisplay` instead

### Task 2.7 — Keep the web servers as-is

Keep in `themeparkwaits/src/network/`:
- `web_server.py` — theme park configuration pages (no changes)
- `dev_web_server.py` — dev mode equivalent (no changes)
- `web_server_core.py` — shared HTML generation (no changes)

### Task 2.8 — Remove/archive replaced files

Files that become redundant after the separation:

| File | Disposition |
|---|---|
| `src/ui/unified_display.py` | Replaced by `GenericDisplay` + `ThemeParkDisplay` |
| `src/ui/hardware_display.py` | Replaced by `GenericDisplay` in library |
| `src/ui/sldk_simulator_display.py` | Replaced by `GenericDisplay` in library |
| `src/ui/message_queue.py` | Replaced by `GenericMessageQueue` + `ThemeParkMessageQueue` |
| `src/ui/display_base.py` | Legacy, superseded |
| `src/ui/simulator_display.py` | Replaced by `GenericSimulatorDisplay` in library |
| `src/network/http_client_original.py` | Legacy, archive or delete |
| `src/ota/ota.py` | Legacy MicroPython code, archive or delete |

### Task 2.9 — Update `themeparkwaits.py` bridge module

Update import to reflect new package structure. This file is minimal (45 lines) so the changes are trivial.

---

## Phase 3: Packaging and Distribution

### Task 3.1 — Create ScrollKit `setup.py` / `pyproject.toml`

Package the library for:
- **PyPI** (for desktop/simulator development): `pip install scrollkit`
- **CircuitPython bundle** (for hardware deployment): as `.mpy` files

Dependencies: `adafruit-circuitpython-*` libraries (for hardware), `pygame` (for simulator).

### Task 3.2 — Create Theme Park Waits `requirements.txt`

List ScrollKit as a dependency plus any additional application-specific dependencies.

### Task 3.3 — Write ScrollKit examples

Create simple example applications that demonstrate the library:
1. `examples/hello_world.py` — basic scrolling text
2. `examples/custom_layout.py` — building custom display groups
3. `examples/generic_api_client.py` — using the HTTP client for any API
4. `examples/config_server.py` — creating a generic web configuration interface

---

## Phase 4: Verification

### Task 4.1 — Verify library independence

Run the ScrollKit library tests on its own without any Theme Park Waits files present. Ensure all imports resolve correctly.

### Task 4.2 — Verify Theme Park Waits with new library

1. Install ScrollKit as a dependency
2. Run Theme Park Waits in dev mode (`--dev`) to verify the simulator works
3. Deploy to CircuitPython hardware to verify hardware operation
4. Verify the web configuration interface still works
5. Verify OTA updates still work

### Task 4.3 — Run existing test suite

Run `make test-unit` and `make test-all` to ensure no regressions. Update test imports to reflect new package structure.

---

## Estimated Effort

| Phase | Effort | Risk |
|---|---|---|
| Phase 1 (Library creation) | 3-4 days | Medium — Task 1.4 (generic display) is the hardest |
| Phase 2 (App refactoring) | 2-3 days | Low — mostly import path changes and display class restructuring |
| Phase 3 (Packaging) | 1-2 days | Low |
| Phase 4 (Verification) | 1-2 days | Medium — hardware testing required |

**Total: 7-11 days**

The single highest-risk task is **Task 1.4** (creating the generic display). It requires carefully extracting the platform detection and rendering logic while leaving all theme-park-specific content in the application layer. Getting this wrong would break both the simulator and hardware operation.