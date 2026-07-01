# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Simulator display implementation for SLDK.

Provides display interface using the LED simulator for desktop development.
"""

from __future__ import annotations

import sys
try:
    from typing import Any, Optional
except ImportError:  # CircuitPython has no 'typing' module
    pass

# Verify we're NOT on CircuitPython
if hasattr(sys, 'implementation') and sys.implementation.name == 'circuitpython':
    raise ImportError("Simulator display cannot be used on CircuitPython")

try:
    import asyncio
except ImportError:
    raise ImportError("Simulator requires asyncio")

# The simulator device itself is built inside _sim_backend.create_sim_device;
# these imports probe the simulator rendering stack and provide the Label/font
# used directly by this module.
try:
    from scrollkit.simulator import displayio
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
from .boards import resolve_board


class SimulatorDisplay(GraphicsMixin, DisplayInterface):
    """Simulator display implementation for desktop development."""

    def __init__(self, width: int = 64, height: int = 32, scale: int = 10,
                 *, hardware_timing: bool = False, throttle: bool = False,
                 strict: bool = False, board=None, pitch: float = 3.0):
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
            board: Which board's performance profile to model for hardware
                timing/feasibility (e.g. ``"pimoroni_interstate75_w"``). ``None``
                honors ``SCROLLKIT_HW_BOARD`` and defaults to the MatrixPortal S3.
                The simulated panel geometry is board-agnostic; only the modeled
                timing differs by board.
        """
        self._board_id: str = resolve_board(board).board_id
        self._width: int = width
        self._height: int = height
        self._scale: int = scale
        # LED pitch (mm) -> on-screen LED size. Raise it (e.g. 6.0) to render the
        # panel at a higher resolution for crisp recordings/screenshots; it changes
        # only the visual scale, not the logical 64x32 pixel grid.
        self._pitch: float = pitch
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

        # GIF recording (desktop-only, opt-in). None = off; a list = capturing.
        # Each entry is one shown frame as an (H, W, 3) uint8 array of the LED
        # panel surface. The sibling of screenshot(): one PNG vs many frames.
        self._recording: Optional[list] = None

        # Foreground pixels from set_pixel(), applied after each refresh.
        self._overlay_pixels: dict = {}

        # Reusable Label pool (indexed by draw order within a frame), mirroring
        # UnifiedDisplay/hardware: draw_text() reuses the pooled Label object so
        # unchanged text skips the (expensive) glyph-bitmap rebuild and nothing
        # is allocated per frame. This keeps the hardware feasibility estimate
        # honest — it only charges a text rebuild when .text actually changes.
        self._label_pool: list = []
        self._label_idx: int = 0
        # Parallel pool for integer-scaled labels (draw_text_scaled), mirroring
        # UnifiedDisplay. Kept separate from _label_pool so a scaled and an
        # unscaled draw in the same frame never thrash one Label's .scale.
        self._scaled_pool: list = []
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
        """Initialize the display simulator."""
        if self._initialized:
            return
            
        try:
            # Build + initialize the simulator device (and its hardware-timing
            # model, opt-in via the constructor flags or SCROLLKIT_HW_* env vars)
            # through the backend helper shared with UnifiedDisplay.
            from ._sim_backend import create_sim_device
            self.device, self.matrix, self.display, self._perf = create_sim_device(
                self._width, self._height, self._board_id, pitch=self._pitch,
                hardware_timing=self._hardware_timing, throttle=self._throttle,
                strict=self._strict)

            # Set up display groups (content below, layers above) + cache gfx.
            self.main_group = displayio.Group()
            self.display.root_group = self.main_group
            from scrollkit.simulator import bitmaptools as _bitmaptools
            self._init_graphics(displayio, _bitmaptools)

            # Set initial brightness
            await self.set_brightness(self._brightness)

            self._initialized = True
            print("Simulator display initialized")

        except (ImportError, OSError) as e:
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
        self._scaled_idx = 0

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

            # If recording (opt-in), grab this finished frame for save_gif().
            # Done after the overlay re-render so set_pixel() pixels are included.
            if self._recording is not None:
                self._capture_recording_frame()

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

    # ------------------------------------------------------------------
    # GIF recording — the sibling of screenshot(): one PNG vs an animation.
    # Desktop-only and opt-in; off by default so a normal run pays nothing.
    # ------------------------------------------------------------------

    # Soft cap: warn once past this many captured frames (~25s at 20 FPS) so a
    # recording left on by accident doesn't silently eat memory.
    _RECORDING_WARN_FRAMES = 500

    def start_recording(self):
        """Begin capturing each shown frame for a later :meth:`save_gif`.

        After this, every :meth:`show` appends the current LED-panel frame. Call
        :meth:`save_gif` to encode them or :meth:`stop_recording` to discard.
        Returns ``self`` so the call can be chained.
        """
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
        try:
            import pygame
        except ImportError:
            return
        surface = (self.matrix.get_surface()
                   if self.matrix is not None and hasattr(self.matrix, "get_surface")
                   else None)
        if surface is None:
            return
        # array3d gives (W, H, 3); transpose to image orientation (H, W, 3).
        frame = pygame.surfarray.array3d(surface).transpose(1, 0, 2).copy()
        self._recording.append(frame)
        if len(self._recording) == self._RECORDING_WARN_FRAMES:
            print("SimulatorDisplay: recording is %d frames and growing; call "
                  "save_gif()/stop_recording() to release memory."
                  % self._RECORDING_WARN_FRAMES)

    def save_gif(self, path, *, fps: int = 20, target_width: int = 360,
                 max_colors: int = 48, loop: int = 0, frame_step: int = 1,
                 disposal: int = 1):
        """Encode the recorded frames to an animated GIF and clear the buffer.

        Renders the frames captured since :meth:`start_recording` into an
        animated GIF at ``path``. Frames are downscaled to ``target_width`` and
        share **one** adaptive palette (≤ ``max_colors``) so colors stay stable
        across the loop and the file stays small. ``frame_step`` keeps only every
        Nth frame (smaller file; the per-frame duration is lengthened to keep
        playback speed correct). ``loop=0`` loops forever. ``disposal=1`` keeps
        the file small by letting Pillow store only each frame's changed region.

        Returns the path on success, or None when there is nothing to save or
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
        if not frames:
            return None
        try:
            from PIL import Image
        except ImportError:
            print("save_gif failed: Pillow not installed (pip install Pillow)")
            return None

        kept = frames[::max(1, int(frame_step))]
        rgb = []
        for arr in kept:
            img = Image.fromarray(arr, "RGB")
            if target_width and img.width != target_width:
                h = max(1, round(img.height * target_width / img.width))
                img = img.resize((target_width, h), Image.LANCZOS)
            rgb.append(img)

        # One shared palette from a handful of evenly-sampled frames: stable
        # colors across the loop (no per-frame flicker) and a much smaller file.
        sample = rgb[::max(1, len(rgb) // 16)]
        montage = Image.new("RGB", (rgb[0].width, rgb[0].height * len(sample)))
        for i, frame_img in enumerate(sample):
            montage.paste(frame_img, (0, i * rgb[0].height))
        palette = montage.quantize(colors=max_colors, method=Image.MEDIANCUT)
        paletted = [im.quantize(palette=palette) for im in rgb]

        duration = int(round(1000.0 / fps)) * max(1, int(frame_step))
        try:
            # disposal=1 ("do not dispose") leaves the prior frame in place so
            # Pillow can crop each frame to just its changed region — the static
            # LED-panel background is written once, shrinking the file several-fold
            # versus disposal=2 (which restores to background and forces full frames).
            paletted[0].save(path, save_all=True, append_images=paletted[1:],
                             duration=duration, loop=loop, optimize=True,
                             disposal=disposal)
            return path
        except (OSError, ValueError) as e:
            print(f"save_gif failed: {e}")
            return None

    def save_video(self, path, *, fps: int = 24, target_width=None,
                   crf: int = 20, preset: str = "medium",
                   border: int = 0, border_color=(10, 10, 13)):
        """Encode the recorded frames to an MP4 (H.264) via ffmpeg; clear the buffer.

        The web-friendly sibling of :meth:`save_gif`: for full-colour animation an
        MP4 is far smaller and smoother than a GIF (no 256-colour palette, real
        inter-frame compression), so it's the right format for a site hero. The raw
        recorded frames are piped straight to ``ffmpeg`` (which must be on PATH).

        ``target_width`` optionally downscales (kept even, as ``yuv420p`` requires);
        ``None`` keeps native size. ``crf`` trades size for quality (≈18 best … 24
        smaller; 20 is a good default). ``preset`` is libx264's speed/efficiency
        knob. ``-movflags +faststart`` makes the file stream-ready on the web.
        ``border`` adds a dark bezel of that many pixels on every side (the panel
        surface is flush to the LEDs, so a bezel keeps edge rows off the frame
        boundary — like a real sign's frame); ``border_color`` is its RGB.

        Returns the path, or None when there are no frames or ffmpeg/encode is
        unavailable (mirroring :meth:`save_gif`). Recording is stopped either way.

        Example::

            display.start_recording()
            for _ in range(120):
                await content.render(display)
                await display.show()
            display.save_video("hero.mp4")
        """
        import shutil
        import subprocess

        frames = self._recording or []
        self._recording = None
        if not frames:
            return None
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            print("save_video failed: ffmpeg not found (e.g. `brew install ffmpeg`)")
            return None

        h0, w0 = int(frames[0].shape[0]), int(frames[0].shape[1])
        if target_width and int(target_width) != w0:
            out_w = int(target_width)
            out_h = max(1, round(h0 * out_w / w0))
        else:
            out_w, out_h = w0, h0
        out_w -= out_w % 2          # yuv420p needs even dimensions
        out_h -= out_h % 2
        if out_w < 2 or out_h < 2:
            return None
        resize = (out_w, out_h) != (w0, h0)
        if resize:
            try:
                from PIL import Image
            except ImportError:
                print("save_video failed: Pillow needed to resize (pip install Pillow)")
                return None

        vf = []
        if border and int(border) > 0:
            b = int(border) - int(border) % 2   # keep padded dims even for yuv420p
            if b > 0:
                bc = border_color
                vf = ["-vf", "pad=iw+%d:ih+%d:%d:%d:color=0x%02X%02X%02X"
                      % (2 * b, 2 * b, b, b, int(bc[0]), int(bc[1]), int(bc[2]))]

        cmd = ([ffmpeg, "-y", "-loglevel", "error",
                "-f", "rawvideo", "-pix_fmt", "rgb24",
                "-s", "%dx%d" % (out_w, out_h), "-r", str(int(fps)), "-i", "-",
                "-an"] + vf
               + ["-c:v", "libx264", "-pix_fmt", "yuv420p",
                  "-crf", str(int(crf)), "-preset", str(preset),
                  "-movflags", "+faststart", path])
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        except OSError as e:
            print("save_video failed: could not launch ffmpeg (%r)" % (e,))
            return None
        try:
            for arr in frames:
                if resize:
                    arr_bytes = Image.fromarray(arr, "RGB").resize(
                        (out_w, out_h), Image.LANCZOS).tobytes()
                else:
                    arr_bytes = arr.tobytes()
                proc.stdin.write(arr_bytes)
            proc.stdin.close()
            rc = proc.wait()
        except (OSError, ValueError) as e:
            print("save_video failed: %r" % (e,))
            return None
        if rc != 0:
            print("save_video failed: ffmpeg exited %s" % rc)
            return None
        return path

    def feasibility_report(self):
        """Estimate how this app would perform on the real hardware.

        Returns a FeasibilityReport (estimated FPS, per-frame cost breakdown,
        peak RAM vs budget, warnings). Requires hardware_timing=True (or
        SCROLLKIT_HW_SIM=1); otherwise returns a clearly-labeled disabled stub.
        """
        if self._perf is None:
            from ._sim_backend import disabled_feasibility_report
            return disabled_feasibility_report(
                "enable with SimulatorDisplay(hardware_timing=True) or SCROLLKIT_HW_SIM=1")
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

    async def draw_text_scaled(self, text: str, x: int = 0, y: int = 0,
                               color: int = 0xFFFFFF, scale: int = 2,
                               font: Any = None) -> None:
        """Draw integer-scaled text, reusing a pooled scaled Label.

        Simulator mirror of :meth:`UnifiedDisplay.draw_text_scaled` — same scaled
        pool discipline, re-appended to the content group each frame (which
        clear() empties), so nothing is allocated per frame after warm-up.
        """
        if font is None:
            font = self.font
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
        else:
            label = Label(font, text=text, color=color, scale=scale)
            label.x = x
            label.y = y
            self._scaled_pool.append(label)
        self._content_group.append(label)
        self._scaled_idx += 1

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