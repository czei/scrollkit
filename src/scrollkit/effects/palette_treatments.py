# Copyright (c) 2024-2026 Michael Czeiszperger
"""Dwell treatments for palette-partitioned layers — pure palette animation.

Each treatment animates a :class:`scrollkit.effects.palette_partition.
PalettePartition` by rewriting its group colors every frame: zero pixel
work, so every class here is device-safe by construction. All of them
begin and end painting the theme's ``flat`` color, so a caller can swap
the partition tile in over identical flat sprites, run the treatment,
and swap back with no visible seam.

**Theme contract**: a 5-stop tuple ``(base, dim, flat, warm, hot)`` from
darkest to hottest — the shape of an ember ramp. ``flat`` is the resting
color of the mark; ``base`` its dimmed dwell state; ``warm``/``hot`` the
highlights; ``dim`` the trailing shade.

**Frame contract**: construct, then call :meth:`step` once per frame
until ``is_complete``. After each step, ``blink_now`` is True on the
frames where the source choreography blinked its mascot's eyes — the
caller owns pacing and blinks entirely:

    t = VelvetSweep(fx, theme)
    while not t.is_complete:
        t.step()
        if t.blink_now:
            await my_blink(fx)        # presents its own held frames
        else:
            await present_frame()

Only :class:`PacketTrace` touches the display directly (four 1-px packet
sprites); give it :meth:`PacketTrace.start` / :meth:`PacketTrace.detach`.

Each class's ``PARTITION`` attribute names the partition builder it is
designed for (see ``treatments_for``). Promoted from the DarkOwl LED
logo app (2026), where these run 24/7 on a MatrixPortal S3.
"""

import math

__all__ = [
    "AnchorWake",
    "CipherRain",
    "EclipseCross",
    "GradientDwell",
    "HaloPulse",
    "HeatmapDrift",
    "InkShimmer",
    "PacketTrace",
    "RimLight",
    "RouteCircuit",
    "SonarSweep",
    "StrokeAnatomy",
    "TREATMENT_CLASSES",
    "VelvetSweep",
    "treatments_for",
]

def lerp(a, b, t):
    """Blend 0xRRGGBB ``a`` -> ``b`` at t in 0..1.

    Deliberately NOT :func:`scrollkit.display.colors.lerp`: this is the
    source app's exact formula (``int(ca + delta * t)`` truncates the
    SUM, not the delta), kept so the promoted treatments are bit-exact
    against their originals. The visible difference is at most 1/255 per
    channel on descending fades.
    """
    out = 0
    for shift in (16, 8, 0):
        ca = (a >> shift) & 0xFF
        cb = (b >> shift) & 0xFF
        out |= (int(ca + (cb - ca) * t) & 0xFF) << shift
    return out


# The shared budget: every treatment is n_groups palette writes per frame
# (5-22 writes), no pixel work, no per-frame allocation (one preallocated
# color list, mutated in place).
_PALETTE_ONLY = {
    "hardware_safe": True,
    "allocates_per_frame": False,
    "max_pixel_writes_per_frame": 0,
    "modeled_frame_ms": 0.6,
    "note": "n_groups palette writes per frame; zero pixel work",
}


class _Treatment:
    """Shared driver: a generator script yielding once per frame.

    Scripts ``yield`` per presented frame and ``yield True`` on frames
    where the source choreography blinked (exposed as ``blink_now``).
    """

    FEASIBILITY = _PALETTE_ONLY
    PARTITION = None                 # recommended partition builder name

    def __init__(self, fx, theme):
        self.fx = fx
        self.theme = tuple(theme)
        n = fx.n_groups
        self._colors = [self.theme[2]] * n
        self._from = [0] * n         # snapshot buffer for fades
        self.frame = 0
        self.blink_now = False
        self._complete = False
        self._gen = self._script()

    @property
    def is_complete(self):
        return self._complete

    def step(self):
        """Advance one frame. Returns True once complete."""
        if self._complete:
            return True
        try:
            self.blink_now = next(self._gen) is True
        except StopIteration:
            self.blink_now = False
            self._complete = True
            return True
        self.frame += 1
        return False

    # -- script helpers (all mutate the preallocated color list) ----------

    def _paint(self):
        self.fx.paint(self._colors)

    def _set_all(self, color):
        colors = self._colors
        for i in range(len(colors)):
            colors[i] = color

    def _snapshot(self):
        src, dst = self._colors, self._from
        for i in range(len(src)):
            dst[i] = src[i]
        return dst

    def _fade(self, start, end, frames):
        """Crossfade every group color from start to end, painting each
        frame (the port of the app-side ``_fx_paint_fade``)."""
        colors = self._colors
        for f in range(1, frames + 1):
            t = f / frames
            for i in range(len(colors)):
                colors[i] = lerp(start[i], end[i], t)
            self._paint()
            yield

    def _hold(self, frames):
        for _ in range(frames):
            yield

    def _script(self):
        raise NotImplementedError


