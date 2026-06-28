# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Unified display implementation for SLDK.

Provides a unified interface that works on both CircuitPython hardware
and desktop development environments using the LED simulator.
"""

from __future__ import annotations

import sys
import gc
try:
    from typing import Any, Dict, List, Optional
except ImportError:  # CircuitPython has no 'typing' module
    pass

from ..exceptions import DisplayError, SimulatorError

try:
    # Desktop Python
    import asyncio
except ImportError:
    # CircuitPython
    import asyncio

# Platform detection
IS_CIRCUITPYTHON = hasattr(sys, 'implementation') and sys.implementation.name == 'circuitpython'

# Conditional imports based on platform
if IS_CIRCUITPYTHON:
    import displayio
    import terminalio
    try:
        from adafruit_bitmap_font import bitmap_font
    except ImportError:
        bitmap_font = None
    from adafruit_display_text.label import Label
else:
    # SLDK Simulator imports - these will be optional
    try:
        from scrollkit.simulator.devices.matrixportal_s3 import MatrixPortalS3
        from scrollkit.simulator import displayio
        from scrollkit.simulator.adafruit_bitmap_font import bitmap_font
        from scrollkit.simulator.adafruit_display_text.label import Label
        from scrollkit.simulator.terminalio import FONT as terminalio_FONT
        # Create module alias for consistency
        from scrollkit.simulator import terminalio as simulator_terminalio
        terminalio = simulator_terminalio
        terminalio.FONT = terminalio_FONT
        LED_SIMULATOR_AVAILABLE = True
    except ImportError:
        LED_SIMULATOR_AVAILABLE = False
        displayio = None
        terminalio = None
        bitmap_font = None
        Label = None

from .interface import DisplayInterface
from ._graphics import GraphicsMixin
from .boards import resolve_board


class UnifiedDisplay(GraphicsMixin, DisplayInterface):
    """Unified display that auto-detects hardware vs simulator."""
    
    def __init__(self, width=None, height=None, bit_depth: int = 4, board=None):
        """Initialize unified display.

        Args:
            width: Display width in pixels. ``None`` uses the board's default
                (64 on both supported boards).
            height: Display height in pixels. ``None`` uses the board's default
                (32 on both supported boards).
            bit_depth: Color bits per channel on hardware (1-6). Measured on a
                MatrixPortal S3, a full refresh costs ~4.5 ms at bit_depth<=4 but
                ~13.7 ms at bit_depth 6 (~3x) — so 4 is the speed/quality sweet
                spot for scrolling/data displays. Raise to 6 only if you need
                smooth color gradients and can afford the lower frame rate.
            board: Canonical board id (e.g. ``"adafruit_matrixportal_s3"`` or
                ``"pimoroni_interstate75_w"``). ``None`` auto-detects on hardware
                via ``board.board_id``, honors ``SCROLLKIT_HW_BOARD``, and falls
                back to the MatrixPortal S3 (see ``display/boards.py``).
        """
        spec = resolve_board(board)
        self._board_id: str = spec.board_id
        self._board_spec = spec
        self._width: int = spec.default_width if width is None else width
        self._height: int = spec.default_height if height is None else height
        self._bit_depth: int = bit_depth
        self._brightness: float = 0.3

        # Platform specific components
        self.hardware: Any = None
        self.matrix: Any = None
        self.display: Any = None
        self.device: Any = None  # For simulator
        self._perf: Any = None    # hardware-realism PerformanceManager (opt-in, desktop)

        # Display components
        # main_group = [_content_group (below), _layer_group (above)]; labels +
        # fill live in _content_group, persistent effect layers in _layer_group
        # (never disturbed by the per-frame label reset). See GraphicsMixin / D11.
        self.main_group: Any = None
        self._content_group: Any = None
        self._layer_group: Any = None
        self._gfx: Any = None
        self._initialized: bool = False

        # For text rendering
        self.font: Any = None
        # Reusable Label pool, indexed by draw-order within a frame. draw_text()
        # pulls the next slot and mutates it in place; scrolling/static text then
        # reuses one Label forever instead of allocating (and leaking) a new
        # Label+Group every frame. Reset each frame in clear().
        self._label_pool: List[Any] = []
        self._label_idx: int = 0
        # Parallel pool for integer-scaled labels (draw_text_scaled). Kept
        # separate from _label_pool so a scaled and an unscaled draw in the same
        # frame never thrash one Label's .scale attribute. Same discipline:
        # reuse + mutate in place, reset index in clear(), hide-unused in show().
        self._scaled_pool: List[Any] = []
        self._scaled_idx: int = 0

    @property
    def width(self) -> int:
        """Display width in pixels."""
        return self._width
        
    @property
    def height(self) -> int:
        """Display height in pixels."""
        return self._height
    
    async def initialize(self) -> None:
        """Initialize the display hardware or simulator."""
        if self._initialized:
            return
            
        try:
            # Platform-specific hardware initialization
            self._initialize_hardware()
            
            # Set up display groups (content below, layers above) + cache gfx.
            self.main_group = displayio.Group()
            self.display.root_group = self.main_group
            if IS_CIRCUITPYTHON:
                import bitmaptools as _bitmaptools
            else:
                from scrollkit.simulator import bitmaptools as _bitmaptools
            self._init_graphics(displayio, _bitmaptools)

            # Load default font
            self.font = terminalio.FONT if terminalio else None
            
            # Set initial brightness
            await self.set_brightness(self._brightness)
            
            self._initialized = True
            print(f"Display initialized ({'CircuitPython' if IS_CIRCUITPYTHON else 'Simulator'})")
            
        except (DisplayError, ImportError, OSError) as e:
            print(f"Failed to initialize display: {e}")
            raise
    
    def _initialize_hardware(self) -> None:
        """Initialize the display hardware/simulator."""
        if IS_CIRCUITPYTHON:
            # Build the RGB matrix via the resolved board's constructor. bit_depth
            # is passed explicitly (4 by default) rather than relying on a library
            # default — it's the single biggest refresh-cost lever (~3x between
            # bit_depth 4 and 6). Per-board pin wiring lives in display/boards.py.
            try:
                self.hardware, self.display, self.matrix = (
                    self._board_spec.make_matrix(
                        self._width, self._height, self._bit_depth))
            except ImportError:
                raise ImportError(
                    "No compatible hardware found for board %r" % self._board_id)
        else:
            if not LED_SIMULATOR_AVAILABLE:
                raise ImportError(
                    "LED simulator not available. "
                    "Install with: pip install sldk[simulator]"
                )
            
            # Create MatrixPortal S3 device
            self.device = MatrixPortalS3(width=self._width, height=self._height)
            # Wire hardware-timing simulation BEFORE initialize() (LEDMatrix reads
            # device.performance_manager there). Opt-in via env var.
            self._maybe_enable_hardware_timing()
            self.device.initialize()
            
            # Get references to the display components
            self.matrix = self.device.matrix
            self.display = self.device.display
            self.hardware = self.device  # For compatibility
            
            # Initialize surface for simulator
            if hasattr(self.matrix, 'initialize_surface'):
                self.matrix.initialize_surface()

    def _maybe_enable_hardware_timing(self) -> None:
        """Model real-hardware timing/RAM on desktop, like SimulatorDisplay.

        Opt-in via SCROLLKIT_HW_SIM=1 (estimate/feasibility),
        SCROLLKIT_HW_THROTTLE=1 (also crawl at the modeled speed), or
        SCROLLKIT_HW_STRICT=1 (enforce the feasibility gate — raise
        FeasibilityError on a sustained over-budget run). This whole method only
        runs on the desktop simulator path; it is a no-op on CircuitPython, where
        the device runs at real speed and there is no model to gate.
        """
        import os
        env_sim = os.environ.get("SCROLLKIT_HW_SIM") == "1"
        env_throttle = os.environ.get("SCROLLKIT_HW_THROTTLE") == "1"
        env_strict = os.environ.get("SCROLLKIT_HW_STRICT") == "1"
        if not (env_sim or env_throttle or env_strict):
            return
        try:
            from scrollkit.simulator.core.hardware_profile import profile_for
            from scrollkit.simulator.core.performance_manager import (
                PerformanceManager, set_active)
        except ImportError:
            return
        self._perf = PerformanceManager(profile_for(self._board_id), enabled=True,
                                        throttle=env_throttle, strict=env_strict)
        self.device.performance_manager = self._perf   # read by LEDMatrix
        set_active(self._perf)                          # read by the Label rebuild hook

    def feasibility_report(self):
        """Estimate how this app would perform on the real hardware.

        Mirrors SimulatorDisplay.feasibility_report(); returns a disabled stub
        unless hardware timing was enabled (via the env vars above).
        """
        if self._perf is None:
            from scrollkit.simulator.core.feasibility import FeasibilityReport
            return FeasibilityReport(
                "hardware timing disabled", "DISABLED",
                "enable with SCROLLKIT_HW_SIM=1 or SCROLLKIT_HW_THROTTLE=1",
                False, None, 0.0, 0.0, {}, 0, 0,
                ["Hardware timing is off — no feasibility data. Enable with "
                 "SCROLLKIT_HW_SIM=1."])
        return self._perf.report()

    async def clear(self) -> None:
        """Clear the display (start a new frame).

        Resets the per-frame Label slot index so draw_text() reuses pooled
        Labels instead of allocating new ones. Labels not redrawn this frame are
        hidden in show().
        """
        self._label_idx = 0
        self._scaled_idx = 0

        # Wipe the bounded-painter canvas so fill_rect drawings don't ghost across
        # frames (immediate-mode, like draw_text). One C bulk fill; layer stays.
        if getattr(self, "_paint_bitmap", None) is not None:
            self._paint_bitmap.fill(0)

        # Clear any pixel data drawn outside the displayio group (e.g. set_pixel).
        if self.matrix and hasattr(self.matrix, 'fill'):
            self.matrix.fill(0x000000)

    def _hide_unused_labels(self) -> None:
        """Hide pooled Labels that weren't drawn this frame (frame drew fewer)."""
        for i in range(self._label_idx, len(self._label_pool)):
            lbl = self._label_pool[i]
            if hasattr(lbl, "hidden"):
                lbl.hidden = True
        for i in range(self._scaled_idx, len(self._scaled_pool)):
            lbl = self._scaled_pool[i]
            if hasattr(lbl, "hidden"):
                lbl.hidden = True

    async def show(self) -> bool:
        """Update the physical display."""
        self._hide_unused_labels()
        if IS_CIRCUITPYTHON:
            if self.hardware:
                self.hardware.display.refresh(minimum_frames_per_second=0)
            return True
        else:
            # Simulator needs pygame event handling
            return await self._update_simulator()
    
    async def _update_simulator(self) -> bool:
        """Update the simulator display."""
        if not self.display:
            return True
            
        try:
            import pygame
            
            # Check if pygame is initialized
            if not pygame.get_init():
                self.display.refresh(minimum_frames_per_second=0)
                return True
            
            # Check if window exists
            if pygame.display.get_surface() is None:
                self.display.refresh(minimum_frames_per_second=0)
                return True
            
            # Handle events to keep window responsive
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return False
            
            # display.refresh() already renders the matrix to its surface exactly
            # once (== one modeled hardware frame). Do NOT call matrix.render()
            # again below — a second render would double-count modeled frames and
            # make the feasibility estimate disagree with the throttle crawl.
            self.display.refresh(minimum_frames_per_second=0)

            # Blit the rendered LED matrix surface to the pygame window.
            screen = pygame.display.get_surface()
            if screen and hasattr(self.matrix, 'get_surface'):
                screen.fill((0, 0, 0))
                matrix_surface = self.matrix.get_surface()
                if matrix_surface:
                    screen.blit(matrix_surface, (0, 0))

            pygame.display.flip()
            
            # Small yield for responsiveness
            await asyncio.sleep(0.001)
            
        except ImportError:
            # Pygame not available
            if self.display:
                self.display.refresh(minimum_frames_per_second=0)
        
        return True
    
    async def set_pixel(self, x: int, y: int, color: int) -> None:
        """Set a single pixel color.
        
        Args:
            x: X coordinate
            y: Y coordinate
            color: Color as 24-bit RGB integer
        """
        if self.matrix and 0 <= x < self._width and 0 <= y < self._height:
            # Try different methods to set pixel
            if hasattr(self.matrix, 'set_pixel'):
                self.matrix.set_pixel(x, y, color)
            elif hasattr(self.matrix, '__setitem__'):
                try:
                    self.matrix[x, y] = color
                except (TypeError, AttributeError):
                    # Try alternative indexing
                    try:
                        self.matrix[y][x] = color
                    except (TypeError, AttributeError, IndexError):
                        # Fallback - print for debugging
                        print(f"Cannot set pixel at ({x}, {y}) to {color:06X}")
            else:
                print(f"Matrix object has no set_pixel method: {type(self.matrix)}")
    
    async def fill(self, color: int) -> None:
        """Fill entire display with color.
        
        Args:
            color: Color as 24-bit RGB integer
        """
        if self.matrix and hasattr(self.matrix, 'fill'):
            self.matrix.fill(color)
        else:
            # Fallback to pixel-by-pixel
            await super().fill(color)
    
    async def set_brightness(self, brightness: float) -> None:
        """Set display brightness.
        
        Args:
            brightness: Float between 0.0 and 1.0
        """
        self._brightness = max(0.0, min(1.0, brightness))
        
        if self.display:
            try:
                if IS_CIRCUITPYTHON:
                    self.hardware.display.brightness = self._brightness
                else:
                    self.display.brightness = self._brightness
            except (AttributeError, TypeError) as e:
                print(f"Failed to set brightness: {e}")
    
    async def draw_text(self, text: str, x: int = 0, y: int = 0, color: int = 0xFFFFFF, font: Any = None) -> None:
        """Draw text on display using displayio labels.
        
        Args:
            text: Text to display
            x: Starting X coordinate
            y: Starting Y coordinate
            color: Text color as 24-bit RGB
            font: Font to use (uses default if None)
        """
        if not Label:
            # Label class not available
            return

        # Use provided font or default
        if font is None:
            font = self.font
        if font is None:
            return

        # Pull the next Label slot for this frame and mutate it in place. Only
        # touch .text when it actually changed (a text change rebuilds the glyph
        # bitmap — the dominant per-frame cost on hardware; moving .x/.y is cheap).
        idx = self._label_idx
        if idx < len(self._label_pool):
            label = self._label_pool[idx]
            if label.text != text:
                label.text = text
            if label.color != color:
                label.color = color
            label.x = x
            label.y = y
            if hasattr(label, "hidden"):
                label.hidden = False
        else:
            label = Label(font, text=text, color=color)
            label.x = x
            label.y = y
            self._label_pool.append(label)
            self._content_group.append(label)   # added directly; no per-label wrapper Group
        self._label_idx += 1

    async def draw_text_scaled(self, text: str, x: int = 0, y: int = 0,
                               color: int = 0xFFFFFF, scale: int = 2,
                               font: Any = None) -> None:
        """Draw integer-scaled text (e.g. a large number), reusing a pooled Label.

        Like :meth:`draw_text` but renders at ``scale`` x the font's native size.
        Uses a dedicated scaled-Label pool so mixing scaled and unscaled draws in
        the same frame never thrashes a Label's ``.scale``; per-frame work stays
        allocation-free after the first frame.

        Args:
            text: Text to display.
            x: Starting X coordinate.
            y: Starting Y coordinate (the font baseline, as with ``draw_text``).
            color: Text color as 24-bit RGB.
            scale: Integer magnification factor (>=1).
            font: Font to use (default font if None).
        """
        if not Label:
            return
        if font is None:
            font = self.font
        if font is None:
            return
        if scale < 1:
            scale = 1

        idx = self._scaled_idx
        if idx < len(self._scaled_pool):
            label = self._scaled_pool[idx]
            if label.text != text:
                label.text = text
            if label.color != color:
                label.color = color
            if getattr(label, "scale", scale) != scale:
                label.scale = scale
            label.x = x
            label.y = y
            if hasattr(label, "hidden"):
                label.hidden = False
        else:
            label = Label(font, text=text, color=color, scale=scale)
            label.x = x
            label.y = y
            self._scaled_pool.append(label)
            self._content_group.append(label)
        self._scaled_idx += 1

    def _convert_color(self, color: Any) -> int:
        """Convert color to platform-appropriate format.
        
        Args:
            color: Color value (int or hex string)
            
        Returns:
            Integer color value
        """
        if isinstance(color, str):
            return int(color, 16)
        return int(color)
    
    async def create_window(self, title: str = "SLDK Display") -> None:
        """Create display window (simulator only).
        
        Args:
            title: Window title
        """
        if IS_CIRCUITPYTHON:
            # No window needed on hardware
            return
            
        try:
            import pygame
            
            if not pygame.get_init():
                pygame.init()
            
            # Create window
            if hasattr(self.matrix, 'surface_width'):
                width = self.matrix.surface_width
                height = self.matrix.surface_height
            else:
                # Default scale of 10x
                width = self._width * 10
                height = self._height * 10
                
            screen = pygame.display.set_mode((width, height))
            pygame.display.set_caption(title)
            
        except ImportError:
            pass  # Pygame not available
    
    async def run_event_loop(self) -> None:
        """Run the display event loop (simulator only).
        
        This keeps the simulator window responsive.
        Should be run as a background task.
        """
        if IS_CIRCUITPYTHON:
            return
            
        while True:
            result = await self.show()
            if not result:
                break
            await asyncio.sleep(0.01)  # ~100 FPS max