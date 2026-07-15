#!/usr/bin/env python3
"""ScrollKit demo (HARD): the showcase reel — every effect, named as it plays.

An endless self-driving teaser that mixes the whole toolbox, act by act, and
NAMES each effect as it shows it: the swarm assembles the word SWARM, a velvet
sheen sweeps across VELVET, IRIS irises in and out. Watching the reel doubles
as a table of contents for the per-effect tutorials in the docs.

What plays (scheduled so nothing similar ever runs twice in a row):

  builds / exits   all 13 theatrical transitions — each gets a named act
                   (build, a true screen-to-screen content swap, exit), and
                   six double as anonymous wipes around the dwells
  dwells           all 13 palette treatments, run on a partitioned word
  splashes         reveal wink, drip, swarm (both directions), swirl
  interstitials    KineticMarquee, WaveRider, the 5 bitmap-text palette
                   effects, a cel-animated flying owl, a zigzag bee
  garnish          Sparkle / Snow / Ember particles behind a held word
  scheduling       ActScheduler — weighted-age, family-tagged decks, plus a
                   rotating color theme, so a 24/7 loop never feels repetitive

Characters: the flying owl (art borrowed from the DarkOwl desk-sign app whose
palette effects were promoted into this library) opens the show by air-dropping
the letters of SCROLLKIT and later sweeps back to collect them; a striped bee
zigzags between acts. Their sprite code is the worked example for
docs/guide/character-animation.md.

Run on desktop (opens a pygame window):

    python demos/hard/showcase_reel.py
    python demos/hard/showcase_reel.py --throttle   # crawl at real device speed
    python demos/hard/showcase_reel.py --strict     # hard feasibility gate

    # Jump the queue: play these acts first, then let the scheduler take over
    # (any act name from the deck — swarm, velvet, iris, cipher, drip, ...).
    python demos/hard/showcase_reel.py swarm iris glitch

The same code runs unchanged on an Adafruit MatrixPortal S3.
"""

import sys
import os

# Desktop-only path setup + shared demo CLI plumbing (absent on CircuitPython,
# where os.path doesn't exist and the app runs with defaults).
try:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
    import _demo_support as _support
except (AttributeError, ImportError):
    _support = None

import asyncio
import math
import random

from scrollkit.app.base import ScrollKitApp
from scrollkit.display.unified import displayio
from scrollkit.display.bitmap_text import (
    BitmapText, RainbowChase, MonoChase, NeonTubeCrawl, ChromeSheen,
    HazardStripes,
)
from scrollkit.effects.drip_splash import DripReveal
from scrollkit.effects.particles import ParticleEngine, Sparkle, Snow, Ember
from scrollkit.effects.reveal_splash import show_reveal_splash, pixels_from_text
from scrollkit.effects.scrolling import KineticMarquee, WaveRider, SplitFlap
from scrollkit.effects.swarm_reveal import SwarmReveal
from scrollkit.effects.swirl_in import SwirlIn
from scrollkit.effects.transitions import transition_factory
from scrollkit.effects.palette_partition import (
    PalettePartition,
    bfs_paths,
    map_anchor_distance,
    map_angle,
    map_checker,
    map_diagonal,
    map_exposure,
    map_radial,
    map_rain,
    map_regions,
    map_route,
    map_topology,
)
from scrollkit.effects.palette_treatments import (
    AnchorWake,
    CipherRain,
    EclipseCross,
    GradientDwell,
    HaloPulse,
    HeatmapDrift,
    InkShimmer,
    PacketTrace,
    RimLight,
    RouteCircuit,
    SonarSweep,
    StrokeAnatomy,
    VelvetSweep,
)
from scrollkit.utils.scheduler import ActScheduler

# ---------------------------------------------------------------------------
# Character art. Every sprite is a list of equal-length ASCII rows; each
# character maps to a palette slot. The sprites get their OWN palette, so no
# word treatment can ever recolor a character mid-flight.
#
# The owls are borrowed from the DarkOwl LED-logo app (the desk sign this
# library's palette-partition effects were promoted from). The bee is new.
# ---------------------------------------------------------------------------

SPRITE_CHARS = {".": 0, "#": 1, "o": 2, "w": 3, "d": 4, "h": 5, "b": 6}
SPRITE_COLORS = (
    0x000000,   # 0 transparent
    0xB02318,   # 1 '#' brick red (body base)
    0xFFB030,   # 2 'o' amber (eyes, beak, bee stripes)
    0xFFF1D8,   # 3 'w' warm white (catchlights, wings)
    0x571007,   # 4 'd' dark plumage / bee bands
    0xD4481E,   # 5 'h' hot underside
    0xE8873C,   # 6 'b' tawny buff (facial disc, bee head)
)

# Small flying owl, side view facing LEFT, two wing poses (a simple flap).
OWL_FLY_UP = (
    "..........#...",
    ".........##...",
    "........##....",
    ".#.#...##.....",
    ".###..##....#.",
    "o#w##########.",
    ".############.",
    "..............",
    "..............",
    "..............",
)
OWL_FLY_DOWN = (
    "..............",
    "..............",
    "..............",
    ".#.#..........",
    ".###........#.",
    "o#w##########.",
    ".############.",
    "......##......",
    ".......##.....",
    "........#.....",
)

