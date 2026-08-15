# Pixel Art

A 64×32 panel is 2,048 pixels. That is not a small screen — it is a *drawing
surface*, and it has been one since the 1980s. Yet the default answer to "build
me an LED sign" is almost always a line of scrolling text, because the text
classes are the first thing every API tour shows you.

Text is the right answer for a bus timetable. It is the wrong answer for a
**sign** — the thing hanging in a lobby that has to say who you are in one
glance, from across a room, to someone who is not going to stand and read.
That job wants a wordmark you drew, in your colors, at the weight you chose,
next to a picture of the thing you actually do.

This page is how. It is the general form of the conventions in the
[Forge sign](../sample-project.md) — a real 24/7 makerspace sign built entirely
from hand-drawn pixel art — and its worked example is
[`demos/medium/pixel_wordmark.py`](../demos.md#pixel-wordmark), which is ~420
lines and passes the strict feasibility gate.

!!! abstract "The one idea"
    Pixel art is per-pixel **data**, and per-pixel work is exactly what the
    device cannot afford. The resolution is that you pay for the pixels
    **once**, at startup, and afterwards animate by writing *palette entries*
    and *tile positions* — a few microseconds a frame, no matter how elaborate
    the picture. Everything below is a consequence of that sentence.

---

## 1. Letterforms are data

A glyph is a tuple of equal-length strings, one character per LED. A character
names a **palette slot**, not a color, so the art and its coloring stay
independent:

```python
CHAR_TO_SLOT = {".": 0, " ": 0, "#": 1, "o": 2, "w": 3, "s": 4, "d": 5}
#                transparent    brand  ember  cream  ceramic  shadow
```

Slot 0 is transparent (`palette.make_transparent(0)`), so a sprite is a
silhouette rather than a rectangle. Everything else is an index into one
palette you control. Map `" "` to 0 as well as `"."` — spaces creep into ASCII
art and an unmapped character is a `KeyError` at startup (see below).

Now the letters. Editing art is editing text:

```python
CAPS7 = {
    "B": ("####.",
          "#...#",
          "#...#",
          "####.",
          "#...#",
          "#...#",
          "####."),
    "E": ("#####",
          "#....",
          "#....",
          "####.",
          "#....",
          "#....",
          "#####"),
}
```

### Repair the art at import — both crashes are typos

Hand-authored art fails at startup in exactly two ways, and both throw from deep
inside the conversion loop with nothing on the panel and no clue which sprite is
at fault:

- **Ragged rows.** You add a character to row 4 and forget the others. A bitmap
  sized from `rows[0]` then throws
  `IndexError: Pixel index (30, 4) out of bounds`.
- **A character you never mapped.** A stray space, or a `+` you invented for a
  highlight and never added to the slot map: `KeyError: '+'`.

These are not hypothetical, and they are not rare. When this page was tested on
models building a sign from scratch, **every single first-attempt failure was
one of these two and nothing else** — one of them a single row of 25 characters
where its two neighbours were 26, inside a 598-line program with 34 sprites.

Neither is ambiguous about what you meant, so don't crash on them — repair them:

```python
from scrollkit.utils.pixel_art import normalize_all, normalize_art

CAPS7 = normalize_all(CAPS7, CHAR_TO_SLOT)          # a whole {name: rows} map
ANVIL = normalize_art(ANVIL, CHAR_TO_SLOT, name="ANVIL")   # or one sprite
```

Short rows pad on the right with transparent. Unmapped whitespace becomes
transparent. Any *other* unmapped character becomes the first lit slot — because
you drew something there, and silently substituting transparent would delete the
sprite instead of coloring it oddly. Every repair prints one line naming the
sprite, so you find out without the sign going dark:

```
pixel_art: ANVIL: padded 1 ragged row(s) to width 26
pixel_art: ANVIL: unmapped character(s) + -> 'o'; map them explicitly to pick their color
```

Clean art passes through untouched, so normalizing costs nothing once the art is
right. To assert instead of repair — in a test, say — use `art_problems`, which
returns a list of strings and is empty when the art is clean:

```python
from scrollkit.utils.pixel_art import art_problems

for name, rows in CAPS7.items():
    assert not art_problems(rows, CHAR_TO_SLOT, name=name)
```

### Author small, then double

Strokes are the thing that goes wrong. A letterform drawn freehand at 14 px
tall ends up with 2-px stems and 3-px bowls and reads as mush. Draw it at 5×7
with **1-px strokes**, then scale by an integer factor — every stroke comes out
exactly 2 px, and the shapes stay the ones you approved:

```python
def scale2(rows):
    """Integer 2x scale: every pixel becomes 2x2."""
    out = []
    for row in rows:
        wide = "".join(ch + ch for ch in row)
        out.append(wide)
        out.append(wide)
    return out
```

Non-integer scaling is not available to you. There is no antialiasing on an LED
panel — a pixel is on or off — so 1.5× produces a limp you will see from the
doorway.

### Sizing for 64×32

Do the arithmetic before you draw. Width is the constraint that bites:

```
n glyphs x glyph_width + (n - 1) x gap  <=  64
```

`BREW` at 10 px per glyph with 2-px gaps is `4 × 10 + 3 × 2 = 46` px, centred at
`x = (64 - 46) // 2 = 9`. Five letters at 12 px would be 68 — over, before you
started. The Forge's hero `FORGE` is exactly `5 × 10 + 4 × 2 = 58` px for this
reason, and its second size (8 px glyphs, 1-px gaps, 44 px) exists so the same
word fits alongside a picture.

Practical sizes for a 32-px-tall panel:

| Cap height | Glyphs across 64 px | Use |
|---|---|---|
| 20 px | ~5 | a wordmark alone, filling the panel |
| 13-14 px | ~4-5 | a wordmark with a subject sprite below it |
| 8 px | ~10 | a second line (`THE`, a tagline, a stacked lockup) |

### Your glyphs vs. the built-in font

ScrollKit's text classes and `pixels_from_text()` use a fixed 5×7 bitmap font
and place text on a **baseline** — `y` is the baseline, not the top, which is
why `y=0` pushes the ascenders off the panel and renders nothing readable, and
`y≈12` centres a line (`capabilities()["panel"]["coordinates"]` has the rule).
That font is the right tool when the content is *words that change*.

Hand-drawn glyphs are the right tool when the content is *your identity*. They
cost you a tuple per letter and buy you weight, width, counters, an ember in
the O — and, crucially, **top-left placement**: a glyph tile's `y` is the top
row of the art, so a 14-px glyph at `y=2` occupies rows 2..15 exactly. No
baseline arithmetic, no surprises. You only need the letters your sign spells.

---

## 2. The subject sprite

A wordmark tells people your name. The sprite tells them what you do — and it
is the thing that makes a passer-by look twice. A hammer and anvil. A saw
blade. A coffee cup. Same convention, more slots:

```python
CUP = ("dddddddddd.....",
       "dooooooood.....",
       "dooooooooddddd.",
       "dssssssssd..dd.",
       "dssssssssd..dd.",
       "dssssssssddddd.",
       ".dsssssssd.....",
       "..ddddddd......",
       ".ssssssssss....",
       "..dddddddd.....")
```

Three conventions from the Forge, all of which exist because of something that
went wrong first:

**Partition the palette by role.** Slots 1-3 are *logo* colors — anything may
animate them. Slots 4-5 are *material* shades used only by the subject. A
palette treatment sweeping heat through the wordmark writes the logo slots; the
ceramic physically cannot change color, because no effect knows those slots
exist. (The Forge reserves 1-3 for the mark, 4-8 for a heat ramp, 9-11 for
steel/iron/wood, and says so in its module docstring so nothing drifts.)

**Contrast against black, not against paper.** A "black" outline on a bee works
on white paper; on an unlit LED panel it *is* the background. Use a dark
*color* (`SHADOW = 0x6A6058`) where you want a shadow, and reserve true black
for "off". This is also why unlit pixels are free real estate — the Forge's
knockout block (a solid yellow rectangle with the letterforms punched out
unlit) costs nothing extra and is the brand's actual mark.

**One silhouette, several renderings.** The Forge's anvil is authored once and
rendered twice: in steel (`s`/`d` material slots) for the vignette where a
hammer strikes it, and as a one-color brand-yellow *stencil* for the layouts
where it is a logo element. The transform is four lines and runs at import:

```python
def _stencil(rows):
    """Every lit pixel goes to the brand slot."""
    return ["".join("#" if c != "." else "." for c in row) for row in rows]
```

The same trick gives you `_white_hot(rows)` (swap the body slot for the
highlight slot) so a freshly-forged letter can cool to brand color with a
single palette lerp instead of a second bitmap.

!!! note "Gamma, if you are chasing exact brand color"
    A HUB75 panel's drive is linear in the channel value, so the design colors
    you sampled from a logo file come out roughly 10× too bright in the dark
    channels. The Forge gamma-encodes every design color **once at import**
    (`panel_color()`, `PANEL_GAMMA = 2.2`) and makes it the identity on
    desktop, so previews keep the design intent and the panel gets the corrected
    values. It is a per-app choice, not something the library imposes.

Sprite *motion* — pose cycles, mirroring, eased flight paths, props — is a
subject of its own and already has a page:
[Character Animation](character-animation.md). This page is about the mark and
the acts it plays.

---

## 3. Build once, mutate forever

Here is the tension, stated honestly.

`performance_guide()` says never to push pixels in a Python loop. Pixel art is
per-pixel data. Both are true, and the resolution is not a clever drawing
technique — it is that **you stop drawing**.

### What the device actually charges

Every number here is from `device_benchmarks.json`, captured on a real
MatrixPortal S3 (CircuitPython 9.1.0):

| Operation | Measured | Per pixel |
|---|---|---|
| `bitmap[x, y] = v` (interpreted) | 6,996 ns | 6,996 ns |
| `bitmaptools.fill_region`, 512 px | 147,049 ns | 287 ns |
| `bitmaptools.blit`, 256 px | 159,462 ns | 623 ns |
| `bitmap.fill(v)`, whole 64×32 | 8,926 ns | 4.4 ns |
| `palette[i] = color` | 2,629 ns | — |
| `tile.x = n` / `tile.hidden = True` | 2,492 ns | — |
| `TileGrid(...)` (allocate) | 47,607 ns | — |
| `display.refresh()` @ `bit_depth=4` | 4,488,000 ns | — |

Read the middle rows carefully, because the usual summary ("use C calls") is
too coarse to act on. A C bulk call carries a fixed dispatch cost — the
library's model puts it at ~12 µs — amortized over however many pixels the call
covers. `bitmap.fill` covers 2,048 pixels in one call, so it is ~1,600× cheaper
per pixel than the interpreted write. A **one-pixel** `fill_region` covers one,
so it costs ~12 µs — *worse* than the 7 µs interpreted write it was supposed to
replace.

So there is no bulk call that draws pixel art cheaply. Pixel art is, by
definition, a different value at every pixel. The only winning move is to
convert it exactly once.

### The conversion, once

```python
def _tile(self, display, rows, x=0, y=0):
    """ASCII rows -> Bitmap -> TileGrid, added hidden. Build-time only."""
    gfx = display.gfx
    bmp = gfx.Bitmap(max(len(row) for row in rows), len(rows),
                     len(PALETTE_COLORS))
    for ty, row in enumerate(rows):
        for tx, ch in enumerate(row):
            slot = CHAR_TO_SLOT[ch]
            if slot:
                bmp[tx, ty] = slot
    tile = gfx.TileGrid(bmp, pixel_shader=self._palette)
    tile.x, tile.y = x, y
    tile.hidden = True
    display.add_layer(tile)
    return tile
```

Note `max(len(row) for row in rows)` rather than `len(rows[0])`: belt to
`normalize_art`'s braces, so art that skipped normalization still renders rather
than raising `IndexError` from inside the loop.

`display.gfx` is the one graphics path: real `displayio` on CircuitPython, the
simulator's equivalents on desktop, same code either way. `add_layer` composites
the tile above content and — this is the part that makes the whole approach
work — the display loop's per-frame `clear()` deliberately **does not touch
layers**. Your art stays on the panel without being redrawn.

The demo builds 4 glyph tiles, a cup, two steam cels, a striped backdrop, a
mask and two palette partitions: **1,318 interpreted bitmap writes, ~9.2 ms of
device time, paid once**. Instrument the next 400 frames and you get **zero
bitmap writes and 9.3 palette writes per frame — about 25 µs**, 0.05% of the
50 ms budget. That ratio is the whole technique.

### The smallest complete example

Forty lines, and it runs. Build in the first `render()` call (the display exists
by then), animate with two writes after that:

```python
from scrollkit.app.base import ScrollKitApp
from scrollkit.display.content import DisplayContent

ART = ("#.....#####.####.",     # L E D, 5 px each, 1 px gaps -> 17 px wide
       "#.....#.....#...#",
       "#.....####..#...#",
       "#.....#.....#...#",
       "#.....#.....#...#",
       "#####.#####.####.")
SLOTS = {".": 0, "#": 1}
COLORS = (0x000000, 0x00FF88)


class Mark(DisplayContent):
    def __init__(self):
        DisplayContent.__init__(self, duration=None)   # never reads a clock
        self._tile = None
        self._f = 0

    async def render(self, display):
        if self._tile is None:                         # build ONCE
            gfx = display.gfx
            bmp = gfx.Bitmap(max(len(r) for r in ART), len(ART), len(COLORS))
            for y, row in enumerate(ART):
                for x, ch in enumerate(row):
                    bmp[x, y] = SLOTS[ch]
            self._pal = gfx.Palette(len(COLORS))
            self._pal[0], self._pal[1] = COLORS
            self._pal.make_transparent(0)
            self._tile = gfx.TileGrid(bmp, pixel_shader=self._pal)
            self._tile.x, self._tile.y = 23, 13        # (64-17)//2, (32-6)//2
            display.add_layer(self._tile)
        self._f += 1                     # animate with TWO writes a frame:
        self._tile.y = 13 + (self._f // 8) % 2         # a 1 px bob...
        self._pal[1] = COLORS[1] if self._f % 24 < 12 else 0x006644


class MarkApp(ScrollKitApp):
    def __init__(self):
        super().__init__(enable_web=False, update_interval=3600)

    async def create_display(self):
        from scrollkit.display.simulator import SimulatorDisplay
        return SimulatorDisplay(width=64, height=32)

    async def setup(self):
        self.content_queue.add(Mark())
```

`run_headless(MarkApp(), frames=120, strict=True)` returns `advanced=True`,
`~195 fps`, no warnings. Grow it from here.

### The arithmetic that decides your design

| Per frame | Device cost | Share of the 50 ms budget |
|---|---|---|
| `display.refresh()` (unavoidable) | 4.5 ms | 9% |
| 14 palette writes (the demo's busiest act) | 37 µs | 0.07% |
| repaint a 300-px wordmark, per pixel | 2.1 ms | 4% |
| repaint the full 2,048-px panel, per pixel | 14.3 ms | 29% |

And that last row is only the *writes*. Deciding each pixel's color costs about
as much again: on this chip a bare loop iteration is 2.0 µs, an integer add
1.5 µs, a list index 2.9 µs, a dict lookup 2.3 µs. A per-pixel loop that
computes anything is roughly twice the table's number.

You can watch the cliff in the harness. The same content, painted through
`display.set_pixel` every frame at increasing sizes:

| Pixels repainted per frame | Modeled frame time | Modeled FPS |
|---|---|---|
| 0 (refresh only) | 4.5 ms | ~223 |
| 100 | 7.2 ms | ~139 |
| 300 (a wordmark) | 12.7 ms | ~79 |
| 1,000 | 31.8 ms | ~32 |
| 2,048 (full panel) | 60.4 ms | ~17 — **over budget** |

A 300-pixel wordmark repainted every frame *survives*. That is the honest
answer, and it is also the trap: it survives right up until you add the second
animated thing, and the Forge's heaviest act already models at 49.47 ms against
a 50 ms budget. Building once costs you nothing you were going to spend
anyway, and it leaves the whole budget for the show.

!!! warning "The harness cannot catch this one for you"
    The simulator charges for `display.set_pixel`, for Label rebuilds, and for
    the bulk painters. It does **not** charge for a raw `bitmap[x, y] = v` in
    your own code — that write goes straight into a numpy buffer on desktop.
    So a per-frame per-pixel loop over your own bitmaps can pass
    `run_headless(strict=True)` and still crawl on the board. Keep every
    per-pixel loop inside your build step, where it is trivially auditable, and
    the question never arises.

---

## 4. Animating without touching a pixel

Five techniques cover essentially everything. All five are in the demo; all
five are palette writes or attribute writes.

### Move — `tile.x` / `tile.y`

A prebuilt tile moves for ~2.5 µs. Ease it, and the motion reads as intent
rather than as a tween ([Character Animation](character-animation.md) covers
the easing vocabulary):

```python
def _step_build(self, f):
    """The cup rises on an ease-out, then the wordmark drips in above it."""
    if f <= 10:
        self.cup.hidden = False
        self.cup.y = int(round(32 + (CUP_XY[1] - 32) * _ease_out(f / 10.0)))
        return False
```

### Cel-swap — two `hidden` flags

Draw the pose twice, show one. This is how the steam rises, how the Forge's saw
blade spins (two tooth phases), and how its hammer swings (three authored
rotation poses on an arc):

```python
up = (f // 4) % 2 == 0
self.steam[0].hidden = not up
self.steam[1].hidden = up
```

Never rebuild a bitmap to change a frame of animation. A `TileGrid` costs 48 µs
to allocate; a `hidden` flag costs 2.5 µs and doesn't feed the garbage
collector.

### Palette cycling — one write per color

The single cheapest animation there is. The demo's coffee heats and cools by
walking one palette slot along a ramp built at import:

```python
COFFEE_RAMP = multi_gradient((0x4A1C06, 0xB04C14, 0xE88A28), 12)

def _step_brew(self, f):
    """Cycle the coffee's heat through its ramp: ONE palette write."""
    i = f % 22
    self._palette[2] = COFFEE_RAMP[i if i < 12 else 22 - i]
```

The ping-pong index (`0..11` then `10..1`) is there so the loop has no seam.
Build ramps with the [color generators](utils.md#colour-generators)
(`gradient`, `multi_gradient`, `spectrum`, `depth_palette`) at import time —
never inside a frame.

### Partition + treatment — a gradient over the whole mark

To animate *across* the art rather than uniformly, assign every lit pixel to
one of N groups **once**, bake that into an indexed bitmap, then rewrite N
palette entries per frame. That is
[`PalettePartition`](palette-treatments.md), and the library ships thirteen
treatments that drive one.

**This is the single biggest difference between a sign that looks designed and a
sign that looks like tiles sliding around**, and it is ten lines. A mark that
only moves and blinks reads as a screensaver; a mark with a sweep travelling
through it reads as lit. Every act below should use one — it costs N palette
writes a frame, not a redraw:

```python
group_map, n = map_diagonal(self._slots, 10)
fx = PalettePartition(gfx, self._slots, group_map, n)
display.add_layer(fx.tile)
...
fx.fill(BRAND)                # every group the resting color
fx.tile.hidden = False        # the invisible swap: same pixels, same color
for tile in self.glyphs:      # ...one layer deeper
    tile.hidden = True
self._treatment = VelvetSweep(fx, THEME, sweeps=60)
```

The **invisible swap** is the trick worth stealing: paint the partition flat in
the mark's resting color and reveal it in the same frame you hide the glyph
tiles. Identical pixels, identical colors, no visible seam — and now the whole
mark is a single animatable layer. Every treatment starts and ends on the theme's
`flat` color precisely so this swap works in both directions.

A treatment takes a 5-stop theme `(base, dim, flat, warm, hot)`, darkest first,
and reports its own end:

```python
t = self._treatment
t.step()
if t.is_complete:
    fx.tile.hidden = True
    self._show_word()
```

### Mask — the mark as a window

Build an opaque layer covering the mark's box with the letters punched
**transparent**, put anything you like behind it, and animate the thing behind:

```python
mask = gfx.Bitmap(64, WORD_H, 2)
mask.fill(1)                          # one C call, 2,048 px
for (x, y) in self._slots:
    mask[x, y - WORD_Y] = 0           # punch the letters out
mask_pal = gfx.Palette(2)
mask_pal.make_transparent(0)
mask_pal[1] = 0x000000
```

The demo's backdrop is one striped row per palette slot, built with 14
`fill_region` calls; scrolling the stripes is *rotating the palette*, so the
tile never moves and can never bleed past the mask:

```python
def _step_glow(self, f):
    n = len(GLOW_BANDS)
    for i in range(n):
        self._back_pal[1 + i] = GLOW_BANDS[(i + f) % n]
```

Bound the mask to the mark's box, not the whole panel, and everything below it
(here, the cup) keeps living.

### And the reveals you don't have to write

Assembling and dismantling the mark is already solved. **Use these — do not write
your own reveal.** A hand-rolled one is the most reliable way to blow the frame
budget on a sign that was otherwise fine: it ends up touching pixels per frame,
which is the one thing §3 says never to do, and it does it during the busiest
moment of the act. These walk a prebuilt schedule and cost a handful of writes a
frame, and every one has run on the board for months.

Feed any of them your pixel set and drive it a step per frame:

| Effect | What it does |
|---|---|
| [`DripReveal`](effects.md#splash-reveals) | every pixel falls from an edge into place |
| [`SwarmReveal`](effects.md#splash-reveals) | a flock delivers pixels one per bird (≤ ~20 birds on device) |
| [`show_reveal_splash`](effects.md#splash-reveals) | the panel lights up, then everything not the mark winks off |
| [13 transitions](transitions.md) | full-screen cover → swap → reveal, by name |

```python
self._drip = DripReveal(list(self._slots), color=BRAND, fall_speed=2, stagger=1)
self._drip.start(display)
...
if self._drip.step():           # True when assembled
    self._drip.detach()
    self._show_word()           # the same pixels, now the real tiles
```

---

## 5. Composing acts, and scheduling them

### Placements are data

A *layout* is a table of `(glyph, x, y)` placements plus an **anchor point** —
the coordinate that anchored effects (wakes, halos, sonar sweeps, route
terminals) radiate from. Keep it as data and one wordmark composes several
ways with no new art:

```python
LAYOUTS = {
    "line": {                                   # FORGE at full size
        "glyphs": (("F", 3, 6), ("O", 15, 6), ("R", 27, 6),
                   ("G", 39, 6), ("E", 51, 6)),
        "anchor": "O",
        "anchor_point": (20, 15),               # the ember in the O's counter
    },
    "emblem": {                                 # the word standing on an anvil
        "glyphs": (("F13", 10, 2), ("O13", 19, 2), ("R13", 28, 2),
                   ("G13", 37, 2), ("E13", 46, 2), ("ANVIL", 21, 19)),
        "anchor": "ANVIL",
        "anchor_point": (31, 20),
    },
}
```

From a layout you derive the one thing every effect wants — the set of lit
pixels and their slots:

```python
def word_slots():
    """Every lit pixel of the assembled wordmark: {(x, y): slot}."""
    slots = {}
    for ch, gx0, gy0 in GLYPHS:
        for gy, row in enumerate(scale2(CAPS7[ch])):
            for gx, c in enumerate(row):
                if CHAR_TO_SLOT[c]:
                    slots[(gx0 + gx, gy0 + gy)] = CHAR_TO_SLOT[c]
    return slots
```

That dict feeds `DripReveal`, `SwarmReveal`, every partition builder, and the
mask. Build it once per layout and cache it.

### One act per thing the organization does

The wordmark says who they are; the acts say what happens in the building. A
makerspace with a metal shop, a laser, a woodshop and a 3D printer wants four
acts — a hammer forging the letters on an anvil, a laser cutting them out of
plate, a saw ripping a board, a printer rastering them in — not four screens of
text listing the equipment. The wordmark stays; the subject sprite changes. That
substitution is the whole difference between a sign for *them* and a sign for
anyone.

### An act is build → dwell → exit

Structure each act as three beats and you can mix and match them: a *build*
puts the mark on the panel, a *dwell treatment* keeps it interesting, an *exit*
takes it away. Because all three operate on the same pixel set, `N` builds ×
`M` treatments × `K` exits gives you `N × M × K` distinct acts from `N + M + K`
pieces of code. The Forge gets its whole show from 11 builds, 13 treatments and
8 exits.

### Schedule them, don't randomize them

Plain `random.choice` repeats. A sign that plays the same thing twice running
reads as broken to anyone watching, and someone is always watching a 24/7 sign.
`ActScheduler` (`scrollkit.utils.scheduler`) draws from decks of
`(name, family, ...)` entries, weights each by `(acts since last seen + 1)²`,
starts unseen entries old so fresh material leads, and refuses anything whose
**family** you tell it to avoid:

```python
DWELL_ACTS = (("brew", "subject"), ("sheen", "sweep"),
              ("rain", "fall"), ("glow", "mask"))

def _next(self):
    name, family = self._sched.pick(self.DWELL_ACTS, "dwell",
                                    avoid={self._family})
    self._begin(name, family)
```

Families are the whole point. Two different treatments that both *look like* a
diagonal sweep should share the family `"sweep"`, so the scheduler never plays
them back to back even though they are different code. Ages are kept per deck
key, so one instance schedules builds, treatments, exits and layouts
independently:

```python
b_name, b_fam, build = sched.pick(builds, "b", used)
t_name, t_fam, treat = sched.pick(treats, "t", used | {b_fam})
e_name, e_fam, exit_ = sched.pick(exits,  "e", used | {b_fam, t_fam})
```

`force=` names an opener with the same age bookkeeping — the Forge always
strikes the anvil on the first act after power-up, so the sign forges itself
when the shop wakes up.

!!! warning "Don't hand-roll the deck — `random.shuffle` isn't on the device"
    The obvious substitute for a scheduler is a shuffled deck, and it doesn't
    exist: CircuitPython has no `random.shuffle`, `random.choices`,
    `random.sample` or `random.gauss` — only `random`, `uniform`, `randint`,
    `randrange`, `getrandbits`, `choice` and `seed`. Code that shuffles works in
    the simulator and raises `AttributeError` on the board. `ActScheduler` uses
    nothing but `random.random()`, and gives you the no-repeat behaviour a
    shuffle doesn't.

### Where the loop lives

The demo makes the sign a `DisplayContent` whose `render()` advances **exactly
one frame** and returns. The library's display loop calls it once per frame on
both platforms, `run_headless` drives that same loop deterministically, and
nothing has to know whether it is on a laptop or a board:

```python
async def render(self, display):
    if not self._built:
        self.build(display)          # every bitmap, once
        self._begin("build")
        return
    self._f += 1
    ...
    if done:
        self._next()
```

Count frames; never read a clock. `DisplayContent(duration=None)` means
completion is never derived from elapsed time, so a slow frame can't cut an act
short and two runs of the same app produce the same pixels.

An app can also drive its own `while self.running:` loop inside `setup()` and
`await self.display.show()` per frame (that is how the Forge is written, and it
suits a long linear vignette). The trade: a `setup()` that never returns can't
be driven by `run_headless`, so you lose the one-line verification below.

---

## 6. Verify it — don't hope

```python
from scrollkit.dev import run_headless, validate

r = run_headless(PixelWordmarkDemo(), frames=300, strict=True,
                 screenshot="frame.png")
print(r.as_text())
print(validate(PixelWordmarkDemo()).as_text())
```

Four things to read, in order:

| Check | What it tells you |
|---|---|
| `r.is_blank` / `bright_pixels` | did anything light up at all — a mis-typed slot map renders nothing |
| `r.advanced` | did the picture change between the first and last frame — a sign that doesn't animate is a bug, not a style |
| the feasibility block | modeled ms/frame and FPS, from device measurements; **"No feasibility warnings"** is the verdict you want |
| `validate(app)` | structured issues with fixes — off-panel `y`, color name strings, RAM |

The demo's own verdict (after `random.seed(0)`, so the act order is fixed):

```
=== run_headless: 300 frames ===
  Rendered: yes (bright=396, lit=412, coverage=20.1%, advanced=True)
  Content: {'type': 'BrewSign', ..., 'act': 'brew', 'act_frame': 83, 'lit_pixels': 300}

=== Hardware feasibility: Adafruit MatrixPortal S3 (64x32) ===
  Confidence: MEASURED on device (measured on adafruit_matrixportal_s3, CircuitPython 9.1.0)
  Estimated hardware FPS: ~93.7   (median frame ~11 ms, worst ~11 ms)
  Per-frame cost (avg): pixel_writes 6.2 ms | refresh 4.5 ms | bulk_ops 0.0 ms
  Estimated peak RAM: 0 KB / 2024 KB budget
  No feasibility warnings.
```

`strict=True` turns the 50 ms budget into a wall — a sustained over-budget run
raises `FeasibilityError` instead of shipping. Override `describe()` on your
content so the harness can tell you *which act* was on screen; the demo reports
`act`, `act_frame` and `lit_pixels`, which is how you check that every act in a
scheduled show actually plays.

### Cost every act, not just the run

A scheduled sign shows a different act every few seconds, so a single
300-frame run samples whichever act it happened to land on. Force each act in
turn and read the model per act:

| Act | Modeled frame | Modeled FPS | What is on screen |
|---|---|---|---|
| `brew` | 10.67 ms | ~94 | wordmark + cup, 1 palette write |
| `sheen` | 10.67 ms | ~94 | partition + `VelvetSweep`, 10 palette writes |
| `rain` | 10.67 ms | ~94 | partition + `CipherRain`, 10 palette writes |
| `glow` | 20.99 ms | ~48 | **mask + backdrop**, 14 palette writes |

The odd one out is instructive. `glow` does no more animation work than the
others — but every lit or opaque pixel of every visible layer gets composited
each frame, and `glow` adds two full ink-box layers. That is why the demo sizes
its mask and backdrop to the word's bounding box rather than the panel: it cut
the modeled frame from 28.6 ms to 21.0 ms for an identical picture. **An opaque
full-panel layer is the one pixel-art construct that genuinely costs you.**

!!! note "What that line is, and isn't"
    The `pixel_writes` figure covers the simulator's own compositing pass, and
    its per-pixel constant is an engineering estimate rather than a device
    capture (`full_refresh_us`, the interpreted-write and bulk-op costs all are
    measured). The profile's own advice applies: trust the *relative* breakdown
    — which category dominates, and how a change moves it — more than the
    absolute FPS.

To look at it rather than measure it, run the simulator window — the art either
reads at 64×32 or it doesn't, and only your eyes decide that:

```bash
PYTHONPATH=src python demos/medium/pixel_wordmark.py
PYTHONPATH=src python demos/medium/pixel_wordmark.py --throttle   # at device speed
```

### Three rules that keep a sign reproducible

1. **Never read wall-clock time.** Count frames. `time.monotonic()` makes the
   same app render differently on a fast machine and a slow one, and
   `time.time()` isn't reliable on the device at all.
2. **Never derive an order from a `set`.** This has bitten this library for
   real: `swarm_reveal.py` built its delivery queue with `list(set(...))`, and
   the reveal came out in a different order on different Python builds. Sort
   first, or keep the order in a list.
3. **Never allocate in a frame.** Bitmaps, TileGrids, Groups, ramps, lists —
   build them in your build step. Allocation is tens of microseconds each plus
   the GC pause you pay for later.

---

## Checklist

Before you call a sign done:

- [ ] Every glyph and sprite is authored as ASCII rows with a `CHAR_TO_SLOT` map.
- [ ] Slot 0 is transparent; material slots are disjoint from logo slots.
- [ ] The wordmark's width arithmetic fits 64 px with the gaps you want.
- [ ] Every per-pixel loop runs in the build step, never in `render()`.
- [ ] Every per-frame change is a palette write, a `tile.x/y`, a `hidden` flag,
      or a library effect's `.step()` — never a redraw.
- [ ] The build and the exit come from the library — `DripReveal`, `SwarmReveal`,
      `show_reveal_splash` or a named transition. If you wrote your own reveal,
      delete it and use one of those.
- [ ] At least one act animates the whole mark through a `PalettePartition` and
      a treatment, rather than moving tiles around.
- [ ] At least three acts, family-tagged, picked through an `ActScheduler`.
- [ ] `run_headless(app, frames=300, strict=True)` reports `advanced=True` and
      no feasibility warnings.
- [ ] You have looked at it in the simulator window at 64×32.

## See also

- [The Forge Sign](../sample-project.md) — the full 24/7 application these
  conventions come from, with source.
- [Character Animation](character-animation.md) — pose cycles, mirroring,
  easing, and props for the subject sprite.
- [Palette Partitions & Treatments](palette-treatments.md) — the partition
  builders and all thirteen treatments.
- [Performance](performance.md) — the whole measured cost model.
- [Effects](effects.md) and [Transitions](transitions.md) — the builds and
  exits you don't have to write.
