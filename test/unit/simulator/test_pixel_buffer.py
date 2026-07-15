"""Focused contract tests for the simulator's pixel-buffer foundation."""

from scrollkit.simulator.core.pixel_buffer import PixelBuffer


def test_set_get_and_out_of_bounds_pixels_use_rgb_contract():
    pixels = PixelBuffer(3, 2)
    pixels.clear_dirty()

    pixels.set_pixel(1, 1, 0x123456)
    assert pixels.get_pixel(1, 1) == (0x12, 0x34, 0x56)
    assert pixels.get_dirty_region() == (1, 1, 1, 1)

    pixels.set_pixel(-1, 0, (1, 2, 3))
    assert pixels.get_pixel(-1, 0) == (0, 0, 0)
    assert pixels.get_dirty_region() == (1, 1, 1, 1)


def test_dirty_region_accumulates_then_fill_and_clear_invalidate_all():
    pixels = PixelBuffer(4, 3)
    pixels.clear_dirty()
    pixels.set_pixel(3, 2, (1, 2, 3))
    pixels.set_pixel(1, 0, (4, 5, 6))
    assert pixels.get_dirty_region() == (1, 0, 3, 2)

    pixels.fill((9, 8, 7))
    assert pixels.is_dirty() and pixels.get_dirty_region() is None
    assert pixels.get_pixel(0, 0) == (9, 8, 7)

    pixels.clear()
    assert pixels.get_pixel(3, 2) == (0, 0, 0)
    pixels.clear_dirty()
    assert not pixels.is_dirty() and pixels.get_dirty_region() is None


def test_blit_clips_and_honors_transparent_key():
    source = PixelBuffer(2, 2)
    source.set_pixel(0, 0, 0x000000)
    source.set_pixel(1, 0, 0xFF0000)
    source.set_pixel(0, 1, 0x00FF00)
    source.set_pixel(1, 1, 0x0000FF)

    dest = PixelBuffer(2, 2)
    dest.fill(0x112233)
    dest.clear_dirty()
    dest.blit(source, x=-1, y=0, key_color=0x000000)

    # Source column zero is clipped; column one lands at destination x=0.
    assert dest.get_pixel(0, 0) == (255, 0, 0)
    assert dest.get_pixel(0, 1) == (0, 0, 255)
    assert dest.get_pixel(1, 0) == (0x11, 0x22, 0x33)
    assert dest.get_dirty_region() == (0, 0, 0, 1)


def test_brightness_scales_pixels_and_marks_full_buffer_dirty():
    pixels = PixelBuffer(2, 1)
    pixels.fill((200, 100, 50))
    pixels.clear_dirty()
    pixels.apply_brightness(0.5)

    assert pixels.get_pixel(0, 0) == (100, 50, 25)
    assert pixels.is_dirty() and pixels.get_dirty_region() is None
