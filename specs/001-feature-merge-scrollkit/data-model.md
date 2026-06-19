# Data Model & Package Architecture: Merged ScrollKit

## Merged Package Structure

```
src/scrollkit/
├── __init__.py                    # Public exports (see Exports section)
│
├── app/
│   ├── __init__.py
│   ├── base.py                    # SLDKApp — full-featured async app base
│   └── minimal.py                 # MinimalLEDApp — lightweight entry point
│
├── display/
│   ├── __init__.py
│   ├── interface.py               # DisplayInterface ABC
│   ├── hardware.py                # CircuitPython hardware display (MatrixPortal S3)
│   ├── simulator.py               # Desktop simulator display (uses scrollkit.simulator)
│   ├── unified.py                 # UnifiedDisplay — auto-detects platform
│   ├── queue.py                   # DisplayQueue — priority + expiry queue
│   ├── manager.py                 # DisplayManager — drives queue + strategy
│   ├── strategy.py                # DisplayStrategy ABC + Priority enum + registry
│   ├── content.py                 # DisplayContent, StaticText, ScrollingText
│   └── enhanced_content.py        # GradientText, AnimatedContent, etc.
│
├── effects/
│   ├── __init__.py
│   ├── base.py                    # Effect ABC
│   ├── effects.py                 # EffectsEngine (max 2 concurrent, 5 FPS default)
│   ├── transitions.py             # FadeTransition, SlideTransition, etc.
│   ├── basic_transitions.py       # Simple cut/wipe transitions
│   ├── particles.py               # ParticleEngine — particle burst effects
│   └── reveal.py                  # RevealEffect — progressive uncover animation
│
├── web/
│   ├── __init__.py
│   ├── server.py                  # ScrollKitWebServer — unified web server
│   ├── adapters.py                # CircuitPythonAdapter + DesktopAdapter
│   ├── handlers.py                # WebHandler, StaticFileHandler, APIHandler
│   ├── forms.py                   # Form parsing
│   └── templates.py               # HTML template rendering
│
├── ota/
│   ├── __init__.py
│   ├── client.py                  # OTAClient — fetches manifest, downloads, applies
│   ├── manifest.py                # UpdateManifest — version, file list, checksums
│   ├── server.py                  # OTAServer — serves manifests (desktop/CI use)
│   └── updater.py                 # Thin orchestration layer
│
├── network/
│   ├── __init__.py
│   ├── wifi_manager.py            # WiFiManager — CircuitPython WiFi (from ScrollKit)
│   ├── http_client.py             # HttpClient — async/sync HTTP (from ScrollKit)
│   └── http_response.py           # Response wrappers + JSON BOM handling
│
├── config/
│   ├── __init__.py
│   └── settings_manager.py        # SettingsManager — JSON persistence (from ScrollKit)
│
├── simulator/                     # Desktop display emulation (from SLDK, unchanged)
│   ├── __init__.py
│   ├── core/
│   │   ├── display_manager.py     # pygame window manager
│   │   ├── led_matrix.py          # Virtual LED matrix grid
│   │   ├── pixel_buffer.py        # Raw pixel storage
│   │   └── color_utils.py
│   ├── displayio/                 # CircuitPython displayio emulation
│   │   ├── bitmap.py
│   │   ├── palette.py
│   │   ├── tilegrid.py
│   │   ├── group.py
│   │   ├── display.py
│   │   ├── fourwire.py
│   │   └── ondiskbitmap.py
│   ├── adafruit_bitmap_font/      # BDF font loading
│   ├── adafruit_display_text/     # Text rendering (label, bitmap_label, scrolling_label)
│   ├── terminalio/                # Terminal font
│   ├── devices/
│   │   ├── base_device.py
│   │   ├── generic_matrix.py
│   │   └── matrixportal_s3.py     # MatrixPortal S3 simulator
│   └── fonts/                     # BDF font files
│
└── utils/
    ├── __init__.py
    ├── error_handler.py           # ErrorHandler — file-based logging (from ScrollKit)
    ├── color_utils.py             # RGB/hex conversion, brightness (from ScrollKit)
    ├── system_utils.py            # Memory info, uptime, battery (from ScrollKit)
    ├── timer.py                   # Timer class (from ScrollKit)
    └── url_utils.py               # secrets.py credential loading (from ScrollKit)
```

