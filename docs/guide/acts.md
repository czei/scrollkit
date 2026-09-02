# Marks & Acts

A sign is not one animation. It is a **mark** (the thing being shown) and a stream
of **acts** over it, where an act is three beats: **build, dwell, exit**. Reveal the
mark, hold it while something interesting happens to it, take it away. Then do it
again with a different three.

This page covers the two pieces that make that portable:
[`scrollkit.effects.mark`](#the-mark-pixelmark) gives you a mark when your app does
not already own one, and [`scrollkit.effects.acts`](#the-acts) gives you builds,
dwells and exits that work on *any* mark, including yours.

The palette treatments were already portable dwells, because
[a treatment](palette-treatments.md) takes a `PalettePartition` and nothing else.
Builds and exits were not: they got written inside the app that owned the mark and
reached straight into its tiles, its layout and its palette, so reusing one meant
copying it. `acts` is the missing half.

## The shortest thing that works

```python
from scrollkit.effects.mark import PixelMark
from scrollkit.effects.acts import play_sign

mark = PixelMark.from_text(display, "BLUE RIDGE COFFEE", y=12)
mark.attach(display)
await play_sign(mark.context(display), acts=4)
```

Four full build/dwell/exit cycles over a wordmark rendered from the display's own
font, with no art authored anywhere and no act written by you. That is deliberately
the first example: a deck of acts can be assembled and judged against a real
wordmark *before* anyone draws anything.

## The mark: `PixelMark`

Every build in `acts` has the same shape. Hide the mark, run an overlay that shows
its pixels arriving, then call `ctx.show()` to hand the real thing back and drop the
overlay. **That last step assumes something real is underneath.** An app that owns
its wordmark already has it, a set of glyph tiles it can un-hide. Without one, the
drops land, the overlay detaches, and the panel goes black while the act cheerfully
returns `True`.

`PixelMark` is the minimal version: lit cells and their colours in, one bitmap, one
palette and one tile out.

```python
from scrollkit.effects.mark import PixelMark

# From the display's own font.
mark = PixelMark.from_text(display, "OPEN", x=4, y=10, color=0xFFB030)

# Or from ASCII art, in the format pixel art is already authored in.
OWL = ("..###..",
       ".#o.o#.",
       "..###..")
mark = PixelMark.from_art(OWL, {"#": 0xFFB030, "o": 0x102030}, x=20, y=8)

mark.attach(display)          # builds the layer and adds it, HIDDEN
```

| Member | What it does |
|---|---|
| `PixelMark(cells, colors=None, color=None)` | `cells` is `{(x, y): index}` or any iterable of `(x, y)`. A mapping colours each cell from `colors`; a bare iterable is one flat `color`. |
| `.from_text(display, text, x=0, y=0, scale=1, color=None)` | A mark from a line of text in `display.font`. |
| `.from_art(rows, chars, x=0, y=0)` | A mark from rows of characters plus `{character: 0xRRGGBB}`. |
| `.attach(display)` | Build the layer, add it, leave it hidden. Returns `self`. |
| `.tile` | The mark's `TileGrid`, or `None` before `attach`. Read-only. |
| `.show()` / `.hide()` | Flip `tile.hidden`. |
| `.detach()` | Remove the layer. |
| `.context(display=None, frame=None)` | A [context](#the-context) wired to this mark. |

Four behaviours here are decisions rather than defaults, and each one is the answer
to a way signs actually break:

- **It attaches hidden.** Every act's first move is to clear the panel, so attaching
  visible would flash the finished mark for one frame before the act that assembles
  it begins.
- **An unmapped character in `from_art` is a hole, not a guess.** That is how `.`
  and the space character become background without being special-cased, and it
  means a character nobody defined leaves a gap rather than putting a shape on the
  panel its author never drew. (`normalize_art` in [`utils.pixel_art`](pixel-art.md) takes the
  opposite view, for a different job: repairing a typo at import, where substituting
  transparent would silently delete a sprite.)
- **Index 0 is never lit.** `0` means "no ink here" in ASCII art and slot 0 of the
  built palette is reserved for transparency, so a cell carrying 0 is skipped.
  Lighting it would give every mark a rectangular background.
- **Off-panel cells are dropped, not raised on.** Art is authored by hand, and a
  wordmark placed one column too far right should not take the sign down.

`from_art` builds the palette from the colours actually used, in first-seen order,
so a mark carries what it needs rather than everything the art module happened to
define.

### A mark is a thing that moves

`.tile` is exposed because the [image animators](effects.md#image-animators) take a
`TileGrid`, and a host flying a mark along a path had no way to get one without
reaching into a private attribute:

```python
from scrollkit.effects.image_animators import MotionAnimator

fly = MotionAnimator(path="point_to_point", from_xy=(-30, 4), to_xy=(6, 12),
                     frames=40, curve="ease_out_quad")
fly.start(display, mark.tile, None, None, None)
```

Position the mark with `tile.x` / `tile.y`. The cells themselves are fixed at
`attach` time.

## The acts

An act is handed a context and knows nothing else. Every one returns `True` if it
ran to completion and `False` if it stopped early, and every one detaches whatever
it attached, **including on the early exit**, because otherwise the overlay outlives
the act and the next one starts on a panel it did not draw.

| Act | Kind | What it looks like |
|---|---|---|
| `swarm_build(ctx, ...)` | build | A flock carries the mark into place, pixel by pixel. |
| `drip_in(ctx, direction="top", ...)` | build | The mark's pixels rain in from an edge; the true colours arrive as the last drop lands. |
| `wink_in(ctx, ...)` | build | Every LED lights, then everything that is not the mark winks off. |
| `reveal_via(ctx, transition="Iris Snap")` | build | A screen transition covers the panel, the mark appears behind it, it uncovers. |
| `treatment_dwell(ctx, treatment="VelvetSweep", ramp=None, groups=10)` | dwell | A [palette treatment](palette-treatments.md) animates the mark in place. |
| `hide_via(ctx, transition="Pixel Dissolve")` | exit | The same transitions, taking the mark away. |
| `swarm_unbuild(ctx, ...)` | exit | The flock carries the mark off again. |

Seven functions, and they are not seven choices. `reveal_via` and `hide_via` each
take any of **12** transition names and `treatment_dwell` takes any of **11**
treatments, so the menu is [39 entries](#the-menu-selectable) wide.

```python
from scrollkit.effects.acts import drip_in, treatment_dwell, hide_via

ctx = mark.context(display)
await drip_in(ctx, direction="bottom")
await treatment_dwell(ctx, treatment="HaloPulse")
await hide_via(ctx, transition="CRT Collapse")
```

Look them up by name the same way you look up a transition:

```python
from scrollkit.effects.acts import act_factory, supported_acts

supported_acts()          # ('swarm', 'drip', 'wink', 'reveal', 'treatment', 'unswarm', 'hide')
supported_acts("build")   # ('swarm', 'drip', 'wink', 'reveal')
ok = await act_factory("drip")(ctx, direction="bottom")
```

`act_factory` returns `None` for a name it does not know rather than raising,
matching `transition_factory`: the caller decides whether an unknown name is a typo
or a feature it does not have yet.

### The context

Duck-typed on purpose. An app already has these under its own names, and should not
have to inherit anything to use an act. Six are required; `colors` is optional:

| Name | What it is |
|---|---|
| `ctx.slots` | The mark's lit cells: `{(x, y): palette index}`, or any iterable of `(x, y)`. |
| `ctx.colors` | Optional. The ramp those indices point into, low to high. |
| `ctx.display` | The display to `start()` an effect against. |
| `ctx.running` | Falsy means the sign is stopping, and the act must return early. |
| `await ctx.frame()` | Present one frame. `False` means the surface went away, and the return value is not advisory. |
| `ctx.show()` | Put the mark on screen in its final place. |
| `ctx.hide()` | Clear the mark and anything layered over it. |

`SimpleContext` is the smallest thing that satisfies it, and `PixelMark.context()`
builds one for you. An app with its own tiles should pass **itself**:

```python
class MySign:
    slots = ...            # {(x, y): 1}
    colors = (0x70140E, 0xB02318, 0xE65A28)
    running = True

    def show(self):  self._show_logo()
    def hide(self):  self._hide_all()
    async def frame(self): return await self.display.show() is not False

await drip_in(self)        # the sign IS the context
```

!!! warning "Per-pixel indices are meaningless without a ramp"
    `SwarmReveal` raises on an `index_map` with no `text_colors` rather than
    guessing, and it is right to: a guessed palette is a sign in colours nobody
    chose. A context with slots but no `colors` gets a flat reveal, which is correct
    and is what a one-tone mark wanted anyway.

## The menu: `selectable()`

`selectable()` returns the menu, **one entry per choice rather than per function**.
A person picking from a list picks "Iris Snap", not "reveal_via with
transition=Iris Snap", so the expansion happens once, where the acts are, instead of
in every caller.

```python
from scrollkit.effects.acts import selectable

for name, kind, family, act, options in selectable():
    ...
```

39 entries: **15 builds** (12 transitions plus swarm, drip and wink), **11 dwells**
(one per driveable treatment), **13 exits** (12 transitions plus unswarm). Compose
one of each and that is 2,145 distinct acts out of seven functions and one drawing.

`family` is what the entry *looks like*, and it is where the judgement lives. Two
entries sharing a family are similar enough that the
[scheduler](utils.md#actscheduler-090) will not play them back to back. **A treatment's
family is its partition**, because two treatments animating the same grouping of
pixels genuinely do look alike, and that is the distinction a viewer makes. Eleven
treatments collapse to nine families. A transition is its own family, which is the
honest answer when nobody has grouped them by eye.

## The whole sign: `play_sign()`

```python
from scrollkit.effects.acts import play_sign

played = await play_sign(ctx)                       # until ctx.running goes false
played = await play_sign(ctx, acts=4)               # exactly four cycles
played = await play_sign(ctx, chosen=["Iris Snap", "HaloPulse", "exit:CRT Collapse"])
```

`play_sign` draws build, dwell and exit from an `ActScheduler` and repeats. That is
what a sign IS in this design: **a deck is chosen and the order is not.** The
scheduler leads with the least-recently-seen entry and never plays two of a family
back to back, which is why a panel running this for a week does not visibly loop.
It returns the number of complete cycles played.

Pass your own `scheduler=` to share age bookkeeping with the rest of your show.

!!! note "A choice is a kind **and** a name"
    Every transition is both a build and an exit, so `chosen=["Pixel Dissolve"]`
    selects it in *both* decks. Someone who kept "Pixel Dissolve" to end on did not
    thereby ask for it to open with. Write `"exit:Pixel Dissolve"` to say the thing
    you meant. A bare name still selects every kind it appears in, which is the
    forgiving reading when nobody has said otherwise.

    A name that is not on the menu is ignored rather than raising, because a deck is
    a preference and one stale entry should not stop a sign. A deck with **no exit**
    is refused outright: a sign that ended mid-build leaves the panel in a state no
    act chose.

## What is refused, and why

A menu entry that cannot work is worse than an absent one, and a silent no-op is
worse than both. Four things are therefore missing on purpose:

- **`Drop from Sky` is not a driveable transition.** `transitions_available()`
  returns 12 of the 13 names in `supported_names()`. Drop from Sky is a different
  thing wearing the same word: it hooks `pre_render_hook` and animates a content
  `Label`'s x/y through the display process, so its `start()` never calls the swap
  callback and a mark handed to it stays hidden while the act reports success.
  Anything carrying that hook is excluded.
- **`RouteCircuit` and `PacketTrace` are not driveable dwells.**
  `treatments_available()` returns 11 of 13. Both want `map_route`, which needs a
  mark's glyph stroke paths and terminus pixels. That is app knowledge, and it is
  not derivable from a set of cells.
- **A treatment wanting arguments this module cannot invent is dropped.** Only `lo`
  and `hi` are servable (`GradientDwell` wants them, and the ramp's ends are the
  obvious answer). The check reads the live `__init__` signature, so it cannot drift.
- **`point_to_point` with no endpoints raises** rather than quietly travelling from
  `(0, 0)` to `(0, 0)`. A move that goes nowhere is the failure mode with nothing to
  read.

One thing is resampled rather than refused. **A treatment theme is exactly five
stops**, because every treatment class unpacks `base, dim, flat, warm, hot`. A
mark's palette is however many colours its art needed, so `treatment_dwell`
resamples to five with the endpoints kept. Refusing would mean "your wordmark has
six colours, so you may not have a heat sweep", which is not a rule anyone would
accept.

## Cost

The builds and exits walk a prebuilt schedule for a handful of writes a frame, and
`treatment_dwell` does **zero** pixel writes: a `PalettePartition` groups the mark's
own pixels once and the treatment animates the groups by rewriting N palette
entries. That is why a sign can afford a dozen dwells.

`num_birds` is the one real feasibility knob, on `swarm_build` / `swarm_unbuild`:
per-frame cost grows with its **square**, because of the boids neighbour pass.

Verify a whole show, not one act, since a scheduled sign shows a different act every
few seconds:

```python
from scrollkit.dev import run_headless
result = run_headless(app, frames=600, strict=True)   # FeasibilityError if it busts
```

## See also

- [Pixel Art](pixel-art.md) for authoring the art a mark is made from.
- [Palette Partitions & Treatments](palette-treatments.md) for what the dwells are.
- [Theatrical Transitions](transitions.md) for the 13 names the builds and exits wrap.
- [Utilities](utils.md#actscheduler-090) for the scheduler `play_sign` draws with.
- `docs/sample-project.md` for a full application built this way.