# The BIG interstitial owl (24x16, facing LEFT) — three wing poses for a true
# cel flap cycle: UP, MID (glide), DOWN. Owl proportions: big round head into a
# stocky egg body, SHORT fan tail, broad wings, shaded plumage.
BIG_OWL_UP = (
    ".............ddddd......",
    "..........b#####dd......",
    "..#..#...b#####dd.......",
    ".######.b#####dd........",
    ".############dd.........",
    "bboob#########..........",
    "obwob#########dddd......",
    ".wwb##############h.....",
    "..hh##########hhh.......",
    "...hhhhhhhhhh...........",
    ".....bhhhb..............",
    "......o.o...............",
    "........................",
    "........................",
    "........................",
    "........................",
)
BIG_OWL_MID = (
    "........................",
    "........................",
    "..#..#...dddddddddd.....",
    ".######.b##########dd...",
    ".#######b#########dd....",
    "bboob####hhhhhhhdd......",
    "obwob#########dddd......",
    ".wwb##############h.....",
    "..hh##########hhh.......",
    "...hhhhhhhhhh...........",
    ".....bhhhb..............",
    "......o.o...............",
    "........................",
    "........................",
    "........................",
    "........................",
)
BIG_OWL_DOWN = (
    "........................",
    "........................",
    "..#..#..................",
    ".######.................",
    ".#######dddddd..........",
    "bboob#########..........",
    "obwob#########dddd......",
    ".wwb##############h.....",
    "..hh##########hhh.......",
    "...hhhhhhhhhhb###d......",
    ".....bhhhb..b####d......",
    "......o.o...b###dd......",
    "............####d.......",
    ".............ddd........",
    "........................",
    "........................",
)

# The bee (13x7, facing RIGHT): amber body with hot-orange bands, a white
# eye up front, a tapered tail-stinger, white wings in two poses (raised /
# swept back). Bands use the hot shade, not dark — dark-on-black vanishes.
BEE_UP = (
    "....www......",
    "...wwwww.....",
    "....ww.......",
    "...ohhoohhow.",
    "hhoohhoohhoo.",
    "...ohhoohho..",
    ".............",
)
BEE_DOWN = (
    ".............",
    ".............",
    ".wwww........",
    "...ohhoohhow.",
    "hhoohhoohhoo.",
    "...ohhoohho..",
    ".............",
)

# ---------------------------------------------------------------------------
# Color themes. Each is a 5-stop ramp (base, dim, flat, warm, hot) — the shape
# every palette treatment expects; the word itself is shown at the flat stop.
# Panel color is RGB444: adjacent stops differ in a channel's top nibble or
# they'd quantize to the same LED color.
# ---------------------------------------------------------------------------

THEMES = (
    ("lagoon",  (0x083038, 0x105058, 0x18888C, 0x30B8B0, 0x70E8D8)),
    ("amber",   (0x502008, 0x804010, 0xB06018, 0xD88820, 0xF8B840)),
    ("orchid",  (0x400830, 0x701048, 0xA02060, 0xC84080, 0xE870A8)),
    ("meadow",  (0x083810, 0x106018, 0x209020, 0x40C030, 0x88E858)),
    ("glacier", (0x102848, 0x184870, 0x2870A0, 0x48A0D0, 0x88D0F0)),
)

BIRD_COLOR = 0xFFCC66               # the swarm flock, a warm pale amber
NUM_BIRDS = 18                      # device-safe (<= ~20 on an S3)
PACKET_COLOR = 0xFFB030             # PacketTrace sprites, visible on any theme

# Anonymous build/exit wipes around the named dwells (an aesthetic split —
# any transition can do both). Named transition acts cover all 13.
BUILD_TRANSITIONS = (
    ("slit-in", "sweep", "Light Slit"),
    ("iris-in", "radial", "Iris Snap"),
    ("mosaic-in", "texture", "Mosaic Resolve"),
    ("gradual-in", "sweep", "Gradual Reveal"),
    ("venetian-in", "bands", "Venetian Shutters"),
    ("scan-in", "bands", "Scan Fold"),
)
EXIT_TRANSITIONS = (
    ("crt-out", "collapse", "CRT Collapse"),
    ("dissolve-out", "texture", "Pixel Dissolve"),
    ("glitch-out", "bands", "Glitch Bars"),
    ("rain-out", "fall", "Column Rain"),
    ("diag-out", "sweep", "Diagonal Wipe"),
    ("wipe-out", "sweep", "Horizontal Wipe"),
)


def _mirror(rows):
    """The sprite flipped left-to-right (index loop — CircuitPython has no
    extended slices, so rows[::-1]-style tricks are off the table)."""
    out = []
    for row in rows:
        out.append("".join(row[len(row) - 1 - j] for j in range(len(row))))
    return out


def _ease_out(t):
    """Cubic ease-out on t in 0..1 (decelerating arrivals)."""
    inv = 1.0 - t
    return 1.0 - inv * inv * inv


def _ease_in(t):
    """Cubic ease-in on t in 0..1 (accelerating departures and dives)."""
    return t * t * t


class _Pos:
    """A minimal x/y stand-in DropFromSky can animate (it moves content
    coordinates rather than painting an overlay)."""

    def __init__(self, x, y):
        self.x = x
        self.y = y


