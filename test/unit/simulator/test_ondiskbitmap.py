"""OnDiskBitmap must read an indexed BMP's palette with every channel intact.

Regression: the simulator's OnDiskBitmap passed the raw numpy ``uint8`` channels
straight into ``rgb888_to_rgb565``, where ``(r & 0xF8) << 8`` overflowed the uint8
dtype to 0 — zeroing red and green so every indexed image rendered pure blue
(``#0000xx``). It also double-converted, since ``Palette.__setitem__`` re-converts
an int argument. Real CircuitPython ``displayio.OnDiskBitmap`` reads the BMP's
palette correctly on hardware, so this was simulator-only and silently corrupted
any app that previewed bitmaps in the sim. The fix hands ``Palette`` the plain-int
RGB tuple and lets ``__setitem__`` do the single, correct conversion.
"""

import pytest

Image = pytest.importorskip("PIL.Image")

from scrollkit.simulator.displayio.ondiskbitmap import OnDiskBitmap


def _make_indexed_bmp(path):
    """A 2x2 indexed (palettized) BMP with colors black, white, red, green."""
    img = Image.new("P", (2, 2))
    img.putpalette([0, 0, 0,  255, 255, 255,  255, 0, 0,  0, 255, 0]
                   + [0] * (256 * 3 - 12))
    img.putpixel((0, 0), 0)   # black
    img.putpixel((1, 0), 1)   # white
    img.putpixel((0, 1), 2)   # red
    img.putpixel((1, 1), 3)   # green
    img.save(str(path))
    return str(path)


def test_indexed_bmp_palette_keeps_all_channels(tmp_path):
    """White/red/green survive the load (565-rounded), not collapsed to blue."""
    palette = OnDiskBitmap(_make_indexed_bmp(tmp_path / "probe.bmp")).pixel_shader

    white = palette.get_rgb888(1)
    red = palette.get_rgb888(2)
    green = palette.get_rgb888(3)

    assert white[0] > 200 and white[1] > 200 and white[2] > 200
    assert red[0] > 200 and red[1] < 60 and red[2] < 60     # red channel intact
    assert green[1] > 200 and green[0] < 60 and green[2] < 60  # green channel intact


def test_indexed_bmp_is_not_all_blue(tmp_path):
    """The exact failure signature: before the fix every entry was #0000xx."""
    palette = OnDiskBitmap(_make_indexed_bmp(tmp_path / "probe.bmp")).pixel_shader

    reds = [palette.get_rgb888(i)[0] for i in range(len(palette))]
    greens = [palette.get_rgb888(i)[1] for i in range(len(palette))]

    assert max(reds) > 200    # some entry has real red   (was 0 for every entry)
    assert max(greens) > 200  # some entry has real green (was 0 for every entry)
