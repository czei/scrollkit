# Utilities

`scrollkit.utils` collects small, dependency-light helpers used across the
library.

| Module | What it offers |
|--------|----------------|
| `utils.color_utils` | RGB ↔ hex conversion, brightness scaling, colour matching |
| `utils.error_handler` | `ErrorHandler` — centralised logging with file persistence |
| `utils.system_utils` | free-memory info, uptime, timestamp formatting |
| `utils.timer` | a small `Timer` for common timing patterns |
| `utils.url_utils` | credential loading from `secrets.py` |
| `utils.image_processor` | basic image scaling/cropping helpers |

## Colour helpers

```python
from scrollkit.utils.color_utils import rgb_to_hex, hex_to_rgb, scale_brightness

rgb_to_hex((255, 0, 128))      # 0xFF0080
hex_to_rgb(0x00FF88)           # (0, 255, 136)
scale_brightness((255, 255, 255), 0.5)
```

## Error logging

```python
from scrollkit.utils.error_handler import ErrorHandler

log = ErrorHandler()
log.error(exception, "context message")
```

`ErrorHandler` writes to a log file when the filesystem is writable and degrades
gracefully when it isn't (e.g. a read-only CircuitPython filesystem).
