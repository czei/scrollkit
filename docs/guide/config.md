# Configuration

`scrollkit.config.settings_manager.SettingsManager` persists application settings
to a JSON file that survives reboots, and is safe to read while the app runs.

```python
from scrollkit.config.settings_manager import SettingsManager

settings = SettingsManager(
    filename="settings.json",
    defaults={"brightness_scale": "0.5", "scroll_speed": "Medium"},
)

settings.get("scroll_speed")          # "Medium"
settings.set("scroll_speed", "Fast")
settings.save_settings()              # persist to disk
settings.get_scroll_speed()           # 0.02 (seconds/pixel for "Fast")
```

## Highlights

- **Defaults** — register app-specific defaults; only missing keys are filled in.
- **Scroll speed** — `get_scroll_speed()` maps `"Slow" / "Medium" / "Fast"` to
  seconds-per-pixel.
- **Pretty names** — `get_pretty_name("scroll_speed")` → `"Scroll Speed"` for UI.
- **CircuitPython bool quirk** — CircuitPython's JSON parser stores booleans as
  strings; `SettingsManager` knows which keys are booleans and coerces them back,
  so you get real `True`/`False`.

## Who writes settings

The [web UI](web.md) writes settings; the main display loop reads them. The web
server never touches the display queue directly — settings are the safe channel
between the two.
