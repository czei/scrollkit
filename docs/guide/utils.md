# Utilities

`scrollkit.utils` collects small, dependency-light helpers used across the
library.

| Module | What it offers |
|--------|----------------|
| `utils.color_utils` | `colors` — a small Title-case-name → hex-string table consumed by the settings schema (color math itself now lives in `display.colors`) |
| `utils.error_handler` | `ErrorHandler` — centralised logging with file persistence |
| `utils.system_utils` | NTP / HTTP-Date system clock sync (`set_system_clock`) |
| `utils.url_utils` | credential loading from `secrets.py` |

## Colour helpers

```python
from scrollkit.utils.color_utils import ColorUtils

ColorUtils.colors["Orange"]   # "0xffa500" — used as a settings default
```

For actual colour math (hex/int conversion, brightness scaling, gradients), see
[Colour generators](#colour-generators) below (`scrollkit.display.colors`) — the
current, correct API.

## Error logging

```python
from scrollkit.utils.error_handler import ErrorHandler

log = ErrorHandler("error_log")
log.error(exception, "context message")
```

`ErrorHandler` writes to a log file when the filesystem is writable and degrades
gracefully when it isn't (e.g. a read-only CircuitPython filesystem).

## Colour generators

`scrollkit.display.colors` exposes the **full** 24-bit colour space as continuous
generators (device-safe integer math) rather than a fixed catalogue of named
palettes — sample exactly the ramp you want, at the resolution the panel can show.
Build a ramp **once** (at import or effect construction) and reuse it; none of these
belong in a per-frame loop.

```python
from scrollkit.display.colors import spectrum, gradient, multi_gradient, depth_palette

spectrum(16)                                        # 16 hues around the wheel
gradient(0x102840, 0x00CCFF, 16)                    # deep blue -> cyan
multi_gradient((0x330000, 0xFF4400, 0xFFF0A0), 16)  # a fire ramp
depth_palette(0x66CCFF, strength=0.55)              # a close "lit from above" ramp
```

<div class="grid" markdown>
<figure markdown="span">![spectrum](../assets/reference/colors/spectrum.png){ width="280" }<figcaption>`spectrum(16)`</figcaption></figure>
<figure markdown="span">![gradient](../assets/reference/colors/gradient.png){ width="280" }<figcaption>`gradient(...)`</figcaption></figure>
<figure markdown="span">![multi_gradient](../assets/reference/colors/multi-gradient.png){ width="280" }<figcaption>`multi_gradient(...)`</figcaption></figure>
<figure markdown="span">![depth_palette](../assets/reference/colors/depth-palette.png){ width="280" }<figcaption>`depth_palette(...)`</figcaption></figure>
</div>

`hsv(h, s, v)`, `wheel(pos)`, `scale(color, factor)` and `lerp(a, b, t)` round out the
set for single-colour needs. For the 16 named colours used by the minimal API:

![named colours](../assets/reference/colors/named-colors.png){ width="280" }

Feed any of these straight to a [gradient text fill](gradient-text.md)
(`palette=...`).
