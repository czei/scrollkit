"""Palette-partition effect layers: animate any pixel set with palette writes.

The cheapest device-safe animation there is. Statically assign every lit
pixel of an assembled mark (a logo, a word, an icon) to one of N groups,
bake that partition into an indexed full-panel bitmap ONCE, then animate
by rewriting N palette entries per frame: zero per-frame pixel work.

Each :class:`PalettePartition` owns its bitmap AND its own Palette, so
animating one layer can never recolor other sprites or another partition.
``identity_colors`` reserves palette slots that stay constant through any
treatment (a mascot's eyes, a logo accent) — the identity anchor.

Partition builders return ``({(x, y): group_index}, n_groups)`` for the
BODY pixels only (input slot 1); identity pixels (input slots >= 2) are
handled by PalettePartition itself. Pair a partition with the treatment
classes in :mod:`scrollkit.effects.palette_treatments`, or paint it
directly.

Promoted from the DarkOwl LED logo app (2026), where every dwell effect
in a 24/7 sign runs on these partitions.
"""

import math

__all__ = [
    "PalettePartition",
    "bfs_paths",
    "map_anchor_distance",
    "map_angle",
    "map_checker",
    "map_diagonal",
    "map_exposure",
    "map_radial",
    "map_rain",
    "map_regions",
    "map_route",
    "map_topology",
]


class PalettePartition:
    """One partitioned layer: a bitmap, its palette, and paint().

    ``pixel_slots`` maps ``(x, y) -> input slot``: slot 1 is the body
    (partitioned into groups), slots 2..k+1 are identity pixels that take
    the reserved palette slots 1..k (seeded from ``identity_colors`` and
    written only via :meth:`set_identity`). Group colors start at slot
    ``1 + len(identity_colors)``.
    """

    FEASIBILITY = {
        "hardware_safe": True,
        "allocates_per_frame": False,
        "max_pixel_writes_per_frame": 0,      # animation is palette writes
        "modeled_frame_ms": 0.5,
        "note": "one-time build cost ~len(pixel_slots); paint() is n_groups"
                " palette writes",
    }

    def __init__(self, gfx, pixel_slots, group_map, n_groups,
                 identity_colors=(), width=64, height=32):
        self.n_groups = n_groups
        self._group_base = 1 + len(identity_colors)
        bmp = gfx.Bitmap(width, height, self._group_base + n_groups)
        for (x, y), slot in pixel_slots.items():
            if slot == 1:
                bmp[x, y] = self._group_base + group_map[(x, y)]
            else:
                bmp[x, y] = slot - 1      # input slot 2 -> identity slot 1
        self.palette = gfx.Palette(self._group_base + n_groups)
        self.palette.make_transparent(0)
        for i, color in enumerate(identity_colors):
            self.palette[1 + i] = color
        self._identity_colors = tuple(identity_colors)
        self.tile = gfx.TileGrid(bmp, pixel_shader=self.palette)
        self.tile.hidden = True

    def paint(self, colors):
        """Write all group colors (len == n_groups). Identity untouched."""
        pal = self.palette
        base = self._group_base
        for i, c in enumerate(colors):
            pal[base + i] = c

    def fill(self, color):
        """Every group the same color (the invisible-swap state)."""
        pal = self.palette
        base = self._group_base
        for i in range(self.n_groups):
            pal[base + i] = color

    def set_identity(self, *colors):
        """Write the reserved identity slots (e.g. dim the eyes to blink)."""
        for i, c in enumerate(colors):
            self.palette[1 + i] = c


# ---------------------------------------------------------------------------
# Partition builders. Each takes ``pixel_slots`` ({(x, y): slot}) plus
# parameters, and returns ({(x, y): group}, n_groups) over the BODY pixels.
# ---------------------------------------------------------------------------

def _body_pixels(pixel_slots):
    return [p for p, slot in pixel_slots.items() if slot == 1]