---

## Application Layer (NOT in scrollkit package — OUT OF SCOPE, left untouched)

These ThemeParkWaits files remain exactly as they are. Porting them onto the merged library is **out of scope** for this work (see research D-013). They are listed only to mark the library/application boundary — none of them are created, modified, or migrated here.

```
src/
├── app.py                         # ThemeParkApp controller (untouched)
├── main.py                        # App entry point (untouched)
├── themeparkwaits.py              # Module bridge — code.py imports this (untouched)
├── models/                        # untouched
│   ├── theme_park.py
│   ├── theme_park_ride.py
│   ├── theme_park_list.py
│   ├── vacation.py
│   └── epic_universe_rides.py
├── api/                           # untouched
│   └── theme_park_service.py
└── ui/                            # untouched
    └── [display implementations for ThemeParkWaits]
```

> **Note**: Because the merged `scrollkit` replaces the old `src/scrollkit/`, ThemeParkWaits (which imports the old package) is expected to need a separate porting pass later. That pass is deliberately not part of this project — the deliverable here is the standalone library + its own demos.

---

## Core Entities

### DisplayContent
A unit of content to be shown on the display.

```
DisplayContent
  id: str                          # unique identifier
  type: str                        # 'static' | 'scrolling' | 'custom'
  data: Any                        # text, image ref, or custom payload
  priority: Priority               # IDLE | LOW | NORMAL | HIGH | SYSTEM
  duration: float | None           # seconds to display; None = indefinite
  elapsed: float                   # seconds this item has been active
  created_at: float                # time.monotonic() at creation

  is_complete() -> bool            # elapsed >= duration (if duration set)
  render(display: DisplayInterface) -> None
```

Subtypes:
- `StaticText(text, color, font)` — renders non-scrolling text
- `ScrollingText(text, color, scroll_delay, font)` — scrolls text across display

### Priority (enum)
```
IDLE   = 0
LOW    = 1
NORMAL = 2
HIGH   = 3
SYSTEM = 4
```

### DisplayQueue
```
DisplayQueue
  max_items: int                   # cap total queue size
  items: list[DisplayContent]      # sorted by priority (descending)

  add(content: DisplayContent) -> bool    # see eviction policy below
  peek() -> DisplayContent | None         # highest-priority unexpired item
  pop() -> DisplayContent | None          # consume next item
  expire() -> None                        # remove completed items
  len() -> int
```

**Eviction policy** (when `len() == max_items` and `add()` is called):
- If the incoming item is SYSTEM priority → always admit; evict the lowest-priority, oldest non-SYSTEM item to make room.
- Else if the incoming item's priority is higher than the lowest-priority item present → evict that lowest-priority, oldest item; admit the incoming item; return `True`.
- Else (incoming item is lower-or-equal priority than everything present) → reject; return `False`.
- SYSTEM-priority items are never evicted by `add()`.

### UpdateManifest
```
UpdateManifest
  version: str                     # semver (e.g. "1.3.0")
  description: str
  files: dict[path, FileInfo]      # {relative_path: {size, checksum, required}}
  dependencies: list[DependencyInfo]
  requirements: dict               # {circuitpython_version, memory_required, storage_required}
  pre_update_scripts: list[str]    # Python snippets to run before update
  post_update_scripts: list[str]   # Python snippets to run after update

FileInfo
  size: int                        # bytes
  checksum: str                    # SHA256 hex
  required: bool                   # if False, skip on low storage

compare_version(other: str) -> int  # -1 / 0 / 1
validate() -> tuple[bool, str]
```

