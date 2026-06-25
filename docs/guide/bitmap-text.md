# Palette-Animated Bitmap Text (Class 3)

`scrollkit.display.bitmap_text` is the headline differentiator — text that is
visibly *not just displayio*. A ScrollKit-native fixed-cell **5×7 font**
(`FONT_5x7`, table-driven, no BDF parsing) is rendered **once** into an indexed
`Bitmap` whose lit pixels carry palette *indices*. The message scrolls by moving a
`TileGrid`, and the animation comes from rewriting a few **palette** entries each
frame — near-zero per-frame pixel work and **no glyph rebuild**.

!!! info "Reads well static or scrolling"
    The palette effects (`RainbowChase`, `NeonTubeCrawl`, `ChromeSheen`,
    `HazardStripes`) animate colour, not position, so they look good whether the
    text is held static or scrolling (`PAIRS_WITH = ("static", "scrolling")`). See
    [pairing effects to content](effects.md#pairing-effects-to-content).

```python
from scrollkit.display.bitmap_text import (
    BitmapText, RainbowChase, NeonTubeCrawl, ChromeSheen, HazardStripes,
)

text = BitmapText("SCROLLKIT  ", y=12, palette_effect=RainbowChase(period=3),
                  scroll_speed=20, max_width_px=320)
# each frame:
await text.render(display)
```

`BitmapText` is a `DisplayContent`: it builds its indexed bitmap on the first
render, adds a TileGrid layer via `display.add_layer`, and removes it on `stop()`
or `detach(display)`.

## Palette effects

A `palette_effect` rewrites a few `palette[i] = color` entries per frame to animate
the same rendered glyphs. They are plain strategy objects with an
`apply(palette)` method:

| Effect | Animation |
|--------|-----------|
| `RainbowChase` | Rotates a 6-colour rainbow ramp so a rainbow travels through the letters. |
| `NeonTubeCrawl` | A bright pulse crawls along an otherwise-dim neon tube (one glowing ramp slot moves). |
| `ChromeSheen` | A dark→light grey ramp with a highlight band that sweeps across — a metallic sheen. |
| `HazardStripes` | Alternating warning colours that march one slot per step. |

Each takes a `period` (advance every N frames) for calmer or faster motion. Write
your own by providing an object with `apply(palette)`.

## Font

`FONT_5x7` covers the printable ASCII set: `A–Z`, `0–9`, space, and common
punctuation (`. , ! ? : ; - + / = ( ) < > % # @ & $ ' " _ * \`). Lookups fold to
upper-case; unknown characters render blank. `max_width_px` bounds the rendered
bitmap (the whole message is rendered into one bitmap — Option A; a ring-buffer
viewport variant is deferred).

## Hardware budget

`BitmapText.FEASIBILITY` advertises the cost:

| | Value |
|---|---|
| `hardware_safe` | `True` |
| `allocates_per_frame` | `False` |
| `max_pixel_writes_per_frame` | `0` (palette rewrites + TileGrid move only) |
| `modeled_frame_ms` | ~5 |

The glyph bitmap is built once; every subsequent frame is a handful of palette
writes plus a `TileGrid.x` change, so per-frame **pixel** work is zero. Strict-
feasible at the ~50 ms (20 fps) `bit_depth=4` device budget.
