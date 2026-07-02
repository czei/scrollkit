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
    # SLDK Simulator imports - these will be optional. The simulator device itself
    # is built inside _sim_backend.create_sim_device; here we just probe that the
    # simulator rendering stack (displayio/Label/terminalio) is importable.
    try:
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


__all__ = ['UnifiedDisplay', 'IS_CIRCUITPYTHON']

class UnifiedDisplay(GraphicsMixin, DisplayInterface):
    """Unified display that auto-detects hardware vs simulator."""

    # Window title for create_window(); SimulatorDisplay overrides.
    _WINDOW_TITLE = "SLDK Display"
    # Whether show() creates the pygame window automatically on desktop.
    # False here (UnifiedDisplay stays headless unless create_window() is
    # called); SimulatorDisplay — the interactive/dev display — sets True.
    _AUTO_WINDOW = False
    # Soft cap: warn once past this many recorded frames (~25s at 20 FPS) so a
    # recording left on by accident doesn't silently eat memory.
    _RECORDING_WARN_FRAMES = 500

    def __init__(self, width=None, height=None, bit_depth: int = 4, board=None,
                 *, hardware_timing: bool = False, throttle: bool = False,
                 strict: bool = False, pitch=None):
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
            hardware_timing: (desktop only) model how slow the real device would
                run — read the estimate via feasibility_report(). Ignored on
                hardware (the device IS the timing). Also enabled by
                SCROLLKIT_HW_SIM=1.
            throttle: (desktop only) with hardware_timing, also sleep so the
                window crawls at the modeled hardware speed. Also
                SCROLLKIT_HW_THROTTLE=1.
            strict: (desktop only) enforce the feasibility gate — a sustained
                over-budget run raises FeasibilityError. Implies
                hardware_timing. Also SCROLLKIT_HW_STRICT=1.
            pitch: (desktop only) LED pitch (mm) -> on-screen LED size for
                recordings/screenshots. ``None`` uses the simulator default.
        """
        spec = resolve_board(board)
        self._board_id: str = spec.board_id
        self._board_spec = spec
        self._width: int = spec.default_width if width is None else width
        self._height: int = spec.default_height if height is None else height
        self._bit_depth: int = bit_depth
        # Hardware-realism simulation (desktop opt-in; env vars honored too).
        self._hardware_timing: bool = hardware_timing
        self._throttle: bool = throttle
        self._strict: bool = strict
        self._pitch = pitch
        # Brightness default is per-platform ON PURPOSE: hardware boots dim
        # (0.3 — a full-white 64x32 panel at 1.0 is a real power/eye hazard);
        # desktop boots at 1.0 so content is clearly visible in the simulator
        # (both desktop entry points agree; the LED renderer also applies its
        # high-visibility enhancement at 1.0). Apps that manage brightness get
        # the settings default (0.5) applied via _apply_library_settings.
        self._brightness: float = 0.3 if IS_CIRCUITPYTHON else 1.0

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

        # Desktop extras (no-ops on hardware): pygame window + frame recording.
        # None = not recording; a list = capturing (H, W, 3) uint8 frames.
        self._window_created: bool = False
        self._recording = None

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
            
        except (ImportError, OSError) as e:
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
                    'Install with: pip install "scrollkit[simulator]"'
                )

            # Build + initialize the simulator device (and its hardware-timing
            # model, opt-in via the constructor flags or SCROLLKIT_HW_* env
            # vars) through the shared backend helper.
            from ._sim_backend import create_sim_device
            self.device, self.matrix, self.display, self._perf = create_sim_device(
                self._width, self._height, self._board_id, pitch=self._pitch,
                hardware_timing=self._hardware_timing, throttle=self._throttle,
                strict=self._strict)
            self.hardware = self.device  # For compatibility

    def feasibility_report(self):
        """Estimate how this app would perform on the real hardware.

        Mirrors SimulatorDisplay.feasibility_report(); returns a disabled stub
        unless hardware timing was enabled (via the SCROLLKIT_HW_* env vars).
        """
        if self._perf is None:
            from ._sim_backend import disabled_feasibility_report
            return disabled_feasibility_report(
                "enable with hardware_timing=True or SCROLLKIT_HW_SIM=1")
        return self._perf.report()

    # clear() / set_pixel() / fill() / _hide_unused_labels() come from
    # GraphicsMixin — ONE per-frame surface for hardware and simulator.

    async def show(self) -> bool:
        """Update the physical display."""
        self._hide_unused_labels()
        if IS_CIRCUITPYTHON:
            # self.display is the displayio display on every board (the S3's
            # Matrix wrapper display or the Interstate 75's FramebufferDisplay).
            # self.hardware may be a raw rgbmatrix.RGBMatrix with no .display.
            if self.display:
                self.display.refresh(minimum_frames_per_second=0)
            return True
        else:
            # Simulator needs pygame event handling
            return await self._update_simulator()
    
    async def _update_simulator(self) -> bool:
        """Update the simulator display (the ONE desktop frame path)."""
        if not self.display:
            return True

        try:
            import pygame

            # The interactive display (SimulatorDisplay) opens its window on
            # first show; UnifiedDisplay stays headless unless asked.
            if self._AUTO_WINDOW and not self._window_created:
                await self.create_window()

            has_window = pygame.get_init() and pygame.display.get_surface()

            # Handle events to keep the window responsive.
            if has_window:
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

            # If recording (opt-in), grab this finished frame for save_gif().
            if self._recording is not None:
                self._capture_recording_frame()

            if has_window:
                # Blit the rendered LED matrix surface to the pygame window.
                screen = pygame.display.get_surface()
                if screen and hasattr(self.matrix, 'get_surface'):
                    matrix_surface = self.matrix.get_surface()
                    if matrix_surface:
                        screen.fill((0, 0, 0))
                        screen.blit(matrix_surface, (0, 0))
                pygame.display.flip()

            # Small yield for responsiveness
            await asyncio.sleep(0.001)

        except ImportError:
            # Pygame not available
            if self.display:
                self.display.refresh(minimum_frames_per_second=0)

        return True

    # ------------------------------------------------------------------
    # Screenshot + recording (desktop-only, opt-in; None/no-op on hardware).
    # The heavy pygame/Pillow/ffmpeg work lives in display/_recording.py and
    # is imported lazily so the device never pays for it.
    # ------------------------------------------------------------------

    def screenshot(self, path):
        """Save the current display frame to an image file (PNG by extension).

        Renders whatever is currently on the simulated matrix to ``path``.
        Returns the path on success or None if unavailable (e.g. on hardware).

        Example::

            await display.show()
            display.screenshot("frame.png")
        """
        if IS_CIRCUITPYTHON:
            return None
        from ._recording import save_surface_png
        return save_surface_png(self.matrix, path)

    def start_recording(self):
        """Begin capturing each shown frame for a later :meth:`save_gif`.

        After this, every :meth:`show` appends the current LED-panel frame. Call
        :meth:`save_gif`/:meth:`save_video` to encode them or
        :meth:`stop_recording` to discard. No-op (returns None) on hardware.
        Returns ``self`` so the call can be chained.
        """
        if IS_CIRCUITPYTHON:
            return None
        self._recording = []
        return self

    def stop_recording(self) -> None:
        """Stop capturing frames and discard anything not yet saved."""
        self._recording = None

    @property
    def is_recording(self) -> bool:
        """True while frames are being captured for :meth:`save_gif`."""
        return self._recording is not None

    def _capture_recording_frame(self) -> None:
        """Append the current LED-panel surface to the recording (internal)."""
        from ._recording import capture_frame
        frame = capture_frame(self.matrix)
        if frame is None:
            return
        self._recording.append(frame)
        if len(self._recording) == self._RECORDING_WARN_FRAMES:
            print("display: recording is %d frames and growing; call "
                  "save_gif()/stop_recording() to release memory."
                  % self._RECORDING_WARN_FRAMES)

    def save_gif(self, path, *, fps: int = 20, target_width: int = 360,
                 max_colors: int = 48, loop: int = 0, frame_step: int = 1,
                 disposal: int = 1):
        """Encode the recorded frames to an animated GIF and clear the buffer.

        Frames captured since :meth:`start_recording` are downscaled to
        ``target_width`` and share ONE adaptive palette (≤ ``max_colors``) so
        colors stay stable across the loop and the file stays small.
        ``frame_step`` keeps only every Nth frame (per-frame duration is
        lengthened to keep playback speed correct); ``loop=0`` loops forever.

        Returns the path, or None when there is nothing to save or
        pygame/Pillow isn't available (e.g. on hardware) — mirroring
        :meth:`screenshot`. Recording is stopped afterward either way.

        Example::

            display.start_recording()
            for _ in range(60):
                await content.render(display)
                await display.show()
            display.save_gif("demo.gif")
        """
        frames = self._recording or []
        self._recording = None
        if not frames or IS_CIRCUITPYTHON:
            return None
        from ._recording import encode_gif
        return encode_gif(frames, path, fps=fps, target_width=target_width,
                          max_colors=max_colors, loop=loop,
                          frame_step=frame_step, disposal=disposal)

    def save_video(self, path, *, fps: int = 24, target_width=None,
                   crf: int = 20, preset: str = "medium",
                   border: int = 0, border_color=(10, 10, 13)):
        """Encode the recorded frames to an MP4 (H.264) via ffmpeg; clear buffer.

        The web-friendly sibling of :meth:`save_gif`: for full-colour animation
        an MP4 is far smaller and smoother than a GIF. Frames are piped straight
        to ``ffmpeg`` (which must be on PATH). ``target_width`` optionally
        downscales (kept even, as yuv420p requires); ``crf`` trades size for
        quality (≈18 best … 24 smaller); ``border`` adds a dark bezel of that
        many pixels (``border_color`` RGB) so edge rows aren't flush with the
        frame boundary.

        Returns the path, or None when there are no frames or ffmpeg/encode is
        unavailable (mirroring :meth:`save_gif`). Recording stops either way.
        """
        frames = self._recording or []
        self._recording = None
        if not frames or IS_CIRCUITPYTHON:
            return None
        from ._recording import encode_video
        return encode_video(frames, path, fps=fps, target_width=target_width,
                            crf=crf, preset=preset, border=border,
                            border_color=border_color)

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
    
    async def create_window(self, title: str = None) -> None:
        """Create the pygame display window (desktop only; no-op on hardware).

        Args:
            title: Window title (default: the class's _WINDOW_TITLE)
        """
        if IS_CIRCUITPYTHON or self._window_created:
            return

        try:
            import os as _os
            import pygame

            # Ask SDL for a visible, sanely-placed window.
            _os.environ['SDL_VIDEO_WINDOW_POS'] = '100,100'
            _os.environ['SDL_VIDEO_CENTERED'] = '1'

            if not pygame.get_init():
                pygame.init()

            if hasattr(self.matrix, 'surface_width'):
                width = self.matrix.surface_width
                height = self.matrix.surface_height
            else:
                scale = getattr(self, "_scale", 10)
                width = self._width * scale
                height = self._height * scale

            screen = pygame.display.set_mode((width, height), pygame.SHOWN)
            pygame.display.set_caption(title or self._WINDOW_TITLE)
            screen.fill((50, 50, 50))
            pygame.display.flip()
            self._window_created = True

        except ImportError:
            print("Pygame not available for window creation")
    
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