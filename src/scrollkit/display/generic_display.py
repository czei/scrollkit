"""
Generic LED matrix display for ScrollKit.
Works on both CircuitPython hardware and SLDK simulator development environment.
Copyright 2024 3DUPFitters LLC
"""
import asyncio
import time
import sys

# Platform detection
IS_CIRCUITPYTHON = hasattr(sys, 'implementation') and sys.implementation.name == 'circuitpython'

# Conditional imports based on platform
if IS_CIRCUITPYTHON:
    import displayio
    import terminalio
    from adafruit_bitmap_font import bitmap_font
    from adafruit_display_text.label import Label
else:
    # SLDK Simulator imports
    import os
    sldk_path = os.path.join(os.path.dirname(__file__), '..', '..', 'sldk', 'src')
    if os.path.exists(sldk_path) and sldk_path not in sys.path:
        sys.path.insert(0, sldk_path)

    print(f"[GenericDisplay] Loading SLDK from {sldk_path}")

    from sldk.simulator.devices.matrixportal_s3 import MatrixPortalS3
    from sldk.simulator import displayio
    from sldk.simulator.adafruit_bitmap_font import bitmap_font
    from sldk.simulator.adafruit_display_text.label import Label

    print("[GenericDisplay] SLDK imports successful")

    # SLDK doesn't have terminalio.FONT, so load a default font
    default_font_path = os.path.join(sldk_path, 'sldk', 'simulator', 'fonts', 'viii.bdf')
    default_font = None
    if os.path.exists(default_font_path):
        print(f"[GenericDisplay] Loading default font from {default_font_path}")
        default_font = bitmap_font.load_font(default_font_path)
    else:
        print(f"[GenericDisplay] Default font not found at {default_font_path}")

    # Create a mock terminalio module for compatibility
    class MockTerminalio:
        def __init__(self):
            self.FONT = default_font

    terminalio = MockTerminalio()
    print(f"[GenericDisplay] Mock terminalio created with font: {terminalio.FONT}")

from scrollkit.display.display_interface import DisplayInterface
from scrollkit.utils.color_utils import ColorUtils
from scrollkit.utils.error_handler import ErrorHandler

# Initialize logger
logger = ErrorHandler("error_log")