class VelvetSweep(_Treatment):
    """A hot sheen travels diagonally across the dimmed mark."""

    PARTITION = "diagonal"

    def __init__(self, fx, theme, sweeps=80, fade=8):
        self.sweeps = sweeps
        self.fade = fade
        _Treatment.__init__(self, fx, theme)

    def _script(self):
        base, _dim, flat, warm, hot = self.theme
        n = self.fx.n_groups
        colors = self._colors
        for _ in self._fade((flat,) * n, (base,) * n, self.fade):
            yield
        for f in range(self.sweeps):
            ridge = (f * 0.35) % (n + 6) - 3
            for i in range(n):
                d = abs(i - ridge)
                if d < 0.9:
                    colors[i] = hot
                elif d < 2.0:
                    colors[i] = warm
                else:
                    colors[i] = base
            self._paint()
            yield f == self.sweeps // 2
        for _ in self._fade((base,) * n, (flat,) * n, self.fade):
            yield


class AnchorWake(_Treatment):
    """Warmth flows outward from the anchor and a dimmer echo returns."""

    PARTITION = "anchor"

    def __init__(self, fx, theme, hold=4, fade=8):
        self.hold = hold
        self.fade = fade
        _Treatment.__init__(self, fx, theme)

    def _script(self):
        base, dim, flat, warm, hot = self.theme
        n = self.fx.n_groups
        colors = self._colors
        for _ in self._fade((flat,) * n, (base,) * n, self.fade):
            yield
        for direction, front, trail in ((1, hot, warm), (-1, warm, dim)):
            span = n + 4
            for f in range(int(span / 0.45)):
                pos = f * 0.45 - 2
                if direction < 0:
                    pos = (n + 1) - pos
                for i in range(n):
                    d = i - pos
                    if -0.9 < d < 0.9:
                        colors[i] = front
                    elif ((0.9 <= d < 2.2) if direction > 0
                          else (-2.2 < d <= -0.9)):
                        colors[i] = trail
                    else:
                        colors[i] = base
                self._paint()
                yield
            for _ in self._hold(self.hold):
                yield
        yield True                    # the blink beat
        for _ in self._fade((base,) * n, (flat,) * n, self.fade):
            yield


class HaloPulse(_Treatment):
    """Circular pressure waves expand outward through radial bands."""

    PARTITION = "radial"

    def __init__(self, fx, theme, waves=3, fade=8):
        self.waves = waves
        self.fade = fade
        _Treatment.__init__(self, fx, theme)

    def _script(self):
        base, _dim, flat, warm, hot = self.theme
        n = self.fx.n_groups
        colors = self._colors
        for _ in self._fade((flat,) * n, (base,) * n, self.fade):
            yield
        for wave in range(self.waves):
            for f in range(int((n + 3) / 0.4)):
                pos = f * 0.4 - 1
                for i in range(n):
                    d = i - pos
                    if -1.0 < d < 1.0:
                        colors[i] = hot
                    elif -2.4 < d <= -1.0:
                        colors[i] = warm
                    else:
                        colors[i] = base
                self._paint()
                yield
            if wave == 1:
                yield True            # the blink beat
        for _ in self._fade((base,) * n, (flat,) * n, self.fade):
            yield


class SonarSweep(_Treatment):
    """A wedge sweeps around the anchor, leaving a fading afterglow."""

    PARTITION = "angle"

    def __init__(self, fx, theme, fade=8):
        self.fade = fade
        _Treatment.__init__(self, fx, theme)

    def _script(self):
        base, dim, flat, warm, hot = self.theme
        n = self.fx.n_groups
        colors = self._colors
        for _ in self._fade((flat,) * n, (base,) * n, self.fade):
            yield
        total = int(2.5 * n / 0.4)
        for f in range(total):
            pos = (f * 0.4) % n
            for i in range(n):
                d = (pos - i) % n     # how long ago the wedge passed
                if d < 1.0:
                    colors[i] = hot
                elif d < 2.5:
                    colors[i] = warm
                elif d < 4.5:
                    colors[i] = dim
                else:
                    colors[i] = base
            self._paint()
            yield f == total // 2
        for _ in self._fade((base,) * n, (flat,) * n, self.fade):
            yield


