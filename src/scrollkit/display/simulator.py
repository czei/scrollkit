"""Simulator display implementation for SLDK.

Provides display interface using the LED simulator for desktop development.
"""

from __future__ import annotations

import sys
try:
    from typing import Any, Optional
except ImportError:  # CircuitPython has no 'typing' module
    pass

from ..exceptions import SimulatorError

# Verify we're NOT on CircuitPython
if hasattr(sys, 'implementation') and sys.implementation.name == 'circuitpython':
    raise ImportError("Simulator display cannot be used on CircuitPython")

try:
    import asyncio
except ImportError:
    raise ImportError("Simulator requires asyncio")

try:
    from scrollkit.simulator.devices.matrixportal_s3 import MatrixPortalS3
    from scrollkit.simulator import displayio
    from scrollkit.simulator.adafruit_bitmap_font import bitmap_font
    from scrollkit.simulator.adafruit_display_text.label import Label
    from scrollkit.simulator.terminalio import FONT as terminalio_FONT
    from scrollkit.simulator import terminalio as simulator_terminalio
    terminalio = simulator_terminalio
    terminalio.FONT = terminalio_FONT
except ImportError:
    raise ImportError(
        "SLDK simulator not available. "
        "Ensure all SLDK components are properly installed."
    )

from .interface import DisplayInterface
from ._graphics import GraphicsMixin


