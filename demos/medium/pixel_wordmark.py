#!/usr/bin/env python3
"""ScrollKit demo (MEDIUM) — a pixel-art wordmark sign.

The worked example for the Pixel Art guide (``docs/guide/pixel-art.md``): a shop
sign that draws its OWN letterforms instead of using the built-in font, and
animates them without writing a single pixel after startup.

  * BREW is four hand-drawn glyphs, authored 5x7 and ``scale2``-d to 10x14 so
    every stroke lands exactly 2 px wide.
  * The cup is a subject sprite on its own material palette slots, so no effect
    running over the wordmark can ever recolor the ceramic.
  * Four acts — brew, sheen, rain, glow — rotate through an ``ActScheduler`` so
    the sign never plays the same visual family twice running.

Every per-pixel loop runs once, in ``build()``. After that a frame costs a
handful of palette writes and two ``hidden`` flags.

    PYTHONPATH=src python demos/medium/pixel_wordmark.py     # a window
    python demos/render_gifs.py pixel_wordmark               # a GIF

The same code runs unchanged on an Adafruit MatrixPortal S3.
"""

import sys
import os

try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    import _demo_support as _support
except (AttributeError, ImportError):
    _support = None

import asyncio

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.colors import multi_gradient
from scrollkit.display.content import DisplayContent
from scrollkit.effects.drip_splash import DripReveal
from scrollkit.effects.palette_partition import (
    PalettePartition, map_diagonal, map_rain,
)
from scrollkit.effects.palette_treatments import CipherRain, VelvetSweep
from scrollkit.utils.pixel_art import normalize_all, normalize_art
from scrollkit.utils.scheduler import ActScheduler

# --- the palette: one table, partitioned by role ----------------------------
# Slots 1-3 are LOGO colors (anything may animate them); slots 4-5 are MATERIAL
# shades used only by the cup, so a treatment sweeping the wordmark can never
# repaint the ceramic. Slot 0 is transparent — a sprite is a silhouette.
CHAR_TO_SLOT = {".": 0, " ": 0, "#": 1, "o": 2, "w": 3, "s": 4, "d": 5}
BRAND = 0xFFB020        # 1 '#'  the wordmark
COFFEE = 0x8A3A10       # 2 'o'  the hot surface (palette-cycled)
CREAM = 0xFFF0D0        # 3 'w'  steam and highlights
CERAMIC = 0xE8E4DC      # 4 's'  the cup body
SHADOW = 0x6A6058       # 5 'd'  rims and shadow
PALETTE_COLORS = (0x000000, BRAND, COFFEE, CREAM, CERAMIC, SHADOW)

# Ramps built once at import — never inside a frame.
COFFEE_RAMP = multi_gradient((0x4A1C06, 0xB04C14, 0xE88A28), 12)
GLOW_BANDS = multi_gradient((0x2A1204, 0xE88A28, 0x2A1204), 14)
# The 5-stop treatment theme: (base, dim, flat, warm, hot), darkest first.
THEME = (0x7A4A08, 0xA8700F, BRAND, 0xFFD070, 0xFFF6D8)

# --- the letterforms --------------------------------------------------------
# Authored small (5x7, 1 px strokes) and doubled, so the strokes come out
# uniformly 2 px instead of aliasing. Editing the art is editing text.
CAPS7 = {
    "B": ("####.",
          "#...#",
          "#...#",
          "####.",
          "#...#",
          "#...#",
          "####."),
    "R": ("####.",
          "#...#",
          "#...#",
          "####.",
          "#.#..",
          "#..#.",
          "#...#"),
    "E": ("#####",
          "#....",
          "#....",
          "####.",
          "#....",
          "#....",
          "#####"),
    "W": ("#...#",
          "#...#",
          "#.#.#",
          "#.#.#",
          "#.#.#",
          "##.##",
          ".#.#."),
}

# The cup, 15x10: dark rim, the hot surface, ceramic walls, a handle, a saucer.
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

# Two steam cels, 8x3. Swapping which one is hidden IS the animation.
STEAM_A = (".w..w...",
           "w..w....",
           ".w..w...")
STEAM_B = ("w..w....",
           ".w..w...",
           "w..w....")


def scale2(rows):
    """Integer 2x scale: every pixel becomes 2x2 (uniform doubled strokes)."""
    out = []
    for row in rows:
        wide = "".join(ch + ch for ch in row)
        out.append(wide)
        out.append(wide)
    return out


# Repair the two authoring typos at import: a ragged row (which throws
# IndexError from inside the conversion loop) and a character never mapped to a
# slot (KeyError). Both are named and reported rather than fatal -- a sign that
# draws with one odd-colored pixel beats a sign that refuses to start.
CAPS7 = normalize_all(CAPS7, CHAR_TO_SLOT)
CUP = normalize_art(CUP, CHAR_TO_SLOT, name="CUP")
STEAM_A = normalize_art(STEAM_A, CHAR_TO_SLOT, name="STEAM_A")
STEAM_B = normalize_art(STEAM_B, CHAR_TO_SLOT, name="STEAM_B")