class CipherRain(_Treatment):
    """Phase-staggered highlights descend within the strokes."""

    PARTITION = "rain"

    def __init__(self, fx, theme, frames=140, fade=8):
        self.frames = frames
        self.fade = fade
        _Treatment.__init__(self, fx, theme)

    def _script(self):
        base, dim, flat, warm, hot = self.theme
        n = self.fx.n_groups
        colors = self._colors
        for _ in self._fade((flat,) * n, (base,) * n, self.fade):
            yield
        for f in range(self.frames):
            offset = (f * 0.5) % n
            for i in range(n):
                d = (offset - i) % n
                if d < 1.0:
                    colors[i] = hot
                elif d < 2.0:
                    colors[i] = warm
                elif d < 3.2:
                    colors[i] = dim
                else:
                    colors[i] = base
            self._paint()
            yield f == self.frames // 2
        for _ in self._fade((base,) * n, (flat,) * n, self.fade):
            yield


class InkShimmer(_Treatment):
    """Interleaved groups slowly exchange two close shades: satin."""

    PARTITION = "checker"

    def __init__(self, fx, theme, frames=120, fade=8):
        self.frames = frames
        self.fade = fade
        _Treatment.__init__(self, fx, theme)

    def _script(self):
        base, _dim, flat, _warm, _hot = self.theme
        n = self.fx.n_groups
        colors = self._colors
        for f in range(self.frames):
            tt = f * 0.05
            for i in range(n):
                phase = math.sin(tt * 1.6 + i * 1.7)
                colors[i] = lerp(base, flat, 0.5 + 0.5 * phase)
            self._paint()
            yield f == self.frames // 2
        start = self._snapshot()
        for _ in self._fade(start, (flat,) * n, self.fade):
            yield


class RimLight(_Treatment):
    """A light passes over; whichever stroke edge faces it catches a
    highlight. Requires the 5-group exposure partition."""

    PARTITION = "exposure"

    def __init__(self, fx, theme, highlight=0xE8873C, sheltered=0x571007,
                 loops=2, fade=8):
        self.highlight = highlight
        self.sheltered = sheltered
        self.loops = loops
        self.fade = fade
        _Treatment.__init__(self, fx, theme)

    def _script(self):
        base_c, _dim, flat, _warm, _hot = self.theme
        base = (base_c, base_c, base_c, base_c, self.sheltered)
        for _ in self._fade((flat,) * 5, base, self.fade):
            yield
        order = (0, 1, 2, 3)          # overhead, right, under, left
        for loop in range(self.loops):
            for lit in order:
                target = list(base)
                target[lit] = self.highlight
                prev = tuple(target[i] if i == (lit - 1) % 4 else base[i]
                             for i in range(5))
                for _ in self._fade(prev, target, 7):
                    yield
                for _ in self._hold(5):
                    yield
            if loop == 0:
                yield True            # the blink beat
        for _ in self._fade(base, (flat,) * 5, self.fade):
            yield


class HeatmapDrift(_Treatment):
    """Coherent regions warm and cool independently, like detections
    surfacing on an analyst's map."""

    PARTITION = "regions"

    def __init__(self, fx, theme, frames=120, fade=8):
        self.frames = frames
        self.fade = fade
        _Treatment.__init__(self, fx, theme)

    def _script(self):
        base, _dim, flat, warm, hot = self.theme
        n = self.fx.n_groups
        colors = self._colors
        for _ in self._fade((flat,) * n, (base,) * n, self.fade):
            yield
        for f in range(self.frames):
            tt = f * 0.05
            for i in range(n):
                heat = math.sin(tt * 1.1 + i * 2.2)
                if heat > 0.75:
                    colors[i] = hot
                elif heat > 0.45:
                    colors[i] = warm
                elif heat > 0.1:
                    colors[i] = flat
                else:
                    colors[i] = base
            self._paint()
            yield f == self.frames // 2
        start = self._snapshot()
        for _ in self._fade(start, (flat,) * n, self.fade):
            yield


