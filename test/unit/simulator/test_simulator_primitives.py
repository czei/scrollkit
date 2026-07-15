"""Direct contracts for simulator shims that are otherwise only indirect paths."""

from scrollkit.simulator.adafruit_bitmap_font.glyph_cache import GlyphCache
from scrollkit.simulator.core.led_matrix import LEDMatrix
from scrollkit.simulator.displayio.fourwire import FourWire


class _PerformanceProbe:
    enabled = True

    def __init__(self):
        self.operations = []
        self.gc_calls = 0

    def simulate_instruction_delay(self, value):
        self.operations.append(("pixel", value))

    def simulate_io_operation(self, value):
        self.operations.append(("io", value))

    def simulate_gc_pause(self):
        self.gc_calls += 1


def test_glyph_cache_is_lru_and_replacing_a_key_does_not_grow_it():
    cache = GlyphCache(max_glyphs=2)
    cache.put(65, object(), {"dx": 4})
    cache.put(66, object(), {"dx": 5})
    assert cache.get(65) == {"dx": 4}  # A is now most recently used.

    cache.put(67, object(), {"dx": 6})
    assert cache.get(66) is None
    assert cache.get(65) == {"dx": 4}
    assert cache.get(67) == {"dx": 6}

    cache.put(67, object(), {"dx": 7})
    assert len(cache) == 2 and cache.get(67) == {"dx": 7}
    cache.clear()
    assert len(cache) == 0


def test_fourwire_preserves_constructor_values_and_is_a_safe_context_manager():
    wire = FourWire("spi", command="dc", chip_select="cs", reset="rst",
                    baudrate=1_000_000, polarity=1, phase=1)
    assert (wire.spi_bus, wire.command, wire.chip_select, wire.reset_pin) == (
        "spi", "dc", "cs", "rst")
    assert (wire.baudrate, wire.polarity, wire.phase) == (1_000_000, 1, 1)
    with wire as active:
        assert active is wire and wire._locked
        wire.send(0x2A, b"\x00")
        wire.reset()
    assert not wire._locked


def test_headless_led_matrix_updates_buffer_and_accounts_one_refresh():
    perf = _PerformanceProbe()
    matrix = LEDMatrix(2, 1, headless=True, performance_manager=perf)
    matrix.set_pixel(0, 0, 0x123456)
    matrix.render()

    assert matrix.get_pixel(0, 0) == (0x12, 0x34, 0x56)
    assert perf.operations == [("pixel", 3), ("io", "display_refresh")]
    assert perf.gc_calls == 1
    assert not matrix.pixel_buffer.is_dirty()


def test_led_matrix_brightness_and_posterization_are_bounded_and_predictable():
    matrix = LEDMatrix(1, 1, headless=True, bit_depth=4)
    matrix.set_brightness(-1)
    assert matrix.brightness == 0.0
    matrix.set_brightness(2)
    assert matrix.brightness == 1.0
    assert matrix._posterize_color((127, 128, 255)) == (119, 136, 255)
    matrix.posterize = False
    assert matrix._posterize_color((127, 128, 255)) == (127, 128, 255)