class ShowcaseReelApp(ScrollKitApp):
    """The ScrollKit teaser reel: every effect, announced by the word it plays on."""

    def __init__(self, force_acts=()):
        super().__init__(enable_web=False, update_interval=3600)
        self._theme = THEMES[0][1]
        self._force_queue = list(force_acts)   # act names to play first

    async def create_display(self):
        if sys.implementation.name == "circuitpython":
            from scrollkit.display.unified import UnifiedDisplay
            return UnifiedDisplay(width=64, height=32)   # auto-detects the panel
        if _support is not None:
            return _support.simulator_display(getattr(self, "opts", None))
        from scrollkit.display.simulator import SimulatorDisplay
        return SimulatorDisplay(width=64, height=32)

    # -- sprites ------------------------------------------------------------

    def _build_tile(self, rows):
        h, w = len(rows), len(rows[0])
        bmp = displayio.Bitmap(w, h, len(SPRITE_COLORS))
        for y, row in enumerate(rows):
            for x, ch in enumerate(row):
                slot = SPRITE_CHARS[ch]
                if slot:
                    bmp[x, y] = slot
        tile = displayio.TileGrid(bmp, pixel_shader=self._sprite_palette)
        tile.hidden = True
        self.display.add_layer(tile)
        self._all_tiles.append(tile)
        return tile

    def _build_sprites(self):
        self._all_tiles = []

        # Characters share one palette that nothing else ever writes to.
        self._sprite_palette = displayio.Palette(len(SPRITE_COLORS))
        for i, color in enumerate(SPRITE_COLORS):
            self._sprite_palette[i] = color
        self._sprite_palette.make_transparent(0)

        # Words share a tiny 2-slot palette; slot 1 is repainted to the active
        # theme's flat stop each act (a palette write, never a redraw).
        self._word_palette = displayio.Palette(2)
        self._word_palette.make_transparent(0)
        self._word_palette[1] = self._theme[2]

        # Small flying owl: two wing poses, each direction (mirrored rows).
        self.fly_left = [self._build_tile(OWL_FLY_UP),
                         self._build_tile(OWL_FLY_DOWN)]
        self.fly_right = [self._build_tile(_mirror(OWL_FLY_UP)),
                          self._build_tile(_mirror(OWL_FLY_DOWN))]

        # Big owl: three poses cycled UP -> MID -> DOWN -> MID (a real cel flap).
        big = (BIG_OWL_UP, BIG_OWL_MID, BIG_OWL_DOWN)
        self.big_left = [self._build_tile(rows) for rows in big]
        self.big_right = [self._build_tile(_mirror(rows)) for rows in big]

        # The bee: two wing poses, each direction.
        self.bee_right = [self._build_tile(BEE_UP), self._build_tile(BEE_DOWN)]
        self.bee_left = [self._build_tile(_mirror(BEE_UP)),
                         self._build_tile(_mirror(BEE_DOWN))]

        self._word_cache = {}       # (word, scale) -> entry dict
        self._fx_cache = {}         # (word, scale, partition) -> PalettePartition

    # -- words (the per-act "logo") ------------------------------------------

    def _word(self, word, scale):
        """Build (once) and return the word's display entry: its lit pixels,
        its TileGrid, and its per-letter pixel sets for route effects."""
        key = (word, scale)
        entry = self._word_cache.get(key)
        if entry is not None:
            return entry
        w = (6 * len(word) - 1) * scale
        h = 7 * scale
        x0 = (64 - w) // 2
        y0 = (32 - h) // 2

        bmp = displayio.Bitmap(w, h, 2)
        slots = {}
        letters = []
        for i in range(len(word)):
            lpx = set()
            for (gx, gy) in pixels_from_text(word[i], x=0, y=0):
                for sx in range(scale):
                    for sy in range(scale):
                        px = (i * 6 + gx) * scale + sx
                        py = gy * scale + sy
                        bmp[px, py] = 1
                        slots[(x0 + px, y0 + py)] = 1
                        lpx.add((x0 + px, y0 + py))
            if lpx:
                letters.append(lpx)
        tile = displayio.TileGrid(bmp, pixel_shader=self._word_palette)
        tile.x, tile.y = x0, y0
        tile.hidden = True
        self.display.add_layer(tile)
        self._all_tiles.append(tile)

        entry = {"word": word, "scale": scale, "slots": slots, "tile": tile,
                 "x": x0, "y": y0, "w": w, "h": h, "letters": letters,
                 "letter_tiles": None}
        self._word_cache[key] = entry
        return entry

    def _letter_tiles(self, entry):
        """Per-letter TileGrids for a word (lazy) — for swirl / drop / pickup."""
        tiles = entry["letter_tiles"]
        if tiles is not None:
            return tiles
        tiles = []
        scale = entry["scale"]
        word = entry["word"]
        for i in range(len(word)):
            lpx = pixels_from_text(word[i], x=0, y=0)
            if not lpx:
                continue
            w = (max(x for x, _ in lpx) + 1) * scale
            h = 7 * scale
            bmp = displayio.Bitmap(w, h, 2)
            for (gx, gy) in lpx:
                for sx in range(scale):
                    for sy in range(scale):
                        bmp[gx * scale + sx, gy * scale + sy] = 1
            tile = displayio.TileGrid(bmp, pixel_shader=self._word_palette)
            tile.hidden = True
            self.display.add_layer(tile)
            self._all_tiles.append(tile)
            tiles.append((tile, entry["x"] + i * 6 * scale, entry["y"], w, h))
        entry["letter_tiles"] = tiles
        return tiles

    def _show_word(self, entry):
        self._word_palette[1] = self._theme[2]
        tile = entry["tile"]
        tile.x, tile.y = entry["x"], entry["y"]
        tile.hidden = False

    # -- frame helpers --------------------------------------------------------

    async def _frame(self):
        """Present one frame at ~20 fps. False means the window closed."""
        if await self.display.show() is False:
            return False
        await asyncio.sleep(0.05)
        return True

    async def _hold(self, frames):
        for _ in range(frames):
            if not self.running or not await self._frame():
                return False
        return True

    def _hide_all(self):
        for tile in self._all_tiles:
            tile.hidden = True

    def _hide_actors(self):
        for tile in (self.fly_left + self.fly_right + self.big_left
                     + self.big_right + self.bee_left + self.bee_right):
            tile.hidden = True

    # -- library transitions as build/exit wipes -------------------------------

    async def _swap_via(self, name, rearrange):
        """Drive one screen transition: the pattern covers the panel,
        ``rearrange`` runs while hidden, the pattern reveals the result."""
        tr = transition_factory(name)
        await tr.start(self.display, rearrange)
        while not tr.is_complete:
            if not self.running:
                tr.detach()
                return False
            await tr.render(self.display)
            if not await self._frame():
                tr.detach()
                return False
        return True

    async def _reveal_word_via(self, name, entry):
        self._hide_all()
        return await self._swap_via(name, lambda: self._show_word(entry))

    async def _hide_word_via(self, name):
        return await self._swap_via(name, self._hide_all)

    def _pick_in(self):
        name, fam, tname = self._sched.pick(BUILD_TRANSITIONS, "in", self._used)
        self._used.add(fam)
        return tname

    def _pick_out(self):
        name, fam, tname = self._sched.pick(EXIT_TRANSITIONS, "out", self._used)
        self._used.add(fam)
        return tname

    # -- palette partitions over the act's word --------------------------------

    def _route_split(self, entry):
        """(left, right, terminus_index): letters split at the midpoint so
        route packets converge on the middle letter from both ends."""
        n = len(entry["letters"])
        mid = n // 2
        left = tuple(range(mid))
        right = tuple(range(n - 2, mid - 1, -1))
        return left, right, mid

    def _fx(self, entry, name):
        """Build (once per word) a named PalettePartition over the word."""
        key = (entry["word"], entry["scale"], name)
        fx = self._fx_cache.get(key)
        if fx is not None:
            return fx
        slots = entry["slots"]
        cx = entry["x"] + entry["w"] // 2
        cy = entry["y"] + entry["h"] // 2
        if name == "diag":
            group_map, n = map_diagonal(slots, 10)
        elif name == "anchor":
            group_map, n = map_anchor_distance(slots, cx, 10)
        elif name == "radial":
            group_map, n = map_radial(slots, cx, cy, 10)
        elif name == "angle":
            group_map, n = map_angle(slots, cx, cy, 14)
        elif name == "rain":
            group_map, n = map_rain(slots, 10)
        elif name == "checker":
            group_map, n = map_checker(slots, 4)
        elif name == "exposure":
            group_map, n = map_exposure(slots)
        elif name == "regions":
            group_map, n = map_regions(slots, 10)
        elif name == "topo":
            group_map, n = map_topology(slots)
        elif name == "route":
            _left, _right, mid = self._route_split(entry)
            letter_sets = [entry["letters"][i]
                           for i in range(len(entry["letters"])) if i != mid]
            group_map, n = map_route(slots, letter_sets, entry["letters"][mid])
        else:
            raise ValueError(name)
        fx = PalettePartition(displayio, slots, group_map, n)
        fx.tile.hidden = True
        self.display.add_layer(fx.tile)
        self._all_tiles.append(fx.tile)
        self._fx_cache[key] = fx
        return fx

    async def _run_treatment(self, entry, fx_name, make):
        """The dwell driver: invisible swap from the word sprite to the
        partition layer (both flat), step the treatment to completion, swap
        back. Treatments start and end at the theme's flat stop, so both
        swaps are seamless."""
        fx = self._fx(entry, fx_name)
        fx.fill(self._theme[2])
        entry["tile"].hidden = True
        fx.tile.hidden = False
        t = make(fx, entry)
        if hasattr(t, "start"):
            t.start(self.display)               # PacketTrace owns sprites
        ok = True
        while not t.is_complete:
            if not self.running:
                ok = False
                break
            t.step()
            if t.is_complete:
                break
            if not await self._frame():
                ok = False
                break
        if hasattr(t, "detach"):
            t.detach()
        fx.tile.hidden = True
        self._show_word(entry)
        return ok

    # -- treatment factories (library classes + the act's theme/routes) --------

    def _make_plain(self, cls):
        def make(fx, entry):
            return cls(fx, self._theme)
        return make

    def _make_gradient(self, fx, entry):
        return GradientDwell(fx, self._theme, self._theme[1], self._theme[3])

    def _make_rim(self, fx, entry):
        # The library defaults are DarkOwl brand shades; derive the moonlight
        # and the sheltered shadow from the act's theme instead.
        return RimLight(fx, self._theme, highlight=self._theme[4],
                        sheltered=self._theme[0])

    def _make_circuit(self, fx, entry):
        left, right, _mid = self._route_split(entry)
        routes = ([s for i in left for s in range(3 * i, 3 * i + 3)],
                  [s for i in right for s in range(3 * i, 3 * i + 3)])
        return RouteCircuit(fx, self._theme, routes)

    def _make_trace(self, fx, entry):
        left, right, mid = self._route_split(entry)
        letter_sets = [entry["letters"][i]
                       for i in range(len(entry["letters"])) if i != mid]
        runs = ((left, 0), (left, -30), (right, 0), (right, -24))
        return PacketTrace(fx, self._theme, bfs_paths(letter_sets), runs,
                           packet_color=PACKET_COLOR)

    # -- characters -------------------------------------------------------------

    def _fly_pose(self, tiles, frame, x, y):
        """Two-pose flap: alternate wing positions every 3 frames."""
        up = (frame // 3) % 2 == 0
        show, hide = (tiles[0], tiles[1]) if up else (tiles[1], tiles[0])
        show.x, show.y = x, y
        show.hidden = False
        hide.hidden = True

    def _big_pose(self, tiles, frame, x, y):
        """Cel flap for the big owl: UP -> MID -> DOWN -> MID, 2 frames each."""
        pose = (0, 1, 2, 1)[(frame // 2) % 4]
        for i, tile in enumerate(tiles):
            if i == pose:
                tile.x, tile.y = x, y
                tile.hidden = False
            else:
                tile.hidden = True

    async def _owl_flyby(self, direction="left", y_base=3, dip=8):
        """The big cel-animated owl crosses the empty panel, swooping."""
        owl_w = len(BIG_OWL_UP[0])
        tiles = self.big_left if direction == "left" else self.big_right
        travel = 64 + owl_w + 6
        frames_total = int(travel / 2.0)
        for f in range(frames_total + 1):
            if not self.running:
                return False
            t = f / frames_total
            if direction == "left":
                x = int(round(64 + 3 - travel * t))
            else:
                x = int(round(-owl_w - 3 + travel * t))
            y = y_base + int(round(dip * math.sin(math.pi * t)))
            self._big_pose(tiles, f, x, y)
            if not await self._frame():
                return False
        self._hide_actors()
        return True

    async def _bee_crossing(self, direction="right"):
        """The bee zigzags across on a sine path, flapping every other frame."""
        bee_w = len(BEE_UP[0])
        tiles = self.bee_right if direction == "right" else self.bee_left
        travel = 64 + bee_w + 4
        frames_total = int(travel / 1.8)
        y_base = random.randint(8, 18)
        for f in range(frames_total + 1):
            if not self.running:
                return False
            if direction == "right":
                x = int(round(-bee_w - 2 + 1.8 * f))
            else:
                x = int(round(66 - 1.8 * f))
            y = y_base + int(round(5.0 * math.sin(f * 0.30)))
            up = (f // 2) % 2 == 0
            show, hide = (tiles[0], tiles[1]) if up else (tiles[1], tiles[0])
            show.x, show.y = x, y
            show.hidden = False
            hide.hidden = True
            if not await self._frame():
                return False
        self._hide_actors()
        return True

    # -- named acts: the owl delivers SCROLLKIT ---------------------------------

    async def _act_owl_word(self):
        """The opener (and a recurring special): the small owl crosses the
        panel air-dropping the letters of SCROLLKIT one by one, the word
        dwells, and the owl sweeps back collecting every letter."""
        entry = self._word("SCROLLKIT", 1)
        letters = self._letter_tiles(entry)
        self._hide_all()
        self._word_palette[1] = self._theme[2]

        owl_w = len(OWL_FLY_UP[0])
        fly_y = 0
        speed = 1.6
        fall_frames = 6
        drop_y = fly_y + 7                       # released at the talons

        # Right-to-left pass, dropping each letter as the talons cross its slot.
        falling = []                             # [tile_entry_index, phase]
        dropped = set()
        landed = set()
        x = 66.0
        frame = 0
        while x > -owl_w - 2 or falling:
            if not self.running:
                return False
            if x > -owl_w - 2:
                x -= speed
                self._fly_pose(self.fly_left, frame, int(round(x)), fly_y)
            else:
                self._hide_actors()
            owl_center = x + owl_w * 0.35
            for i in range(len(letters)):
                _tile, tx, _ty, w, _h = letters[i]
                if i not in dropped and owl_center <= tx + w / 2:
                    dropped.add(i)
                    falling.append([i, 0])
            still = []
            for item in falling:
                i, phase = item
                tile, tx, ty, _w, _h = letters[i]
                if phase < fall_frames:
                    t = phase / fall_frames
                    tile.x = tx
                    tile.y = int(round(drop_y + (ty - drop_y) * t * t))
                    tile.hidden = False
                    item[1] += 1
                    still.append(item)
                else:
                    tile.x, tile.y = tx, ty      # settled on its slot
                    landed.add(i)
            falling = still
            frame += 1
            if not await self._frame():
                return False

        if not await self._hold(26):
            return False

        # The return sweep: left-to-right, each letter rising into the talons.
        rise_frames = 6
        rising = []
        lifted = set()
        x = -owl_w - 2.0
        frame = 0
        while x < 66 or rising:
            if not self.running:
                return False
            if x < 66:
                x += speed
                self._fly_pose(self.fly_right, frame, int(round(x)), fly_y)
            else:
                self._hide_actors()
            owl_center = x + owl_w * 0.65
            for i in range(len(letters)):
                tile, tx, _ty, w, _h = letters[i]
                if i not in lifted and owl_center >= tx + w / 2:
                    lifted.add(i)
                    rising.append([i, 0])
            still = []
            for item in rising:
                i, phase = item
                tile, tx, ty, _w, _h = letters[i]
                if phase < rise_frames:
                    t = phase / rise_frames
                    tile.y = int(round(ty + (drop_y - ty) * t * t))
                    item[1] += 1
                    still.append(item)
                else:
                    tile.hidden = True           # carried off in the talons
            rising = still
            frame += 1
            if not await self._frame():
                return False
        self._hide_actors()
        return await self._hold(8)

    # -- named acts: treatments --------------------------------------------------

    async def _act_treatment(self, word, scale, fx_name, make):
        """Anonymous wipe in, the NAMED treatment as the dwell, wipe out."""
        entry = self._word(word, scale)
        if not await self._reveal_word_via(self._pick_in(), entry):
            return False
        if not await self._hold(8):
            return False
        if not await self._run_treatment(entry, fx_name, make):
            return False
        if not await self._hold(6):
            return False
        if not await self._hide_word_via(self._pick_out()):
            return False
        return await self._hold(4)

    # -- named acts: transitions ---------------------------------------------------

    async def _act_transition(self, word, scale, tname):
        """The named transition builds its own word, then does its REAL job —
        a cover -> swap-while-hidden -> reveal between two different screens
        (the word jumps position and heats up) — then takes it away. Three
        passes of the pattern, one of them a true content swap."""
        entry = self._word(word, scale)
        if not await self._reveal_word_via(tname, entry):
            return False
        if not await self._hold(14):
            return False

        def swap_screens():
            tile = entry["tile"]
            tile.y = 3 if random.random() < 0.5 else 29 - entry["h"]
            self._word_palette[1] = self._theme[4]
        if not await self._swap_via(tname, swap_screens):
            return False
        if not await self._hold(14):
            return False
        if not await self._hide_word_via(tname):
            return False
        return await self._hold(4)

    async def _act_drop_sky(self):
        """Drop from Sky is the one transition that moves content instead of
        painting an overlay: the word slides in from a random edge."""
        entry = self._word("DROP", 2)
        self._hide_all()
        self._word_palette[1] = self._theme[2]
        tile = entry["tile"]
        direction = random.choice(("top", "left", "right", "bottom"))
        tr = transition_factory("Drop from Sky")
        tr.direction = direction
        await tr.start(self.display, lambda: None)
        pos = _Pos(entry["x"], entry["y"])
        tile.hidden = False
        while not tr.is_complete:
            if not self.running:
                return False
            pos.x, pos.y = entry["x"], entry["y"]
            tr.pre_render_hook(pos)
            tile.x, tile.y = pos.x, pos.y
            await tr.render(self.display, pos)
            if not await self._frame():
                return False
        tile.x, tile.y = entry["x"], entry["y"]
        if not await self._hold(20):
            return False
        if not await self._hide_word_via(self._pick_out()):
            return False
        return await self._hold(4)

    # -- named acts: splashes -------------------------------------------------------

    async def _act_swarm(self):
        """The flock assembles SWARM pixel by pixel, then a reverse flock
        carries it away — both swarm directions in one act."""
        entry = self._word("SWARM", 2)
        self._hide_all()
        self._word_palette[1] = self._theme[2]
        swarm = SwarmReveal(list(entry["slots"]), text_color=self._theme[2],
                            bird_color=BIRD_COLOR, num_birds=NUM_BIRDS,
                            bird_speed=3.2)
        if not await self._run_swarm(swarm):
            return False
        self._show_word(entry)                   # same pixels: seamless handoff
        swarm.detach()
        if not await self._hold(16):
            return False
        self._hide_all()
        unswarm = SwarmReveal(list(entry["slots"]), text_color=self._theme[2],
                              bird_color=BIRD_COLOR, num_birds=NUM_BIRDS,
                              bird_speed=3.2, reverse=True)
        ok = await self._run_swarm(unswarm)
        unswarm.detach()
        if not ok:
            return False
        return await self._hold(4)

    async def _run_swarm(self, swarm, max_steps=2500):
        swarm.start(self.display)
        steps = 0
        while not swarm.is_complete and steps < max_steps and self.running:
            swarm.step()
            steps += 1
            if not await self._frame():
                return False
        return True

    async def _act_drip(self):
        """DRIP rains in pixel by pixel from the top edge."""
        entry = self._word("DRIP", 2)
        self._hide_all()
        self._word_palette[1] = self._theme[2]
        drip = DripReveal(list(entry["slots"]), color=self._theme[2],
                          fall_speed=2, stagger=1, direction="top")
        drip.start(self.display)
        steps = 0
        ok = True
        while not drip.step() and steps < 2000:
            steps += 1
            if not self.running or not await self._frame():
                ok = False
                break
        if ok:
            self._show_word(entry)               # same pixels underneath
        drip.detach()
        if not ok:
            return False
        if not await self._hold(20):
            return False
        if not await self._hide_word_via(self._pick_out()):
            return False
        return await self._hold(4)

    async def _act_wink(self):
        """Every LED lights, then everything that isn't WINK winks off."""
        entry = self._word("WINK", 2)
        self._hide_all()
        self._show_word(entry)
        ok = await show_reveal_splash(self.display, list(entry["slots"]),
                                      color=self._theme[2],
                                      off_per_frame=44, hold_seconds=0.6)
        if ok is False or not self.running:
            return False
        if not await self._hold(12):
            return False
        if not await self._hide_word_via(self._pick_out()):
            return False
        return await self._hold(4)

    async def _act_swirl(self):
        """The letters of SWIRL spiral in around the panel center."""
        entry = self._word("SWIRL", 2)
        letters = self._letter_tiles(entry)
        self._hide_all()
        self._word_palette[1] = self._theme[2]
        sw = SwirlIn(letters)
        while not sw.is_complete:
            if not self.running:
                return False
            sw.step()
            if not await self._frame():
                return False
        if not await self._hold(22):
            return False
        for tile, _tx, _ty, _w, _h in letters:
            tile.hidden = True
        self._show_word(entry)                   # same pixels: seamless swap
        if not await self._hide_word_via(self._pick_out()):
            return False
        return await self._hold(4)

    # -- named acts: characterful scrolling / bitmap text -----------------------------

    async def _act_splitflap(self):
        """SplitFlap spells itself out, each cell flipping through glyphs."""
        self._hide_all()
        # A leading space centers the board (SplitFlap lays cells from x=0).
        eff = SplitFlap(" SPLITFLAP", y=13, color=self._theme[3], seed=7)
        await eff.start()
        while not eff.is_complete:
            if not self.running:
                return False
            await self.display.clear()
            await eff.render(self.display)
            if not await self._frame():
                return False
        await self.display.clear()
        return await self._hold(8)

    async def _scroller_pass(self, eff):
        """Drive a Class-1 scroller across the panel once (it names itself)."""
        await eff.start()
        while not eff.is_complete:
            if not self.running:
                return False
            await self.display.clear()
            await eff.render(self.display)
            if not await self._frame():
                return False
        await self.display.clear()
        return True

    async def _bitmap_banner(self, text, effect):
        """Scroll a palette-animated bitmap banner across once."""
        banner = BitmapText(text, y=12, palette_effect=effect,
                            scroll_speed=26, complete_after_passes=1)
        await banner.start()
        ok = True
        while not banner.is_complete:
            if not self.running:
                ok = False
                break
            await banner.render(self.display)
            if not await self._frame():
                ok = False
                break
        banner.detach(self.display)
        return ok

    # -- named acts: particles ---------------------------------------------------------

    async def _act_particles(self, kind):
        """A held word with its particle system as garnish."""
        word = {"sparkle": "SPARKLE", "snow": "SNOW", "ember": "EMBER"}[kind]
        entry = self._word(word, 2 if len(word) <= 5 else 1)
        if not await self._reveal_word_via(self._pick_in(), entry):
            return False
        engine = ParticleEngine(max_particles=24)
        frames = 96
        ok = True
        for f in range(frames):
            if not self.running:
                ok = False
                break
            await self.display.clear()
            if f % 2 == 0 and f < frames - 24:   # stop spawning near the end
                if kind == "sparkle":
                    engine.add_particle(Sparkle(
                        random.randint(2, 61), random.randint(2, 29),
                        color=random.choice((0xFFFFFF, self._theme[4],
                                             self._theme[3])),
                        lifetime=1.0))
                elif kind == "snow":
                    engine.add_particle(Snow(random.randint(0, 63), 0,
                                             speed=7.0, sway=1.4,
                                             lifetime=6.0))
                else:
                    # Explicit ramp, hottest first: an ember spawns white-hot
                    # and cools to deep red as it rises and fades. (The default
                    # ramp runs cool->hot, which the age-driven brightness fade
                    # cancels out — near-invisible on a dark panel.)
                    engine.add_particle(Ember(random.randint(10, 53), 31,
                                              speed=14.0, drift=3.0,
                                              lifetime=1.8,
                                              colors=(0xFFF0A0, 0xFFCC22,
                                                      0xFF8800, 0xFF4400,
                                                      0xCC1100)))
            await engine.update(self.display)
            if not await self._frame():
                ok = False
                break
        engine.clear_particles()
        await self.display.clear()
        if not ok:
            return False
        if not await self._hide_word_via(self._pick_out()):
            return False
        return await self._hold(4)

    # -- the decks ----------------------------------------------------------------------

    def _decks(self):
        """Every act, tagged by visual family — anything sharing a family is
        'similar' and never plays twice in a row."""
        decks = getattr(self, "_deck_cache", None)
        if decks is not None:
            return decks

        t = self._act_treatment
        acts = (
            # The characters' delivery act (also the forced boot opener).
            ("scrollkit", "letters", self._act_owl_word),
            # All 13 palette treatments, each on the word that names it.
            ("velvet", "sweep",
             lambda: t("VELVET", 1, "diag", self._make_plain(VelvetSweep))),
            ("wake", "radial",
             lambda: t("WAKE", 2, "anchor", self._make_plain(AnchorWake))),
            ("halo", "radial",
             lambda: t("HALO", 2, "radial", self._make_plain(HaloPulse))),
            ("sonar", "radial",
             lambda: t("SONAR", 2, "angle", self._make_plain(SonarSweep))),
            ("cipher", "fall",
             lambda: t("CIPHER", 1, "rain", self._make_plain(CipherRain))),
            ("ink", "texture",
             lambda: t("INK", 2, "checker", self._make_plain(InkShimmer))),
            ("rim", "sweep",
             lambda: t("RIM", 2, "exposure", self._make_rim)),
            ("heatmap", "texture",
             lambda: t("HEATMAP", 1, "regions", self._make_plain(HeatmapDrift))),
            ("eclipse", "sweep",
             lambda: t("ECLIPSE", 1, "diag", self._make_plain(EclipseCross))),
            ("gradient", "texture",
             lambda: t("GRADIENT", 1, "diag", self._make_gradient)),
            ("anatomy", "texture",
             lambda: t("ANATOMY", 1, "topo", self._make_plain(StrokeAnatomy))),
            ("circuit", "route",
             lambda: t("CIRCUIT", 1, "route", self._make_circuit)),
            ("trace", "route",
             lambda: t("TRACE", 2, "route", self._make_trace)),
            # All 13 transitions as named acts (in AND out, so they read).
            ("lightslit", "sweep",
             lambda: self._act_transition("LIGHT SLIT", 1, "Light Slit")),
            ("iris", "radial",
             lambda: self._act_transition("IRIS", 2, "Iris Snap")),
            ("mosaic", "texture",
             lambda: self._act_transition("MOSAIC", 1, "Mosaic Resolve")),
            ("gradual", "sweep",
             lambda: self._act_transition("GRADUAL", 1, "Gradual Reveal")),
            ("venetian", "bands",
             lambda: self._act_transition("VENETIAN", 1, "Venetian Shutters")),
            ("scanfold", "bands",
             lambda: self._act_transition("SCAN FOLD", 1, "Scan Fold")),
            ("crt", "collapse",
             lambda: self._act_transition("CRT", 2, "CRT Collapse")),
            ("dissolve", "texture",
             lambda: self._act_transition("DISSOLVE", 1, "Pixel Dissolve")),
            ("glitch", "bands",
             lambda: self._act_transition("GLITCH", 1, "Glitch Bars")),
            ("columnrain", "fall",
             lambda: self._act_transition("RAIN", 2, "Column Rain")),
            ("diagonal", "sweep",
             lambda: self._act_transition("DIAGONAL", 1, "Diagonal Wipe")),
            ("wipe", "sweep",
             lambda: self._act_transition("WIPE", 2, "Horizontal Wipe")),
            ("dropsky", "fall", self._act_drop_sky),
            # Splashes.
            ("swarm", "swarm", self._act_swarm),
            ("drip", "fall", self._act_drip),
            ("wink", "wall", self._act_wink),
            ("swirl", "letters", self._act_swirl),
            # Characterful scrolling held in place.
            ("splitflap", "letters", self._act_splitflap),
            # Particle garnish.
            ("sparkle", "texture", lambda: self._act_particles("sparkle")),
            ("snow", "fall", lambda: self._act_particles("snow")),
            ("emberp", "ember", lambda: self._act_particles("ember")),
        )

        mids = (
            ("owl-l", "owl", lambda: self._owl_flyby("left", 3, 8)),
            ("owl-r", "owl", lambda: self._owl_flyby("right", 14, -8)),
            ("bee-r", "bee", lambda: self._bee_crossing("right")),
            ("bee-l", "bee", lambda: self._bee_crossing("left")),
            ("marquee", "scroll", lambda: self._scroller_pass(
                KineticMarquee("KINETIC MARQUEE.", y=13,
                               color=self._theme[3], speed=34))),
            ("wave", "scroll", lambda: self._scroller_pass(
                WaveRider("WAVE RIDER", y=15, color=self._theme[3],
                          speed=30, amplitude=4))),
            # Banner colors are fixed (not theme stops): the palette effects
            # derive their own dim base/glow shades, so they need a bright seed.
            ("rainbow", "bitmap",
             lambda: self._bitmap_banner("RAINBOW CHASE", RainbowChase(period=3))),
            ("mono", "bitmap",
             lambda: self._bitmap_banner("MONO CHASE",
                                         MonoChase(color=0x66CCFF))),
            ("neon", "bitmap",
             lambda: self._bitmap_banner("NEON TUBE",
                                         NeonTubeCrawl(color=0x66FFCC))),
            ("chrome", "bitmap",
             lambda: self._bitmap_banner("CHROME SHEEN",
                                         ChromeSheen(color=0x3366AA,
                                                     highlight=0xFFFFFF))),
            ("hazard", "bitmap",
             lambda: self._bitmap_banner("HAZARD STRIPES", HazardStripes())),
        )
        self._deck_cache = (acts, mids)
        return self._deck_cache

    # -- the show -----------------------------------------------------------------------

    async def _act(self):
        """One scheduled act: rotate the color theme, play the least-recently
        seen act whose family differs from its neighbours', then maybe send a
        character or a scroller across the empty panel."""
        acts, mids = self._decks()
        first = not getattr(self, "_opened", False)
        self._opened = True

        theme_deck = tuple((name, name, colors) for name, colors in THEMES)
        _tn, tfam, colors = self._sched.pick(
            theme_deck, "theme", {getattr(self, "_theme_name", None)})
        self._theme_name = tfam
        self._theme = colors

        self._used = set(getattr(self, "_prev_families", ()))
        # Queue-jumping: CLI-named acts play first; otherwise the boot opener.
        if self._force_queue:
            force = self._force_queue.pop(0)
        else:
            force = "scrollkit" if first else None
        name, fam, act = self._sched.pick(acts, "act", self._used, force=force)
        self._used.add(fam)
        if not await act():
            return False
        self._prev_families = self._used - set(getattr(self, "_prev_families", ())) \
            or self._used

        if random.random() < 0.65:
            last = getattr(self, "_last_mid", None)
            m_name, m_fam, mid = self._sched.pick(
                mids, "mid", {last} if last else set())
            self._last_mid = m_fam
            if not await mid():
                return False
            if not await self._hold(4):
                return False
        return True

    async def setup(self):
        if hasattr(self.display, "create_window"):
            await self.display.create_window("ScrollKit Showcase Reel (hard)")
        self._build_sprites()
        self._sched = ActScheduler()
        acts, _mids = self._decks()
        valid = set(entry[0] for entry in acts)
        unknown = [n for n in self._force_queue if n not in valid]
        if unknown:
            print("unknown act(s): %s" % ", ".join(unknown))
            print("acts: %s" % ", ".join(sorted(valid)))
            self._force_queue = [n for n in self._force_queue if n in valid]
        while self.running:
            if await self._act() is False:
                return self._request_shutdown()


if __name__ == "__main__":
    # Positional args name acts to play first; flags go to _demo_support.
    _force = [a for a in sys.argv[1:] if not a.startswith("-")]
    for _a in _force:
        sys.argv.remove(_a)
    if _support is not None:
        _support.main(ShowcaseReelApp(force_acts=_force),
                      "ScrollKit showcase reel (hard)")
    else:
        asyncio.run(ShowcaseReelApp(force_acts=_force).run())
