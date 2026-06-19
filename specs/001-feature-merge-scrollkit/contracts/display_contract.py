"""
Contract: Display Interface
Public API that all display backends must satisfy.
"""

class DisplayInterface:
    """Abstract base class for all display backends."""

    @property
    def width(self) -> int:
        """Display width in pixels."""
        raise NotImplementedError

    @property
    def height(self) -> int:
        """Display height in pixels."""
        raise NotImplementedError

    async def initialize(self) -> None:
        """Initialize hardware/simulator. Must be called before any drawing."""
        raise NotImplementedError

    async def clear(self) -> None:
        """Set all pixels to black."""
        raise NotImplementedError

    async def show(self) -> None:
        """Flush the pixel buffer to the physical display."""
        raise NotImplementedError

    def set_pixel(self, x: int, y: int, color: tuple) -> None:
        """Set a single pixel. color is (r, g, b) with values 0-255."""
        raise NotImplementedError

    def fill(self, color: tuple) -> None:
        """Fill entire display with one color. color is (r, g, b)."""
        raise NotImplementedError

    def set_brightness(self, brightness: float) -> None:
        """Set display brightness. brightness is 0.0–1.0."""
        raise NotImplementedError

    def draw_text(
        self,
        text: str,
        x: int,
        y: int,
        color: tuple,
        font=None,
    ) -> None:
        """
        Draw text at (x, y). color is (r, g, b).
        font is a bitmap font object or None for the terminal font.
        """
        raise NotImplementedError


# --- Contract tests (must FAIL before implementation, PASS after) ---

def test_display_interface_is_abstract():
    """DisplayInterface must not be instantiable directly."""
    try:
        d = DisplayInterface()
        d.width  # Must raise NotImplementedError
        assert False, "Should have raised NotImplementedError"
    except NotImplementedError:
        pass


def test_unified_display_auto_detects_platform():
    """
    UnifiedDisplay must not raise ImportError.
    On desktop it uses the simulator; on CircuitPython it uses hardware.
    """
    from scrollkit.display.unified import UnifiedDisplay
    display = UnifiedDisplay()
    assert display is not None


def test_unified_display_implements_interface():
    """UnifiedDisplay must implement all DisplayInterface methods."""
    from scrollkit.display.unified import UnifiedDisplay
    from scrollkit.display.interface import DisplayInterface
    display = UnifiedDisplay()
    assert isinstance(display, DisplayInterface)
    assert hasattr(display, 'width')
    assert hasattr(display, 'height')
    assert hasattr(display, 'initialize')
    assert hasattr(display, 'clear')
    assert hasattr(display, 'show')
    assert hasattr(display, 'set_pixel')
    assert hasattr(display, 'fill')
    assert hasattr(display, 'set_brightness')
    assert hasattr(display, 'draw_text')


def test_display_width_and_height():
    """MatrixPortal S3 is 64×32. UnifiedDisplay must report correct dimensions."""
    from scrollkit.display.unified import UnifiedDisplay
    display = UnifiedDisplay()
    assert display.width == 64
    assert display.height == 32
