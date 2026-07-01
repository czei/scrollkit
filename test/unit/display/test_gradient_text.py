"""Gradient / multi-colour text fill on StaticText & ScrollingText.

A ``palette`` switches the Label-based text classes to an indexed-bitmap renderer
(``GradientTextLayer``) that paints each lit pixel a palette index by its position
along an axis, then scrolls by moving a TileGrid — zero per-frame pixel writes.
Mono content (``palette=None``) is untouched.
"""

import os
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pytest

pygame = pytest.importorskip("pygame")

from scrollkit.display.content import StaticText, ScrollingText
from scrollkit.display.colors import depth_palette, scale, gradient
from scrollkit.display.gradient_text import GradientTextLayer, _GradientTextLayer, _build_ramp
from scrollkit.display import text_fill


def test_underscore_alias_is_the_public_class():
    # 0.8.x compatibility: themeparkwaits still imports the old private name.
    assert _GradientTextLayer is GradientTextLayer


# --- helpers ----------------------------------------------------------------

async def _make_display():
    from scrollkit.display.simulator import SimulatorDisplay
    d = SimulatorDisplay(width=64, height=32)
    await d.initialize()
    return d


async def _render_to_matrix(d, content):
    await d.clear()
    await content.render(d)
    await d.show()


def _lit_rows(d):
    rows = set()
    for y in range(d.height):
        for x in range(d.width):
            c = d.matrix.get_pixel(x, y)
            if c and tuple(c)[:3] != (0, 0, 0):
                rows.add(y)
    return rows


class _StubDisplay:
    """A display with NO font/gfx — exercises the graceful mono fallback."""
    def __init__(self, width=64):
        self._width = width
        self.draws = []

    @property
    def width(self):
        return self._width

    def measure_text(self, text, font=None):
        return len(text) * 6

    async def draw_text(self, text, x, y=0, color=0xFFFFFF, font=None):
        self.draws.append((text, x, y, color))


# --- depth_palette ----------------------------------------------------------

def test_depth_palette_two_close_shades():
    # Highlight is the base colour; shadow is it darkened by `strength`.
    assert depth_palette(0x66CCFF, 0.4) == (0x66CCFF, scale(0x66CCFF, 0.6))
    hi, lo = depth_palette(0x66CCFF, 0.4)
    assert hi == 0x66CCFF and lo < hi          # shadow is darker


def test_depth_palette_more_steps_returns_full_ramp():
    ramp = depth_palette(0x66CCFF, 0.4, steps=8)
    assert len(ramp) == 8
    assert ramp[0] == 0x66CCFF
    assert ramp == gradient(0x66CCFF, scale(0x66CCFF, 0.6), 8)


# --- vocabulary -------------------------------------------------------------

def test_directions_and_clamp():
    assert text_fill.gradient_directions() == ("vertical", "horizontal", "diagonal")
    assert text_fill.normalize_direction("sideways") == "vertical"
    assert text_fill.normalize_direction("diagonal") == "diagonal"
    assert text_fill.clamp_palette_steps(1) == 2
    assert text_fill.clamp_palette_steps(99) == text_fill.MAX_PALETTE_STEPS
    assert text_fill.clamp_palette_steps(8) == 8


# --- positional index mapping (font-independent math) -----------------------

def test_ramp_index_vertical_spans_top_to_bottom():
    layer = GradientTextLayer("A", 0, (0xFF0000, 0x0000FF), "vertical", 8)
    last = 7
    assert layer._ramp_index(0, 0, 0, 10, 10, last) == 0       # top row -> stop 0
    assert layer._ramp_index(0, 10, 0, 10, 10, last) == last   # bottom -> stop N
    assert layer._ramp_index(0, 5, 0, 10, 10, last) == 3       # middle-ish