def map_diagonal(pixel_slots, n=10):
    """Bands along x + 2y: a diagonal sweep axis."""
    body = _body_pixels(pixel_slots)
    vals = {p: p[0] + 2 * p[1] for p in body}
    lo = min(vals.values())
    hi = max(vals.values())
    span = (hi - lo) + 1
    return {p: (v - lo) * n // span for p, v in vals.items()}, n


def map_anchor_distance(pixel_slots, anchor_x, n=10):
    """Mirrored bands by horizontal distance from an anchor column."""
    body = _body_pixels(pixel_slots)
    vals = {p: abs(p[0] - anchor_x) for p in body}
    hi = max(vals.values())
    return {p: v * n // (hi + 1) for p, v in vals.items()}, n


def map_radial(pixel_slots, cx, cy, n=10, y_scale=2):
    """Concentric distance bands around a point. ``y_scale`` compensates
    panel aspect (64x32 pixels are wider than tall; pass 1 for square)."""
    body = _body_pixels(pixel_slots)
    vals = {}
    for (x, y) in body:
        dx = x - cx
        dy = (y - cy) * y_scale
        vals[(x, y)] = (dx * dx + dy * dy) ** 0.5
    hi = max(vals.values())
    return {p: min(int(v * n / (hi + 1e-6)), n - 1)
            for p, v in vals.items()}, n


def map_angle(pixel_slots, cx, cy, n=14):
    """Angular wedges around a point (a radar sweep axis)."""
    body = _body_pixels(pixel_slots)
    groups = {}
    for (x, y) in body:
        a = math.atan2(y - cy, x - cx)          # -pi..pi
        g = int((a + math.pi) * n / (2 * math.pi + 1e-6))
        groups[(x, y)] = min(g, n - 1)
    return groups, n


def map_rain(pixel_slots, n=10):
    """Per-column phase-staggered vertical cycle. Rotating the palette one
    step per beat makes highlights descend each column, out of phase with
    its neighbours."""
    body = _body_pixels(pixel_slots)
    groups = {}
    for (x, y) in body:
        phase = (x * 7 + (x >> 2) * 3) % n      # cheap fixed column hash
        groups[(x, y)] = (y + phase) % n
    return groups, n


def map_checker(pixel_slots, n=4):
    """Interleaved parity groups: a satin-shimmer texture."""
    body = _body_pixels(pixel_slots)
    if n == 2:
        return {p: (p[0] + p[1]) % 2 for p in body}, 2
    return {p: (p[0] % 2) + 2 * (p[1] % 2) for p in body}, 4


def map_exposure(pixel_slots):
    """Group by which side of the stroke faces open sky.
    Groups: 0 top-facing, 1 right, 2 bottom, 3 left, 4 sheltered."""
    body = set(_body_pixels(pixel_slots))
    groups = {}
    dirs = ((0, -1), (1, 0), (0, 1), (-1, 0))
    for (x, y) in body:
        g = 4
        for i, (dx, dy) in enumerate(dirs):
            if (x + dx, y + dy) not in body:
                g = i
                break
        groups[(x, y)] = g
    return groups, 5


def map_regions(pixel_slots, n=10):
    """Spatially coherent Voronoi regions over the mark. Seeds are lit
    pixels spaced evenly along x, so regions read as contiguous patches
    rather than confetti."""
    body = sorted(_body_pixels(pixel_slots))
    step = max(1, len(body) // n)
    seeds = [body[i * step + step // 2] for i in range(n)]
    groups = {}
    for (x, y) in body:
        best, best_d = 0, 1 << 30
        for i, (sx, sy) in enumerate(seeds):
            dx = x - sx
            dy = (y - sy) * 2            # panel aspect
            d = dx * dx + dy * dy
            if d < best_d:
                best, best_d = i, d
        groups[(x, y)] = best
    return groups, n


def bfs_paths(glyph_pixel_sets):
    """Ordered pixel paths (BFS depth order) per glyph, for packet sprites
    that crawl the actual strokes."""
    paths = []
    for pixel_set in glyph_pixel_sets:
        depth = _bfs_depth(pixel_set)
        paths.append(sorted(depth, key=lambda p: (depth[p], p[1], p[0])))
    return paths


def map_topology(pixel_slots):
    """Classify each body pixel by its lit neighborhood.

    Groups: 0 endpoint, 1 corner/diagonal, 2 junction,
            3 horizontal run, 4 vertical run.
    """
    body = set(_body_pixels(pixel_slots))
    groups = {}
    for (x, y) in body:
        nbrs = []
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                if (dx or dy) and (x + dx, y + dy) in body:
                    nbrs.append((dx, dy))
        deg = len(nbrs)
        if deg <= 1:
            g = 0
        elif deg >= 3:
            g = 2
        else:
            (ax, ay), (bx, by) = nbrs
            if ax == -bx and ay == -by:          # colinear through-pixel
                if ay == 0:
                    g = 3                        # horizontal run
                elif ax == 0:
                    g = 4                        # vertical run
                else:
                    g = 1                        # diagonal run
            else:
                g = 1                            # corner
        groups[(x, y)] = g
    return groups, 5


def map_route(pixel_slots, path_pixel_sets, terminus_pixels, sections=3):
    """BFS along each glyph's strokes, quantized into ordered sections, so
    a 'packet' visibly crawls the letterforms toward a terminus.

    path_pixel_sets: list of (set of body (x, y)) in ROUTE order
    terminus_pixels: set of the destination's body pixels (the last stop)
    Returns (group_map, n_groups); groups are ordered along the route,
    with the terminus as the last group.
    """
    groups = {}
    next_group = 0
    for pixel_set in path_pixel_sets:
        depth = _bfs_depth(pixel_set)
        max_d = max(depth.values()) if depth else 0
        for p, d in depth.items():
            groups[p] = next_group + d * sections // (max_d + 1)
        next_group += sections
    for p in terminus_pixels:
        groups[p] = next_group
    return groups, next_group + 1


def _bfs_depth(pixels):
    """BFS depth over a set of pixels (8-connected) from the top-left one."""
    if not pixels:
        return {}
    seed = min(pixels, key=lambda p: (p[1], p[0]))
    depth = {seed: 0}
    queue = [seed]
    qi = 0
    while qi < len(queue):
        x, y = queue[qi]
        qi += 1
        d = depth[(x, y)]
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                q = (x + dx, y + dy)
                if (dx or dy) and q in pixels and q not in depth:
                    depth[q] = d + 1
                    queue.append(q)
    # unreachable stragglers (shouldn't happen on connected glyphs)
    for p in pixels:
        if p not in depth:
            depth[p] = 0
    return depth