class GenericDisplay(DisplayInterface):
    """
    Generic LED matrix display implementation that works on both CircuitPython
    hardware and the SLDK desktop simulator.

    Provides basic display primitives (scrolling text, static text, images,
    brightness, rotation) without any application-specific content.
    Applications should extend this class to add domain-specific display logic.
    """

    def __init__(self, config=None):
        """
        Initialize the generic display

        Args:
            config: Optional configuration dictionary. May contain:
                - 'settings_manager': SettingsManager instance
                - 'font_path': Path to a custom font file (simulator only)
        """
        self.hardware = None
        self.matrix = None
        self.display = None
        self.device = None
        self.font = None
        self.settings_manager = config.get('settings_manager') if config else None
        self.custom_font_path = config.get('font_path') if config else None

        # For scrolling
        self.scroll_position = 0
        self.scroll_delay = 0.04

        # Main display group (all content goes here)
        self.main_group = None

        # Built-in scrolling label and group
        self.scrolling_label = None
        self.scrolling_group = None

        # Registry of application-created groups for clearing
        self._app_groups = []

    def initialize(self):
        """Initialize the display hardware or simulator"""
        try:
            platform_name = 'CircuitPython' if IS_CIRCUITPYTHON else 'SLDK Simulator'
            logger.info(f"Initializing GenericDisplay ({platform_name})")

            self._initialize_hardware()

            # Font loading
            if IS_CIRCUITPYTHON:
                self.font = terminalio.FONT
            else:
                self._load_simulator_font()

            # Create main display group
            self.main_group = displayio.Group()
            self.display.root_group = self.main_group
            if IS_CIRCUITPYTHON:
                self.main_group.hidden = False

            # Set up built-in scrolling label
            self.scrolling_label = Label(self.font)
            self.scrolling_label.x = 0
            self.scrolling_label.y = 15
            self.scrolling_group = displayio.Group()
            self.scrolling_group.append(self.scrolling_label)
            self.scrolling_group.hidden = True
            self.main_group.append(self.scrolling_group)

            # Platform-specific post-init
            if not IS_CIRCUITPYTHON and hasattr(self.matrix, 'initialize_surface'):
                self.matrix.initialize_surface()

            logger.info("GenericDisplay initialized successfully")
            return True

        except Exception as e:
            logger.error(e, "Failed to initialize GenericDisplay")
            return False

    def _initialize_hardware(self):
        """Initialize the display hardware or simulator"""
        if IS_CIRCUITPYTHON:
            from adafruit_matrixportal.matrix import Matrix
            self.hardware = Matrix()
            self.display = self.hardware.display
            self.matrix = self.hardware
        else:
            self.device = MatrixPortalS3(width=64, height=32)
            self.device.initialize()
            self.matrix = self.device.matrix
            self.display = self.device.display
            self.hardware = self.device

    def _load_simulator_font(self):
        """Load font for SLDK simulator, trying multiple paths"""
        if hasattr(terminalio, 'FONT') and terminalio.FONT:
            self.font = terminalio.FONT
            return

        search_paths = []
        if self.custom_font_path:
            search_paths.append(self.custom_font_path)

        # Try local fonts dir
        import os as _os
        base = _os.path.dirname(__file__)
        search_paths.extend([
            _os.path.join(base, '..', 'fonts', 'tom-thumb.bdf'),
            _os.path.join(base, '..', '..', 'sldk', 'src', 'sldk', 'simulator', 'fonts', 'tom-thumb.bdf'),
            _os.path.join(base, '..', '..', 'sldk', 'src', 'sldk', 'simulator', 'fonts', 'viii.bdf'),
        ])

        for path in search_paths:
            if _os.path.exists(path):
                self.font = bitmap_font.load_font(path)
                return

        logger.error(None, "No suitable font found for SLDK simulator")
        self.font = None

    # ------------------------------------------------------------------
    # Label and Group creation (for applications to build custom layouts)
    # ------------------------------------------------------------------

    def create_label(self, text="", x=0, y=0, scale=1, color=None):
        """
        Create a Label object positioned at (x, y).

        Args:
            text: Initial text content
            x: Horizontal position
            y: Vertical position
            scale: Text scale factor
            color: Color as hex string or integer

        Returns:
            A displayio-compatible Label object
        """
        label = Label(self.font, text=text)
        label.x = x
        label.y = y
        label.scale = scale
        if color is not None:
            label.color = self._convert_color(color)
        return label

    def create_group(self, *labels):
        """
        Create a displayio Group containing the given labels.

        Args:
            *labels: Label objects to add to the group

        Returns:
            A displayio.Group
        """
        group = displayio.Group()
        group.hidden = True
        for label in labels:
            group.append(label)
        return group

    def add_to_main_group(self, group):
        """
        Add an application-created group to the main display.

        Args:
            group: A displayio.Group to add
        """
        self.main_group.append(group)
        self._app_groups.append(group)

    # ------------------------------------------------------------------
    # Display primitives
    # ------------------------------------------------------------------

    def show_scroll_message(self, message, color=None):
        """
        Scroll a message across the display once, then hide it.
        This is a coroutine -- must be awaited.

        Args:
            message: Text to scroll
            color: Optional color
        """
        self._hide_all_groups()
        self.scrolling_label.text = message
        if color is not None:
            self.scrolling_label.color = self._convert_color(color)
        self.scrolling_group.hidden = False

    async def show_scroll_message_async(self, message, color=None):
        """Async version of show_scroll_message with full scroll animation."""
        self.show_scroll_message(message, color)
        await asyncio.sleep(0.5)
        while self._scroll_x(self.scrolling_label):
            await asyncio.sleep(self.scroll_delay)
            self.update()
        self.scrolling_group.hidden = True

    async def show_static_text(self, text, x=0, y=0, scale=1, color=None):
        """
        Display static text at a position for a duration.

        Args:
            text: Text to display
            x: Horizontal position
            y: Vertical position
            scale: Text scale factor
            color: Optional color
        """
        label = self.create_label(text, x, y, scale, color)
        group = displayio.Group()
        group.append(label)
        self.main_group.append(group)
        return label, group

    def set_text(self, text, color=None):
        """
        Set text on the built-in scrolling label.

        Args:
            text: Text to display
            color: Optional color
        """
        if not self.scrolling_label:
            return
        self.scrolling_label.text = text
        if color:
            self.scrolling_label.color = self._convert_color(color)
        self.scrolling_group.hidden = False

    def scroll(self, frame_delay=0.04):
        """Set the scroll frame delay."""
        self.scroll_delay = frame_delay

    def clear(self):
        """Hide all display groups."""
        self._hide_all_groups()

    def update(self):
        """Refresh the display. Returns False if window should close (simulator)."""
        if IS_CIRCUITPYTHON:
            if self.hardware:
                self.hardware.display.refresh(minimum_frames_per_second=0)
            return True
        else:
            return self._update_simulator()

    def _update_simulator(self):
        """Handle pygame events and refresh for the SLDK simulator."""
        if not self.display:
            return True

        import pygame
        if not pygame.get_init():
            self.display.refresh(minimum_frames_per_second=0)
            return True
        if pygame.display.get_surface() is None:
            self.display.refresh(minimum_frames_per_second=0)
            return True

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False

        self.display.refresh(minimum_frames_per_second=0)
        if hasattr(self.matrix, 'render'):
            self.matrix.render()
        pygame.display.flip()
        return True

    async def run_async(self):
        """Run the display in an async loop (simulator only). Exits app on window close."""
        if IS_CIRCUITPYTHON:
            return

        import pygame
        if not pygame.get_init():
            pygame.init()

        screen = pygame.display.set_mode(
            (self.matrix.surface_width, self.matrix.surface_height)
        )
        pygame.display.set_caption("ScrollKit - Generic Display")

        clock = pygame.time.Clock()
        running = True

        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    import sys as _sys
                    pygame.quit()
                    _sys.exit(0)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                        import sys as _sys
                        pygame.quit()
                        _sys.exit(0)

            if self.display and self.display.root_group:
                self.display.refresh(minimum_frames_per_second=0)

            if hasattr(self.matrix, 'render'):
                self.matrix.render()
                if hasattr(self.matrix, 'surface'):
                    screen.blit(self.matrix.surface, (0, 0))

            pygame.display.flip()
            clock.tick(60)
            await asyncio.sleep(0.001)

        pygame.quit()

    def show_image(self, image, x=0, y=0):
        """Display a PIL Image at the given position."""
        try:
            if IS_CIRCUITPYTHON:
                self._show_image_circuitpython(image, x, y)
            else:
                self._show_image_simulator(image, x, y)
        except Exception as e:
            logger.error(e, "Error displaying image")

    def _show_image_circuitpython(self, image, x, y):
        if not (hasattr(image, 'mode') and image.mode):
            return
        from adafruit_imaging.bitmap import displayio_bitmap_from_pil_image
        bitmap = displayio_bitmap_from_pil_image(image)
        tile_grid = displayio.TileGrid(bitmap, pixel_shader=displayio.ColorConverter())
        image_group = displayio.Group()
        image_group.append(tile_grid)
        image_group.x = x
        image_group.y = y
        self._hide_all_groups()
        self.main_group.append(image_group)
        self.update()

    def _show_image_simulator(self, image, x, y):
        if not (hasattr(image, 'mode') and image.mode):
            return
        bitmap = displayio.Bitmap(image.width, image.height, 256)
        palette = displayio.Palette(256)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        for y_pos in range(image.height):
            for x_pos in range(image.width):
                pixel = image.getpixel((x_pos, y_pos))
                color = (pixel[0] << 16) | (pixel[1] << 8) | pixel[2]
                for i in range(len(palette)):
                    if palette[i] == color:
                        color_index = i
                        break
                else:
                    if len(palette) < 256:
                        palette[len(palette)] = color
                        color_index = len(palette) - 1
                    else:
                        color_index = 0
                bitmap[x_pos, y_pos] = color_index
        tile_grid = displayio.TileGrid(bitmap, pixel_shader=palette)
        image_group = displayio.Group()
        image_group.append(tile_grid)
        image_group.x = x
        image_group.y = y
        self._hide_all_groups()
        self.main_group.append(image_group)
        self.update()

    def set_brightness(self, brightness):
        """Set display brightness (0.0 to 1.0)."""
        if not self.display:
            return
        try:
            brightness = min(max(brightness, 0.0), 1.0)
            if IS_CIRCUITPYTHON:
                self.hardware.display.brightness = brightness
            else:
                self.display.brightness = brightness
        except Exception as e:
            logger.error(e, "Failed to set brightness")

    def set_rotation(self, rotation):
        """Set display rotation (0, 90, 180, or 270 degrees)."""
        if not self.display:
            return
        try:
            rotation_map = {0: 0, 90: 1, 180: 2, 270: 3}
            if rotation in rotation_map:
                self.display.rotation = rotation_map[rotation]
        except Exception as e:
            logger.error(e, "Failed to set rotation")

    # ------------------------------------------------------------------
    # Internal utilities
    # ------------------------------------------------------------------

    def _convert_color(self, color):
        """Convert color to platform-appropriate integer."""
        if IS_CIRCUITPYTHON:
            return int(color)
        if isinstance(color, str):
            return int(color, 16)
        return int(color)

    def _hide_all_groups(self):
        """Hide all groups, including app-created ones."""
        self.scrolling_group.hidden = True if self.scrolling_group else None
        for group in self._app_groups:
            if group:
                group.hidden = True

    def _scroll_x(self, label):
        """
        Scroll a label horizontally by 1 pixel. Returns True if still scrolling.
        """
        label.x = label.x - 1
        label_width = label.bounding_box[2]
        display_width = (
            self.hardware.display.width if IS_CIRCUITPYTHON
            else self.display.width
        )
        if label.x < -label_width:
            label.x = display_width
            return False
        return True

    def _center_text(self, label):
        """Center a label horizontally on the display."""
        width = (
            self.hardware.display.width if IS_CIRCUITPYTHON
            else self.display.width
        )
        bounding_box = label.bounding_box
        if bounding_box:
            label_width = bounding_box[2] * label.scale
            padding = int((width - label_width) / 2)
            label.x = max(0, padding)

    @property
    def display_width(self):
        """Get the display width in pixels."""
        if IS_CIRCUITPYTHON and self.hardware:
            return self.hardware.display.width
        elif self.display:
            return self.display.width
        return 64

    @property
    def display_height(self):
        """Get the display height in pixels."""
        if IS_CIRCUITPYTHON and self.hardware:
            return self.hardware.display.height
        elif self.display:
            return self.display.height
        return 32