def test_ramp_index_horizontal_spans_left_to_right():
    layer = GradientTextLayer("A", 0, (0xFF0000, 0x0000FF), "horizontal", 8)
    last = 7
    assert layer._ramp_index(0, 3, 0, 10, 10, last) == 0       # left -> stop 0
    assert layer._ramp_index(10, 3, 0, 10, 10, last) == last   # right -> stop N


def test_ramp_index_diagonal_combines_axes():
    layer = GradientTextLayer("A", 0, (0xFF0000, 0x0000FF), "diagonal", 8)
    last = 7
    assert layer._ramp_index(0, 0, 0, 10, 10, last) == 0
    assert layer._ramp_index(10, 10, 0, 10, 10, last) == last


def test_build_ramp_shapes():
    assert _build_ramp((0x111111,), 5) == (0x111111,) * 5          # 1 colour -> flat
    assert _build_ramp((0x000000, 0xFFFFFF), 4) == gradient(0x000000, 0xFFFFFF, 4)
    assert len(_build_ramp((0x100000, 0x001000, 0x000010), 6)) == 6  # multi-stop


# --- build correctness (rendered bitmap) ------------------------------------

@pytest.mark.asyncio
async def test_gradient_builds_indexed_bitmap_within_4bpp():
    d = await _make_display()
    c = StaticText("ABC", x=2, y=12, palette=(0xFF0000, 0x0000FF), palette_steps=8)
    await c.render(d)
    layer = c._grad
    assert layer is not None
    # steps(8) + transparent(0) == 9 palette values, comfortably <= 16 (4bpp).
    indices = set()
    for x in range(layer.width):
        for y in range(layer._bitmap.height):
            v = layer._bitmap[x, y]
            if v:
                indices.add(v)
    assert len(indices) >= 2               # a real gradient, not one flat colour
    assert max(indices) <= 8               # never exceeds steps
    # Ramp endpoints are the stops (the sim Palette stores RGB565 and returns an
    # (r, g, b) tuple; pure red/blue round-trip exactly).
    assert layer._palette.get_rgb888(1) == (0xFF, 0, 0)
    assert layer._palette.get_rgb888(8) == (0, 0, 0xFF)


@pytest.mark.asyncio
async def test_palette_steps_clamped_to_fit_palette():
    d = await _make_display()
    c = StaticText("HI", y=12, palette=(0x102040, 0x88CCFF), palette_steps=99)
    await c.render(d)
    assert c._grad.steps == text_fill.MAX_PALETTE_STEPS   # 15
    # value_count = steps + transparent <= 16
    assert c._grad.steps + 1 <= 16


@pytest.mark.asyncio
async def test_single_colour_palette_is_flat_fill():
    d = await _make_display()
    c = StaticText("HI", y=12, palette=(0x33AA77,))
    await c.render(d)
    layer = c._grad
    assert layer.steps == 1
    # Every lit pixel uses the one ramp slot (a flat fill, no gradient).
    used = {layer._bitmap[x, y]
            for x in range(layer.width) for y in range(layer._bitmap.height)
            if layer._bitmap[x, y]}
    assert used == {1}


# --- baseline alignment: gradient lands where mono lands --------------------

@pytest.mark.asyncio
async def test_gradient_aligns_vertically_with_mono_text():
    d_mono = await _make_display()
    d_grad = await _make_display()
    await _render_to_matrix(d_mono, StaticText("ABC", x=2, y=12))
    await _render_to_matrix(
        d_grad, StaticText("ABC", x=2, y=12, palette=(0xFFFFFF, 0x808080)))
    mono = _lit_rows(d_mono)
    grad = _lit_rows(d_grad)
    assert mono and grad
    # Same vertical band (allow a 1px tolerance for the baseline rounding).
    assert abs(min(mono) - min(grad)) <= 1
    assert abs(max(mono) - max(grad)) <= 1


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["Big Thunder", "Jungle Cruise",
                                  "Space Mountain", "jolly"])