class SimulatorDisplay(GraphicsMixin, DisplayInterface):
    """Simulator display implementation for desktop development."""
    
    def __init__(self, width: int = 64, height: int = 32, scale: int = 10,
                 *, hardware_timing: bool = False, throttle: bool = False,
                 strict: bool = False):
        """Initialize simulator display.

        Args:
            width: Display width in pixels
            height: Display height in pixels
            scale: Scale factor for window size
            hardware_timing: Model how slow the real CircuitPython device would
                run (read the estimate via feasibility_report()). Off by default;
                also enabled by the env var SCROLLKIT_HW_SIM=1.
            throttle: When hardware_timing is on, also sleep so the window crawls
                at the modeled hardware speed (off by default; tests never use it).
            strict: Enforce the feasibility gate — a sustained over-budget run (or
                a catastrophic single frame, or a RAM breach) raises
                FeasibilityError instead of just warning. Implies hardware_timing
                (you can't gate a model you aren't running). Also enabled by
                SCROLLKIT_HW_STRICT=1. Off by default.
        """
        self._width: int = width
        self._height: int = height
        self._scale: int = scale
        # Hardware-realism simulation (opt-in).
        self._hardware_timing: bool = hardware_timing
        self._throttle: bool = throttle
        self._strict: bool = strict
        self._perf: Any = None
        # Full brightness by default so content is clearly visible in the
        # simulator. (At 1.0 the LED renderer also applies its high-visibility
        # enhancement.) Real hardware dims via its own brightness setting.
        self._brightness: float = 1.0
        
        # Simulator components
        self.device: Any = None
        self.matrix: Any = None
        self.display: Any = None
        
        # Display groups. main_group = [_content_group (below), _layer_group
        # (above)]; _content_group holds the fill background + pooled Labels and
        # is emptied each frame by clear(); _layer_group holds persistent effect
        # layers (overlay-mask / bitmap-text / paint canvas) and is never touched
        # by clear() (see GraphicsMixin / D11).
        self.main_group: Any = None
        self._content_group: Any = None
        self._layer_group: Any = None
        self._gfx: Any = None
        self._initialized: bool = False
        
        # Default font
        self.font: Any = terminalio.FONT
        
        # For pygame window
        self._window_created: bool = False

        # Foreground pixels from set_pixel(), applied after each refresh.
        self._overlay_pixels: dict = {}

        # Reusable Label pool (indexed by draw order within a frame), mirroring
        # UnifiedDisplay/hardware: draw_text() reuses the pooled Label object so
        # unchanged text skips the (expensive) glyph-bitmap rebuild and nothing
        # is allocated per frame. This keeps the hardware feasibility estimate
        # honest — it only charges a text rebuild when .text actually changes.
        self._label_pool: list = []
        self._label_idx: int = 0

    @property
    def width(self) -> int:
        """Display width in pixels."""
        return self._width
        
    @property 
    def height(self) -> int:
        """Display height in pixels."""
        return self._height
    
    async def initialize(self) -> None:
        """Initialize the display simulator."""
        if self._initialized:
            return
            
        try:
            # Create simulator device
            self.device = MatrixPortalS3(
                width=self._width,
                height=self._height
            )
            # Wire hardware-timing simulation onto the device BEFORE initialize()
            # (LEDMatrix reads device.performance_manager in initialize()).
            self._maybe_enable_hardware_timing()
            self.device.initialize()
            
            # Get display components
            self.matrix = self.device.matrix
            self.display = self.device.display
            
            # Set up display groups (content below, layers above) + cache gfx.
            self.main_group = displayio.Group()
            self.display.root_group = self.main_group
            from scrollkit.simulator import bitmaptools as _bitmaptools
            self._init_graphics(displayio, _bitmaptools)

            # Initialize surface
            if hasattr(self.matrix, 'initialize_surface'):
                self.matrix.initialize_surface()
            
            # Set initial brightness
            await self.set_brightness(self._brightness)
            
            self._initialized = True
            print("Simulator display initialized")
            
        except (ImportError, OSError, SimulatorError) as e:
            print(f"Failed to initialize simulator: {e}")
            raise
    
    async def clear(self) -> None:
        """Clear the display (start a new frame)."""
        # Empty the CONTENT group so backgrounds/labels from the previous frame
        # don't accumulate. The Label *objects* survive in self._label_pool and
        # are re-appended (reused) by draw_text(), so this isn't a per-frame
        # allocation — just list membership churn (cheap on desktop). Persistent
        # effect layers live in _layer_group and are deliberately NOT cleared.
        if self._content_group is not None:
            while len(self._content_group):
                self._content_group.pop()
        self._label_idx = 0

        # Wipe the bounded-painter canvas so fill_rect drawings don't ghost across
        # frames (immediate-mode, like draw_text). One C bulk fill; layer stays.
        if getattr(self, "_paint_bitmap", None) is not None:
            self._paint_bitmap.fill(0)

        # Drop any foreground set_pixel() overlay for the new frame.
        self._overlay_pixels = {}

        # Fill with black
        if self.matrix and hasattr(self.matrix, 'fill'):
            self.matrix.fill(0x000000)
    
    async def show(self) -> bool:
        """Update the simulated display."""
        if not self.display:
            return True
            
        try:
            import pygame
            
            # Create window if needed
            if not self._window_created:
                await self.create_window()
            
            # Handle events
            if pygame.get_init() and pygame.display.get_surface():
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        return False
                    elif event.type == pygame.KEYDOWN:
                        if event.key == pygame.K_ESCAPE:
                            return False
            
            # displayio render: group -> matrix pixel buffer -> surface. This
            # already calls matrix.render() internally exactly once (== one
            # modeled hardware frame).
            self.display.refresh(minimum_frames_per_second=0)

            # Foreground set_pixel() overlay writes straight to the pixel buffer,
            # so it needs a re-render to reach the surface. Only render again when
            # an overlay is actually present: an UNCONDITIONAL second render would
            # count a second modeled frame on every show(), roughly halving the
            # estimated hardware FPS and doubling the throttle crawl (so the
            # feasibility report and the visceral throttle would disagree).
            if self._overlay_pixels and hasattr(self.matrix, 'set_pixel'):
                for (px, py), pcolor in self._overlay_pixels.items():
                    self.matrix.set_pixel(px, py, pcolor)
                if hasattr(self.matrix, 'render'):
                    self.matrix.render()

            # Copy the rendered LED matrix surface to the window.
            if pygame.get_init() and pygame.display.get_surface():
                screen = pygame.display.get_surface()
                matrix_surface = (self.matrix.get_surface()
                                  if hasattr(self.matrix, 'get_surface') else None)
                if matrix_surface:
                    screen.fill((0, 0, 0))
                    screen.blit(matrix_surface, (0, 0))
                pygame.display.flip()
            
            # Small yield for responsiveness
            await asyncio.sleep(0.001)
            
        except ImportError:
            # Pygame not available, just refresh
            self.display.refresh(minimum_frames_per_second=0)

        return True

    def screenshot(self, path):
        """Save the current display frame to an image file (PNG by extension).

        Renders whatever is currently on the simulated matrix to ``path``. Useful
        for docs, debugging, and visual tests. Returns the path on success or
        None if the simulator/pygame isn't available (e.g. on hardware).

        Example::

            await display.show()
            display.screenshot("frame.png")
        """
        try:
            import pygame
        except ImportError:
            return None
        # Prefer the rendered matrix surface; fall back to the window surface.
        surface = None
        if self.matrix is not None and hasattr(self.matrix, "get_surface"):
            surface = self.matrix.get_surface()
        if surface is None and pygame.get_init():
            surface = pygame.display.get_surface()
        if surface is None:
            return None
        try:
            pygame.image.save(surface, path)
            return path
        except (pygame.error, OSError) as e:
            print(f"screenshot failed: {e}")
            return None

    def _maybe_enable_hardware_timing(self) -> None:
        """Build a PerformanceManager if hardware timing is requested (opt-in).

        Enabled by the constructor flag or ``SCROLLKIT_HW_SIM=1``. The visceral
        "throttle" crawl is enabled by the ``throttle`` constructor flag or
        ``SCROLLKIT_HW_THROTTLE=1`` — and turning throttle on implies hardware
        timing (you can't crawl at a speed you aren't modeling).
        """
        import os
        env_sim = os.environ.get("SCROLLKIT_HW_SIM") == "1"
        env_throttle = os.environ.get("SCROLLKIT_HW_THROTTLE") == "1"
        env_strict = os.environ.get("SCROLLKIT_HW_STRICT") == "1"
        want_throttle = self._throttle or env_throttle
        want_strict = self._strict or env_strict
        # strict implies hardware timing — you can't gate a model you aren't running.
        want_timing = self._hardware_timing or env_sim or want_throttle or want_strict
        if not want_timing:
            return
        from scrollkit.simulator.core.hardware_profile import matrixportal_s3_profile
        from scrollkit.simulator.core.performance_manager import (
            PerformanceManager, set_active)
        self._perf = PerformanceManager(matrixportal_s3_profile(), enabled=True,
                                        throttle=want_throttle, strict=want_strict)
        self.device.performance_manager = self._perf   # read by LEDMatrix
        set_active(self._perf)                          # read by the Label rebuild hook

    def feasibility_report(self):
        """Estimate how this app would perform on the real hardware.

        Returns a FeasibilityReport (estimated FPS, per-frame cost breakdown,
        peak RAM vs budget, warnings). Requires hardware_timing=True (or
        SCROLLKIT_HW_SIM=1); otherwise returns a clearly-labeled disabled stub.
        """
        if self._perf is None:
            from scrollkit.simulator.core.feasibility import FeasibilityReport
            return FeasibilityReport(
                "hardware timing disabled", "DISABLED",
                "enable with SimulatorDisplay(hardware_timing=True) or SCROLLKIT_HW_SIM=1",
                False, None, 0.0, 0.0, {}, 0, 0,
                ["Hardware timing is off — no feasibility data. Enable with "
                 "hardware_timing=True or SCROLLKIT_HW_SIM=1."])
        return self._perf.report()

    async def set_pixel(self, x: int, y: int, color: int) -> None:
        """Set a single pixel (drawn on top of other content).

        Args:
            x: X coordinate
            y: Y coordinate
            color: Color as 24-bit RGB integer
        """
        if 0 <= x < self._width and 0 <= y < self._height:
            # Recorded as a foreground overlay and applied in show() AFTER the
            # displayio render. Writing straight to the matrix here would be
            # wiped by show()'s per-frame refresh() before the frame is shown.
            self._overlay_pixels[(x, y)] = color

    async def fill(self, color: int) -> None:
        """Fill the entire display with a solid background color.

        Args:
            color: Color as 24-bit RGB integer
        """
        if self._content_group is None:
            return
        # Render fill through the displayio layer: a full-screen background
        # TileGrid inserted at the bottom of the CONTENT group (behind labels,
        # below any effect layers), re-added each frame after clear() empties it.
        bitmap = displayio.Bitmap(self._width, self._height, 1)
        palette = displayio.Palette(1)
        palette[0] = color
        tile = displayio.TileGrid(bitmap, pixel_shader=palette)
        tile.x = 0
        tile.y = 0
        self._content_group.insert(0, tile)
    
    async def set_brightness(self, brightness: float) -> None:
        """Set display brightness.
        
        Args:
            brightness: Float between 0.0 and 1.0
        """
        self._brightness = max(0.0, min(1.0, brightness))
        
        if self.display:
            try:
                self.display.brightness = self._brightness
            except (AttributeError, TypeError) as e:
                print(f"Failed to set brightness: {e}")
    
    async def draw_text(self, text: str, x: int = 0, y: int = 0, color: int = 0xFFFFFF, font: Any = None) -> None:
        """Draw text on display.
        
        Args:
            text: Text to display
            x: Starting X coordinate
            y: Starting Y coordinate
            color: Text color as 24-bit RGB
            font: Font to use (uses default if None)
        """
        # Use provided font or default
        if font is None:
            font = self.font

        # Reuse the pooled Label for this draw slot; only touch .text when it
        # actually changed (a change rebuilds the glyph bitmap — the dominant
        # hardware cost the feasibility model charges for). Re-append it to the
        # group, which clear() emptied for this frame.
        idx = self._label_idx
        if idx < len(self._label_pool):
            label = self._label_pool[idx]
            if label.text != text:
                label.text = text
            if label.color != color:
                label.color = color
            label.x = x
            label.y = y
        else:
            label = Label(font, text=text, color=color)
            label.x = x
            label.y = y
            self._label_pool.append(label)
        self._content_group.append(label)
        self._label_idx += 1
    
    async def scroll_text(self, text: str, y: int = 0, color: int = 0xFFFFFF, speed: float = 0.05) -> None:
        """Scroll text across display.
        
        Args:
            text: Text to scroll
            y: Y coordinate for text
            color: Text color as 24-bit RGB
            speed: Scroll speed in seconds per pixel
        """
        # Create label
        label = Label(self.font, text=text, color=color)
        label.x = self._width  # Start from right edge
        label.y = y
        
        # Create group
        scroll_group = displayio.Group()
        scroll_group.append(label)
        self.main_group.append(scroll_group)
        
        # Estimate text width
        if hasattr(label, 'bounding_box') and label.bounding_box:
            text_width = label.bounding_box[2]
        else:
            text_width = len(text) * 6  # Fallback estimate
        
        # Scroll until text is off screen
        while label.x > -text_width:
            label.x -= 1
            await self.show()
            await asyncio.sleep(speed)
        
        # Remove the group
        self.main_group.remove(scroll_group)
    
    async def create_window(self, title: str = "SLDK Simulator") -> None:
        """Create the simulator window.
        
        Args:
            title: Window title
        """
        if self._window_created:
            return
            
        try:
            import pygame
            import os
            
            # Force window to appear with environment variables
            os.environ['SDL_VIDEO_WINDOW_POS'] = '100,100'
            os.environ['SDL_VIDEO_CENTERED'] = '1'
            
            if not pygame.get_init():
                pygame.init()
            
            # Calculate window size
            if hasattr(self.matrix, 'surface_width'):
                width = self.matrix.surface_width
                height = self.matrix.surface_height
            else:
                width = self._width * self._scale
                height = self._height * self._scale
            
            print(f"Creating pygame window: {width}x{height}")
            
            # Create window with specific flags
            screen = pygame.display.set_mode((width, height), pygame.SHOWN)
            pygame.display.set_caption(title)
            
            # Force window to front
            screen.fill((50, 50, 50))  # Dark gray background
            pygame.display.flip()
            
            print(f"Window created successfully: {title}")
            self._window_created = True
            
        except ImportError:
            # Pygame not available
            print("Pygame not available for window creation")
            pass
    
    async def run_event_loop(self) -> None:
        """Run the display event loop.
        
        This keeps the simulator window responsive.
        """
        while True:
            result = await self.show()
            if not result:
                break
            await asyncio.sleep(0.01)  # ~100 FPS max