class EclipseCross(_Treatment):
    """A deep shadow crosses the flat mark with a hot corona at its
    leading edge and a dusk trail behind."""

    PARTITION = "diagonal"

    def __init__(self, fx, theme, sweeps=2, shadow=0x2A0604):
        self.sweeps = sweeps
        self.shadow = shadow
        _Treatment.__init__(self, fx, theme)

    def _script(self):
        _base, dim, flat, _warm, hot = self.theme
        n = self.fx.n_groups
        colors = self._colors
        for sweep in range(self.sweeps):
            for f in range(int((n + 6) / 0.35)):
                pos = f * 0.35 - 3
                for i in range(n):
                    d = i - pos
                    if -0.9 < d < 0.9:
                        colors[i] = self.shadow      # the shadow core
                    elif 0.9 <= d < 1.9:
                        colors[i] = hot              # leading corona
                    elif -1.9 < d <= -0.9:
                        colors[i] = dim              # trailing dusk
                    else:
                        colors[i] = flat
                self._paint()
                yield
            if sweep == 0:
                yield True            # the blink beat
        self._set_all(flat)
        self._paint()
        for _ in self._hold(2):
            yield


class GradientDwell(_Treatment):
    """The mark crossfades to a two-stop gradient edition, dwells, and
    returns to flat (one Nocturne Library chapter)."""

    PARTITION = "diagonal"

    def __init__(self, fx, theme, lo, hi, fade=12, holds=(20, 12)):
        self.lo = lo
        self.hi = hi
        self.fade = fade
        self.holds = holds
        _Treatment.__init__(self, fx, theme)

    def _script(self):
        flat = self.theme[2]
        n = self.fx.n_groups
        target = tuple(lerp(self.lo, self.hi, i / (n - 1)) for i in range(n))
        for _ in self._fade((flat,) * n, target, self.fade):
            yield
        for _ in self._hold(self.holds[0]):
            yield
        yield True                    # the blink beat
        for _ in self._hold(self.holds[1]):
            yield
        for _ in self._fade(target, (flat,) * n, self.fade):
            yield


class StrokeAnatomy(_Treatment):
    """Endpoints, corners, junctions, and runs trade emphasis in turn:
    the 1px typography under analysis. Requires the 5-group topology
    partition."""

    PARTITION = "topology"

    def __init__(self, fx, theme, fade=9, hold=16):
        self.fade = fade
        self.hold = hold
        _Treatment.__init__(self, fx, theme)

    def _script(self):
        base, dim, flat, warm, hot = self.theme
        phases = (
            (hot, warm, dim, base, base),
            (dim, base, hot, flat, flat),
            (base, hot, dim, base, warm),
        )
        prev = (flat,) * 5
        for k, phase in enumerate(phases):
            for _ in self._fade(prev, phase, self.fade):
                yield
            for _ in self._hold(self.hold):
                yield
            if k == 1:
                yield True            # the blink beat
            prev = phase
        for _ in self._fade(prev, (flat,) * 5, self.fade):
            yield


class RouteCircuit(_Treatment):
    """Hot packets crawl the route sections from both ends and converge
    on the terminus, which flares as each delivery arrives. Requires the
    route partition; ``routes`` are two sequences of group indices (the
    outbound and the inbound walks)."""

    PARTITION = "route"

    def __init__(self, fx, theme, routes, passes=2, base_color=0x4A0D06,
                 fade=8):
        self.routes = tuple(tuple(r) for r in routes)
        self.passes = passes
        self.base_color = base_color
        self.fade = fade
        _Treatment.__init__(self, fx, theme)

    def _base(self):
        n = self.fx.n_groups
        base = [self.base_color] * n
        base[n - 1] = self.theme[2]   # the terminus stays lit: the destination
        return base

    def _script(self):
        _b, dim, flat, warm, hot = self.theme
        n = self.fx.n_groups
        terminus = n - 1
        base = self._base()
        colors = self._colors
        for _ in self._fade((flat,) * n, base, self.fade):
            yield
        for _pass in range(self.passes):
            steps = max(len(r) for r in self.routes) + 2
            for s in range(steps * 2):
                idx = s // 2
                for i in range(n):
                    colors[i] = base[i]
                for route in self.routes:
                    for lag, shade in ((0, hot), (1, warm), (2, dim)):
                        j = idx - lag
                        if 0 <= j < len(route):
                            colors[route[j]] = shade
                self._paint()
                yield
            # both packets arrive: the terminus flares, then absorbs them
            for f in range(8):
                for i in range(n):
                    colors[i] = base[i]
                colors[terminus] = hot if f < 4 else warm
                self._paint()
                yield
        yield True                    # the blink beat
        for _ in self._fade(base, (flat,) * n, self.fade):
            yield