async def test_gradient_matches_mono_baseline_with_descenders(text):
    # Regression: pixels_from_font_text used to top-align every glyph, so mixed-case
    # text with descenders (g/j/p/q/y) floated short letters up and clipped caps.
    # Gradient text must land in the SAME rows as the flat draw_text() path.
    d_mono = await _make_display()
    d_grad = await _make_display()
    await _render_to_matrix(d_mono, StaticText(text, x=0, y=5))
    await _render_to_matrix(
        d_grad, StaticText(text, x=0, y=5, palette=(0xFFFFFF, 0x808080)))
    mono = _lit_rows(d_mono)
    grad = _lit_rows(d_grad)
    assert mono and grad
    assert abs(min(mono) - min(grad)) <= 1
    assert abs(max(mono) - max(grad)) <= 1


class _StubBitmap:
    def __init__(self, w, h):
        self._w, self._h = w, h

    @property
    def width(self):
        return self._w

    def __getitem__(self, xy):
        x, y = xy
        return 1 if (0 <= x < self._w and 0 <= y < self._h) else 0


class _StubFont:
    """Two equal-height glyphs: a cap on the baseline and a 2px descender."""
    GLYPHS = {
        ord("A"): {"bitmap": _StubBitmap(3, 6), "width": 3, "height": 6,
                   "x_offset": 0, "y_offset": 0, "dx": 4, "dy": 0},
        ord("g"): {"bitmap": _StubBitmap(3, 6), "width": 3, "height": 6,
                   "x_offset": 0, "y_offset": -2, "dx": 4, "dy": 0},
    }

    def get_glyph(self, cp):
        return self.GLYPHS.get(cp)


def test_pixels_baseline_aligns_descender_below_caps():
    # Font-independent: the descender's y_offset must drop it below the cap's
    # baseline, not top-align both glyphs to the same row.
    from scrollkit.display.text_pixels import pixels_from_font_text, font_text_ascent
    f = _StubFont()
    assert font_text_ascent(f, "Ag") == 6              # tallest glyph above baseline
    px = pixels_from_font_text(f, "Ag", x=0, y=0)
    a_rows = [y for (x, y) in px if x < 4]              # 'A' (advance 4) is first
    g_rows = [y for (x, y) in px if x >= 4]             # 'g' is second
    assert (min(a_rows), max(a_rows)) == (0, 5)         # cap at top, sits on baseline
    assert (min(g_rows), max(g_rows)) == (2, 7)         # descender drops 2px below it


class _FullCellBitmap:
    """A 6x12 cell with ink only on `lit_rows` (full glyph width)."""
    def __init__(self, lit_rows):
        self._lit = set(lit_rows)

    @property
    def width(self):
        return 6

    def __getitem__(self, xy):
        x, y = xy
        return 1 if (0 <= x < 6 and y in self._lit) else 0


class _FullCellGlyph:
    def __init__(self, lit_rows):
        self.bitmap = _FullCellBitmap(lit_rows)
        self.width = 6
        self.height = 12          # FULL CELL — like the device BuiltinFont
        self.dx = 0
        self.dy = 0               # baseline buried in the cell, not in the metrics
        self.shift_x = 6
        self.shift_y = 0
        self.tile_index = 0


class _FullCellFont:
    """Mimics the device's terminalio BuiltinFont: 6x12 full cells, baseline row 10.

    Recorded from a real MatrixPortal S3 (CP 10.2.1): caps ink rows 2-9, x-height
    4-9, descenders 4-11. The trimmed-BDF simulator font never exercises this, so
    this fixture is how the headless suite guards the device case.
    """
    GLYPHS = {
        ord("A"): list(range(2, 10)),    # cap, sits on the baseline (bottom row 9)
        ord("x"): list(range(4, 10)),    # x-height, same baseline
        ord("p"): list(range(4, 12)),    # descender, drops to row 11
    }

    def get_glyph(self, cp):
        rows = self.GLYPHS.get(cp)
        return _FullCellGlyph(rows) if rows is not None else None