### Settings
```
SettingsManager
  filename: str                    # path to JSON file
  defaults: dict                   # default values for missing keys
  bool_keys: set[str]              # keys to coerce from string to bool

  get(key: str, default=None) -> Any
  set(key: str, value: Any) -> None
  save_settings() -> None
  load_settings() -> dict
  get_scroll_speed() -> float      # maps "Slow"/"Medium"/"Fast" to seconds/pixel
  get_pretty_name(key: str) -> str  # snake_case → Title Case
```

### SLDKApp (renamed: ScrollKitApp in public API)
```
ScrollKitApp (base class)
  display: UnifiedDisplay
  enable_web: bool
  update_interval: float           # seconds between data refreshes

  # Override these:
  async setup() -> None
  async update_data() -> None
  async prepare_display_content() -> DisplayContent | None

  # Framework internals:
  async run() -> None
  async _display_process() -> None   # always runs
  async _data_update_process() -> None  # runs if ≥30KB free
  async _web_server_process() -> None   # runs if ≥50KB free and enable_web
```

---

## Public API Surface (`src/scrollkit/__init__.py`)

**The top-level `__init__.py` MUST stay lightweight** — version metadata only, NO eager imports of submodules. On CircuitPython every imported module costs a globals dict + bytecode overhead; eagerly importing app/display/effects/web/ota/network/utils at `import scrollkit` time could cost 50–100 KB of SRAM before the app even starts (see research D-011). Importing the package alone must have no meaningful memory cost and no side effects.

```python
# src/scrollkit/__init__.py  — the WHOLE file
__version__ = "1.0.0"
# No eager submodule imports. Users import exactly what they need.
```

Callers import from submodules directly (pay-as-you-go):

```python
# App framework
from scrollkit.app.minimal import MinimalLEDApp
from scrollkit.app.base import ScrollKitApp

# Display
from scrollkit.display.unified import UnifiedDisplay
from scrollkit.display.content import DisplayContent, StaticText, ScrollingText
from scrollkit.display.queue import DisplayQueue
from scrollkit.display.strategy import Priority

# Effects
from scrollkit.effects.effects import EffectsEngine

# Web
from scrollkit.web.server import ScrollKitWebServer

# OTA
from scrollkit.ota.client import OTAClient
from scrollkit.ota.manifest import UpdateManifest

# Config & Network
from scrollkit.config.settings_manager import SettingsManager
from scrollkit.network.wifi_manager import WiFiManager
from scrollkit.network.http_client import HttpClient

# Utils
from scrollkit.utils.error_handler import ErrorHandler
from scrollkit.utils.color_utils import rgb_to_hex, hex_to_rgb, scale_brightness
```

---

## Dependency Graph (import order for initialization)

```
utils/               ← no internal dependencies
config/              ← utils
network/             ← utils, config
simulator/           ← no internal dependencies (only pygame + stdlib)
display/interface    ← utils
display/hardware     ← display/interface
display/simulator    ← display/interface, simulator/
display/unified      ← display/hardware, display/simulator
display/content      ← utils
display/queue        ← display/content
display/strategy     ← display/content
display/manager      ← display/queue, display/strategy, display/unified
effects/             ← display/
web/                 ← network/, config/
ota/                 ← network/, utils/
app/base             ← display/manager, effects/, web/, ota/, network/, config/
app/minimal          ← app/base
```

---

## Memory-Constrained Feature Ladder

| Available Free RAM | Features Enabled |
|--------------------|-----------------|
| Any | Display process, static/scrolling text, settings |
| ≥ 30 KB | + Data update process (periodic async refresh) |
| ≥ 50 KB | + Web server (configuration interface) |
| ≥ 80 KB | + Effects engine (transitions/particles) |

The 80 KB threshold for effects is a new addition (effects weren't in the original SLDK memory ladder). This prevents the effects engine from being initialized on very low memory devices.