class PacketTrace(_Treatment):
    """Amber packet dots crawl the actual strokes toward the terminus
    while the route sections behind them glow. The one treatment that
    owns display layers (its 1-px packet sprites): call
    :meth:`start` before stepping and :meth:`detach` after.

    ``paths`` are per-glyph ordered pixel paths (``bfs_paths``) in the
    SAME order the route partition was built from (group = 3 * path
    index + section). ``runs`` are ``(path_indices, lag)`` tuples — one
    packet sprite per run, walking those paths with a frame offset.
    """

    PARTITION = "route"
    FEASIBILITY = {
        "hardware_safe": True,
        "allocates_per_frame": False,
        "max_pixel_writes_per_frame": 0,
        "modeled_frame_ms": 1.2,
        "note": "n_groups palette writes + ~len(runs) tile moves per frame",
    }

    def __init__(self, fx, theme, paths, runs, packet_color=0xFFB030,
                 base_color=0x4A0D06, fade=8):
        self.paths = paths
        self.runs = tuple(runs)
        self.packet_color = packet_color
        self.base_color = base_color
        self.fade = fade
        self._display = None
        self._tiles = []
        _Treatment.__init__(self, fx, theme)

    def start(self, display):
        """Create one 1-px packet sprite per run, above the partition."""
        gfx = display.gfx
        self._display = display
        for _ in self.runs:
            dot = gfx.Bitmap(1, 1, 2)
            dot[0, 0] = 1
            pal = gfx.Palette(2)
            pal.make_transparent(0)
            pal[1] = self.packet_color
            tile = gfx.TileGrid(dot, pixel_shader=pal)
            tile.hidden = True
            display.add_layer(tile)
            self._tiles.append(tile)

    def detach(self):
        """Remove the packet sprites (no-op if never started)."""
        if self._display is None:
            return
        for tile in self._tiles:
            self._display.remove_layer(tile)
        self._tiles = []
        self._display = None

    def _script(self):
        _b, _dim, flat, warm, hot = self.theme
        n = self.fx.n_groups
        terminus = n - 1
        base = [self.base_color] * n
        base[terminus] = flat
        colors = self._colors
        paths = self.paths
        for _ in self._fade((flat,) * n, base, self.fade):
            yield
        route_len = []
        for path_idxs, _lag in self.runs:
            route_len.append(sum(len(paths[g]) for g in path_idxs))
        longest = max(route_len) + 40
        for f in range(0, longest, 2):
            for i in range(n):
                colors[i] = base[i]
            for pi in range(len(self.runs)):
                path_idxs, lag = self.runs[pi]
                step = f + lag
                tile = self._tiles[pi] if pi < len(self._tiles) else None
                if step < 0 or step >= route_len[pi]:
                    if tile is not None:
                        tile.hidden = True
                    continue
                s = step
                for g in path_idxs:
                    if s < len(paths[g]):
                        x, y = paths[g][s]
                        if tile is not None:
                            tile.x, tile.y = x, y
                            tile.hidden = False
                        # wake: warm the route section the packet is in
                        # (route groups are 3 per path in order)
                        sec = 3 * g + min(s * 3 // len(paths[g]), 2)
                        colors[sec] = warm
                        break
                    s -= len(paths[g])
            self._paint()
            yield
        for tile in self._tiles:
            tile.hidden = True
        # deliveries land: the terminus flares
        for f in range(10):
            for i in range(n):
                colors[i] = base[i]
            colors[terminus] = hot if f < 5 else warm
            self._paint()
            yield
        yield True                    # the blink beat
        for _ in self._fade(base, (flat,) * n, self.fade):
            yield


TREATMENT_CLASSES = (
    VelvetSweep, AnchorWake, HaloPulse, SonarSweep, CipherRain, InkShimmer,
    RimLight, HeatmapDrift, EclipseCross, GradientDwell, StrokeAnatomy,
    RouteCircuit, PacketTrace,
)


def treatments_for(partition):
    """The treatment classes designed for a named partition builder."""
    return tuple(cls for cls in TREATMENT_CLASSES
                 if cls.PARTITION == partition)