def test_full_cell_font_baseline_from_ink_not_cell_height():
    # Regression for the hardware-only clip: max(height+y_offset) == 12 (cell bottom)
    # would shove the text up; the real baseline (from ink bottoms) is row 10.
    from scrollkit.display.text_pixels import font_text_ascent, pixels_from_font_text
    f = _FullCellFont()
    assert font_text_ascent(f, "Apx") == 10        # NOT 12
    assert font_text_ascent(f, "AAAx") == 10
    px = pixels_from_font_text(f, "Apx", 0, 0)
    ys = [y for _x, y in px]
    assert min(ys) == 2 and max(ys) == 11          # cap top to descender bottom


@pytest.mark.asyncio
async def test_gradient_full_cell_font_does_not_clip_top():
    from scrollkit.display.gradient_text import GradientTextLayer
    d = await _make_display()
    d.font = _FullCellFont()                        # pretend the device font
    layer = GradientTextLayer("Apx", y=5, palette=(0xFFFFFF, 0x808080))
    layer.build(d)
    assert layer._tile.y == -1                      # y + 4 - baseline(10)
    top = min(y for x in range(layer.width) for y in range(layer._bitmap.height)
              if layer._bitmap[x, y])
    assert layer._tile.y + top >= 0                 # topmost ink on-panel, not clipped


def test_equal_height_run_unchanged_by_baseline_fix():
    # Backward-compat: a uniform-height run (digits / ALL-CAPS) is identical to the
    # old top-aligned behaviour — every glyph starts at row y.
    from scrollkit.display.text_pixels import pixels_from_font_text
    f = _StubFont()
    px = pixels_from_font_text(f, "AA", x=0, y=3)
    assert min(y for _, y in px) == 3                   # top row == y (no shift)
    assert max(y for _, y in px) == 8                   # y + height - 1


# --- scrollability ----------------------------------------------------------

@pytest.mark.asyncio
async def test_gradient_scrolling_text_moves_and_completes():
    d = await _make_display()
    c = ScrollingText("HELLO", y=12, speed=60,
                      palette=depth_palette(0x66CCFF, 0.4))
    await c.start()
    await c.render(d)
    first_x = c._grad.x
    await c.render(d)
    second_x = c._grad.x
    assert second_x < first_x                      # it scrolls leftwards
    # Run until it scrolls off the left edge and completes.
    for _ in range(400):
        if c.is_complete:
            break
        await c.render(d)
    assert c.is_complete


@pytest.mark.asyncio
async def test_gradient_static_mode_centers_and_holds():
    d = await _make_display()
    c = ScrollingText("HI", y=12, speed=0, palette=(0xFFAA00, 0x884400))
    await c.start()
    await c.render(d)
    assert c._grad is not None
    assert c._grad.x >= 0                           # positioned on-screen


# --- lifecycle --------------------------------------------------------------

@pytest.mark.asyncio
async def test_stop_detaches_layer_and_start_rebuilds():
    d = await _make_display()
    c = StaticText("ABC", x=2, y=12, palette=(0xFF0000, 0x00FF00))
    await c.start()
    await c.render(d)
    assert len(d._layer_group) == 1                 # one gradient layer attached
    await c.stop()
    assert len(d._layer_group) == 0                 # detached on stop
    assert c._grad is None
    # Cycled back through a queue: start() + render() must re-add the layer.
    await c.start()
    await c.render(d)
    assert len(d._layer_group) == 1


@pytest.mark.asyncio
async def test_layer_rebuilt_when_text_changes():
    d = await _make_display()
    c = StaticText("A", x=0, y=12, palette=(0xFF0000, 0x0000FF))
    await c.render(d)
    w1 = c._grad.width
    c.text = "ABCDEF"
    await c.render(d)
    assert c._grad.width != w1                       # rebuilt for the new text
    assert len(d._layer_group) == 1                  # old layer not orphaned


# --- no regression on the mono path -----------------------------------------