# --- the layout: placements as data -----------------------------------------
# BREW = 4 glyphs x 10 px + 3 gaps x 2 px = 46 px, centred at x = 9.
WORD = "BREW"
WORD_X, WORD_Y, WORD_H = 9, 2, 14
GLYPHS = tuple((ch, WORD_X + i * 12, WORD_Y) for i, ch in enumerate(WORD))
CUP_XY = (24, 19)
STEAM_XY = (28, 16)


def _ease_out(t):
    """Cubic ease-out on t in 0..1 — decelerating arrivals."""
    inv = 1.0 - t
    return 1.0 - inv * inv * inv


def word_slots():
    """Every lit pixel of the assembled wordmark: {(x, y): slot}."""
    slots = {}
    for ch, gx0, gy0 in GLYPHS:
        for gy, row in enumerate(scale2(CAPS7[ch])):
            for gx, c in enumerate(row):
                if CHAR_TO_SLOT[c]:
                    slots[(gx0 + gx, gy0 + gy)] = CHAR_TO_SLOT[c]
    return slots


class BrewSign(DisplayContent):
    """The sign itself: prebuilt art plus a frame-stepped act machine.

    ``render()`` advances exactly one frame and never touches a pixel — the
    library's display loop calls it once per frame on both platforms, and
    ``scrollkit.dev.run_headless`` drives that same loop deterministically.
    """

    # (name, family) — the scheduler refuses to pick the family that just ran.
    DWELL_ACTS = (("brew", "subject"), ("sheen", "sweep"),
                  ("rain", "fall"), ("glow", "mask"))
    BREW_FRAMES = 88
    GLOW_FRAMES = 84

    def __init__(self):
        # duration=None: completion is never derived from the wall clock. The
        # sign is a persistent banner and counts its own frames.
        DisplayContent.__init__(self, duration=None)
        self._slots = word_slots()
        self._sched = ActScheduler()
        self._act = None
        self._family = None
        self._f = 0
        self._built = False

    # -- one-time construction ------------------------------------------------
    def _tile(self, display, rows, x=0, y=0):
        """ASCII rows -> Bitmap -> TileGrid, added hidden. Build-time only.

        Sized from the LONGEST row, never ``rows[0]``: one row a character
        longer than the first is the commonest pixel-art bug there is, and
        sizing off row 0 turns it into an IndexError deep in this loop."""
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

    def build(self, display):
        """Every bitmap this sign will ever show, allocated once."""
        gfx = display.gfx
        self._palette = gfx.Palette(len(PALETTE_COLORS))
        for i, color in enumerate(PALETTE_COLORS):
            self._palette[i] = color
        self._palette.make_transparent(0)

        self.glyphs = [self._tile(display, scale2(CAPS7[ch]), x, y)
                       for ch, x, y in GLYPHS]
        self.cup = self._tile(display, CUP, CUP_XY[0], CUP_XY[1])
        self.steam = [self._tile(display, STEAM_A, *STEAM_XY),
                      self._tile(display, STEAM_B, *STEAM_XY)]

        # The glow act's two layers, sized to the word's INK BOX — every lit or
        # opaque pixel on screen is composited every frame, so a full-panel
        # layer is the one pixel-art construct that really does cost you.
        xs = [p[0] for p in self._slots]
        x0, w = min(xs), max(xs) - min(xs) + 1

        # The backdrop: one striped row per palette slot, built with C bulk
        # fills. It never moves — rotating its palette scrolls the stripes.
        back = gfx.Bitmap(w, WORD_H, WORD_H + 1)
        for y in range(WORD_H):
            gfx.bitmaptools.fill_region(back, 0, y, w, y + 1, 1 + y)
        self._back_pal = gfx.Palette(WORD_H + 1)
        self._back_pal.make_transparent(0)
        self.backdrop = gfx.TileGrid(back, pixel_shader=self._back_pal)
        self.backdrop.x, self.backdrop.y = x0, WORD_Y
        self.backdrop.hidden = True
        display.add_layer(self.backdrop)

        # The wordmark as a WINDOW: opaque black over the ink box, with the
        # letters punched transparent. One fill, then one write per lit pixel.
        mask = gfx.Bitmap(w, WORD_H, 2)
        mask.fill(1)
        for (x, y) in self._slots:
            mask[x - x0, y - WORD_Y] = 0
        mask_pal = gfx.Palette(2)
        mask_pal.make_transparent(0)
        mask_pal[1] = 0x000000
        self.mask = gfx.TileGrid(mask, pixel_shader=mask_pal)
        self.mask.x, self.mask.y = x0, WORD_Y
        self.mask.hidden = True
        display.add_layer(self.mask)

        # Two partitions of the same pixels — a static index map each, animated
        # by rewriting group colors. Zero per-frame pixel work.
        self._fx = {}
        for name, builder in (("sheen", map_diagonal), ("rain", map_rain)):
            group_map, n = builder(self._slots, 10)
            fx = PalettePartition(gfx, self._slots, group_map, n)
            display.add_layer(fx.tile)
            self._fx[name] = fx
        self._built = True

    # -- act plumbing ---------------------------------------------------------
    def _hide_word(self):
        """Hide every wordmark layer. The cup and its steam are NOT touched:
        the subject keeps living while the acts play over the letters."""
        for tile in self.glyphs:
            tile.hidden = True
        self.backdrop.hidden = self.mask.hidden = True
        for fx in self._fx.values():
            fx.tile.hidden = True

    def _show_word(self):
        for tile in self.glyphs:
            tile.hidden = False

    def _begin(self, act, family=None):
        self._act = act
        self._family = family
        self._f = 0
        self._hide_word()
        self._treatment = None
        self._palette[2] = COFFEE        # undo whatever the last act cycled to
        if act == "build":
            self.cup.hidden = True
            for tile in self.steam:
                tile.hidden = True
            self._drip = DripReveal(list(self._slots), color=BRAND,
                                    fall_speed=2, stagger=1)
            self._drip.start(self._display)
            return
        self._show_word()
        if act == "sheen" or act == "rain":
            fx = self._fx[act]
            fx.fill(BRAND)                  # the invisible swap: same pixels,
            fx.tile.hidden = False          # same color, one layer deeper
            for tile in self.glyphs:
                tile.hidden = True
            self._treatment = (VelvetSweep(fx, THEME, sweeps=60) if act == "sheen"
                               else CipherRain(fx, THEME, frames=90))
        elif act == "glow":
            for tile in self.glyphs:
                tile.hidden = True          # the mask's holes ARE the word
            self._step_glow(0)              # paint frame 0 before it is shown
            self.backdrop.hidden = self.mask.hidden = False

    def _next(self):
        name, family = self._sched.pick(self.DWELL_ACTS, "dwell",
                                        avoid={self._family})
        self._begin(name, family)

    # -- the acts, one frame each --------------------------------------------
    def _step_build(self, f):
        """The cup rises on an ease-out, then the wordmark drips in above it."""
        if f <= 10:
            self.cup.hidden = False
            self.cup.y = int(round(32 + (CUP_XY[1] - 32) * _ease_out(f / 10.0)))
            return False
        if self._drip.step():
            self._drip.detach()
            self._show_word()
            return True
        return False

    def _step_brew(self, f):
        """Cycle the coffee's heat through its ramp: ONE palette write."""
        i = f % 22
        self._palette[2] = COFFEE_RAMP[i if i < 12 else 22 - i]
        return f >= self.BREW_FRAMES

    def _step_treatment(self):
        """One frame of a palette treatment; it reports its own end."""
        t = self._treatment
        t.step()
        if t.is_complete:
            self._fx[self._act].tile.hidden = True
            self._show_word()
            return True
        return False

    def _step_glow(self, f):
        """Scroll the stripes behind the wordmark window — by ROTATING the
        backdrop's palette, so the tile itself never moves and can never bleed
        past the mask. WORD_H palette writes, zero pixel writes."""
        n = len(GLOW_BANDS)
        for i in range(n):
            self._back_pal[1 + i] = GLOW_BANDS[(i + f) % n]
        return f >= self.GLOW_FRAMES

    # -- DisplayContent contract ---------------------------------------------
    async def render(self, display):
        if not self._built:
            self._display = display
            self.build(display)
            self._begin("build")
            return
        self._f += 1
        f = self._f
        if self._act != "build":            # the steam never stops: cel swap,
            up = (f // 4) % 2 == 0          # two `hidden` flags a frame
            self.steam[0].hidden = not up
            self.steam[1].hidden = up
        if self._act == "build":
            done = self._step_build(f)
        elif self._act == "brew":
            done = self._step_brew(f)
        elif self._act == "glow":
            done = self._step_glow(f)
        else:
            done = self._step_treatment()
        if done:
            self._next()

    def describe(self):
        d = DisplayContent.describe(self)
        d.update({"word": WORD, "act": self._act, "act_frame": self._f,
                  "lit_pixels": len(self._slots)})
        return d


class PixelWordmarkDemo(ScrollKitApp):
    """A 64x32 sign built entirely from hand-drawn pixel art."""

    def __init__(self):
        super().__init__(enable_web=False, update_interval=3600)

    async def create_display(self):
        if _support is not None:
            return _support.simulator_display(getattr(self, "opts", None))
        try:
            from scrollkit.display.simulator import SimulatorDisplay
            return SimulatorDisplay(width=64, height=32)
        except ImportError:
            return await super().create_display()

    async def setup(self):
        if hasattr(self.display, "create_window"):
            await self.display.create_window("Pixel Wordmark (medium)")
        self.content_queue.add(BrewSign())


if __name__ == "__main__":
    if _support is not None:
        _support.main(PixelWordmarkDemo(), "ScrollKit pixel-art wordmark (medium)")
    else:
        asyncio.run(PixelWordmarkDemo().run())