@pytest.mark.asyncio
async def test_mono_static_text_uses_draw_text_path():
    stub = _StubDisplay()
    c = StaticText("HELLO", x=3, y=12, color=0x00AAFF)   # no palette
    await c.render(stub)
    assert stub.draws == [("HELLO", 3, 12, 0x00AAFF)]
    assert c._grad is None


@pytest.mark.asyncio
async def test_gradient_falls_back_to_mono_without_a_font():
    # A display with no .font (headless) must not crash — it draws flat instead.
    stub = _StubDisplay()
    c = StaticText("HELLO", x=3, y=12, palette=(0xFF0000, 0x0000FF))
    await c.render(stub)
    assert len(stub.draws) == 1
    assert c._grad is None


# --- feasibility ------------------------------------------------------------

def _gradient_app(content_factory):
    from scrollkit.app.base import ScrollKitApp

    class _App(ScrollKitApp):
        def __init__(self):
            super().__init__(enable_web=False, update_interval=10)
            self._c = None

        async def create_display(self):
            from scrollkit.display.simulator import SimulatorDisplay
            return SimulatorDisplay(width=64, height=32)

        async def prepare_display_content(self):
            return self._c

        async def setup(self):
            self._c = content_factory()

    return _App()


def test_static_gradient_passes_strict_and_renders():
    from scrollkit.dev import run_headless
    app = _gradient_app(
        lambda: StaticText("OPEN", x=4, y=12, palette=depth_palette(0x66CCFF, 0.4)))
    result = run_headless(app, frames=90, hardware=True, strict=True)
    assert result.errors == [], result.errors
    assert result.ok is True                      # visible, no feasibility bust


def test_scrolling_gradient_is_strict_feasible():
    # Few enough frames that the banner stays on-screen; we only assert the strict
    # feasibility gate never trips (zero per-frame pixel writes after the build).
    from scrollkit.dev import run_headless
    app = _gradient_app(
        lambda: ScrollingText("GRADIENT TEXT", y=12, speed=30,
                              palette=(0xA0E8FF, 0x206080), direction="vertical"))
    result = run_headless(app, frames=30, hardware=True, strict=True)
    assert result.errors == [], result.errors


def test_feasibility_metadata_on_public_classes():
    for cls in (StaticText, ScrollingText):
        feas = getattr(cls, "FEASIBILITY", None)
        assert isinstance(feas, dict)
        assert feas["hardware_safe"] is True
        assert feas["allocates_per_frame"] is False
        assert feas["max_pixel_writes_per_frame"] == 0


# --- relocation: text_render is now a re-export shim ------------------------

def test_text_render_shim_re_exports_relocated_helpers():
    from scrollkit.display import text_pixels as tp
    from scrollkit.effects import text_render as tr
    # Same objects via every historical import path (no behavioural drift).
    assert tr.pixels_from_font_text is tp.pixels_from_font_text
    assert tr.font_text_width is tp.font_text_width
    assert tr._glyph_fields is tp._glyph_fields
    assert tr._MISSING_ADVANCE == tp._MISSING_ADVANCE


# --- capabilities catalog ---------------------------------------------------

def test_capabilities_advertises_text_fills_and_feasibility():
    from scrollkit.dev import capabilities
    cat = capabilities()

    tf = cat["text_fills"]["gradient"]
    assert tf["directions"] == list(text_fill.gradient_directions())
    assert tf["default_direction"] == "vertical"
    assert tf["max_palette_steps"] == text_fill.MAX_PALETTE_STEPS

    by_name = {t["name"]: t for t in cat["content_types"]}
    for name in ("StaticText", "ScrollingText"):
        params = [p["name"] for p in by_name[name]["params"]]
        assert "palette" in params and "direction" in params
        assert by_name[name]["feasibility"]["hardware_safe"] is True

    util_names = {u["name"] for u in cat["color_utilities"]}
    assert "depth_palette" in util_names and "gradient" in util_names
    # depth_palette is a transform, NOT a named colour.
    assert "depth_palette" not in cat.get("named_colors", {})
