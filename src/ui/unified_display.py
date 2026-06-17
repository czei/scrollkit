"""
Unified display implementation for Theme Park Waits.
Works on both CircuitPython hardware and LED Simulator development environment.
Now extends GenericDisplay from the ScrollKit Library instead of duplicating hardware logic.
Copyright 2024 3DUPFitters LLC
"""
import asyncio
import os
import sys

from scrollkit.display.generic_display import GenericDisplay, IS_CIRCUITPYTHON
from scrollkit.utils.color_utils import ColorUtils
from scrollkit.utils.error_handler import ErrorHandler

# Platform-appropriate imports for display primitives
if IS_CIRCUITPYTHON:
    import displayio
    from adafruit_display_text.label import Label
else:
    sldk_path = os.path.join(os.path.dirname(__file__), '..', '..', 'sldk', 'src')
    if os.path.exists(sldk_path) and sldk_path not in sys.path:
        sys.path.insert(0, sldk_path)
    from sldk.simulator import displayio
    from sldk.simulator.adafruit_display_text.label import Label

from src.ui.reveal_animation import show_reveal_splash

# Initialize logger
logger = ErrorHandler("error_log")

# Unified positioning configuration
PLATFORM_CONFIG = {
    'scrolling_y': 15,
    'wait_name_y': 7,
    'wait_time_y': 22,
    'closed_y': 22,
    'splash_line1_y': 7,
    'splash_line2_y': 22,
    'update_line1_y': 10,
    'update_line2_y': 22,
    'required_line1_y': 12,
    'required_line2_y': 20,
    'centered_line1_y': 9,
    'centered_line2_y': 23,
    'queue_line1_y': 10,
    'queue_line2_y': 25,
}


class UnifiedDisplay(GenericDisplay):
    """
    Theme Park Waits display that extends the ScrollKit Library's GenericDisplay
    with application-specific content: ride wait times, splash screens, etc.
    """

    def __init__(self, config=None):
        super().__init__(config)
        self.positions = PLATFORM_CONFIG

        # ThemePark-specific display groups
        self.wait_time_name_group = None
        self.wait_time_group = None
        self.closed_group = None
        self.splash_group = None
        self.update_group = None
        self.required_group = None
        self.centered_group = None
        self.queue_group = None

        # ThemePark-specific labels
        self.wait_time_name = None
        self.wait_time = None
        self.closed = None
        self.splash_line1 = None
        self.splash_line2 = None
        self.update_line1 = None
        self.update_line2 = None
        self.required_line1 = None
        self.required_line2 = None
        self.centered_line1 = None
        self.centered_line2 = None
        self.queue_line1 = None
        self.queue_line2 = None

    def initialize(self):
        """Initialize the display with generic setup + ThemePark-specific groups."""
        if not super().initialize():
            return False

        try:
            self._setup_themepark_groups()
            if self.settings_manager:
                self.set_colors(self.settings_manager)
            return True
        except Exception as e:
            logger.error(e, "Failed to set up ThemePark display groups")
            return False

    def _setup_themepark_groups(self):
        """Create ThemePark-specific display groups and labels."""
        pos = self.positions

        self.wait_time_name = Label(self.font)
        self.wait_time_name.x = 0
        self.wait_time_name.y = pos['wait_name_y']
        self.wait_time_name.scale = 1
        self.wait_time_name_group = displayio.Group()
        self.wait_time_name_group.append(self.wait_time_name)
        self.wait_time_name_group.hidden = True

        self.wait_time = Label(self.font)
        self.wait_time.x = 0
        self.wait_time.y = pos['wait_time_y']
        self.wait_time.scale = 2
        self.wait_time_group = displayio.Group()
        self.wait_time_group.append(self.wait_time)
        self.wait_time_group.hidden = True

        self.closed = Label(self.font)
        self.closed.x = 14
        self.closed.y = pos['closed_y']
        self.closed.scale = 1
        self.closed.text = "Closed"
        self.closed_group = displayio.Group()
        self.closed_group.hidden = True
        self.closed_group.append(self.closed)

        self.splash_line1 = Label(self.font, text="THEME PARK")
        self.splash_line1.x = 2
        self.splash_line1.y = pos['splash_line1_y']
        self.splash_line2 = Label(self.font, text="WAITS", scale=2)
        self.splash_line2.x = 3
        self.splash_line2.y = pos['splash_line2_y']
        self.splash_group = displayio.Group()
        self.splash_group.hidden = True
        self.splash_group.append(self.splash_line1)
        self.splash_group.append(self.splash_line2)
        self.splash_line1.color = self._convert_color(ColorUtils.colors["Yellow"])
        self.splash_line2.color = self._convert_color(ColorUtils.colors["Orange"])

        self.update_line1 = Label(self.font, text="Wait Times")
        self.update_line1.x = 2
        self.update_line1.y = pos['update_line1_y']
        self.update_line2 = Label(self.font, text="Powered By", scale=1)
        self.update_line2.x = 2
        self.update_line2.y = pos['update_line2_y']
        self.update_group = displayio.Group()
        self.update_group.hidden = True
        self.update_group.append(self.update_line1)
        self.update_group.append(self.update_line2)
        self.update_line1.color = self._convert_color(ColorUtils.colors["Yellow"])
        self.update_line2.color = self._convert_color(ColorUtils.colors["Yellow"])

        self.required_line1 = Label(self.font, text="QUEUE-TIMES.COM")
        self.required_line2 = Label(self.font, text="UPDATING NOW")
        self.required_line1.x = 3
        self.required_line1.y = pos['required_line1_y']
        self.required_line2.x = 8
        self.required_line2.y = pos['required_line2_y']
        self.required_group = displayio.Group()
        self.required_group.hidden = True
        self.required_group.append(self.required_line1)
        self.required_group.append(self.required_line2)
        self.required_line1.color = self._convert_color(ColorUtils.colors["Yellow"])
        self.required_line2.color = self._convert_color(ColorUtils.colors["Yellow"])

        self.centered_line1 = Label(self.font, text="Test Line1")
        self.centered_line2 = Label(self.font, text="TEST LINE2")
        self.centered_line1.x = 0
        self.centered_line1.y = pos['centered_line1_y']
        self.centered_line2.x = 0
        self.centered_line2.y = pos['centered_line2_y']
        self.centered_group = displayio.Group()
        self.centered_group.hidden = True
        self.centered_group.append(self.centered_line1)
        self.centered_group.append(self.centered_line2)

        self.queue_line1 = Label(self.font, text="Powered by")
        self.queue_line1.color = self._convert_color(ColorUtils.colors["Yellow"])
        self.queue_line1.x = 0
        self.queue_line1.y = pos['queue_line1_y']
        self.queue_line2 = Label(self.font, text="queue-times.com")
        self.queue_line2.color = self._convert_color(ColorUtils.colors["Orange"])
        self.queue_line2.x = 1
        self.queue_line2.y = pos['queue_line2_y']
        self.queue_group = displayio.Group()
        self.queue_group.hidden = True
        self.queue_group.append(self.queue_line1)
        self.queue_group.append(self.queue_line2)

        # scrolling_group is already added by GenericDisplay.initialize()
        self.main_group.append(self.wait_time_name_group)
        self.main_group.append(self.wait_time_group)
        self.main_group.append(self.closed_group)
        self.main_group.append(self.splash_group)
        self.main_group.append(self.update_group)
        self.main_group.append(self.required_group)
        self.main_group.append(self.centered_group)
        self.main_group.append(self.queue_group)

    def _hide_all_groups(self):
        """Hide all display groups including ThemePark-specific ones."""
        super()._hide_all_groups()
        for group in [
            self.wait_time_name_group, self.wait_time_group, self.closed_group,
            self.splash_group, self.update_group, self.required_group,
            self.centered_group, self.queue_group,
        ]:
            if group:
                group.hidden = True

    def set_colors(self, settings):
        """Set colors from settings."""
        if not hasattr(settings, 'settings'):
            return
        try:
            scale = float(settings.settings.get("brightness_scale", "0.5"))
            self.wait_time_name.color = self._convert_color(ColorUtils.scale_color(
                settings.settings.get("ride_name_color", ColorUtils.colors["Blue"]), scale))
            self.wait_time.color = self._convert_color(ColorUtils.scale_color(
                settings.settings.get("ride_wait_time_color", ColorUtils.colors["Old Lace"]), scale))
            self.closed.color = self.wait_time.color
            self.scrolling_label.color = self._convert_color(ColorUtils.scale_color(
                settings.settings.get("default_color", ColorUtils.colors["Yellow"]), scale))
            self.splash_line1.color = self._convert_color(ColorUtils.scale_color(ColorUtils.colors["Yellow"], scale))
            self.splash_line2.color = self._convert_color(ColorUtils.scale_color(ColorUtils.colors["Orange"], scale))
            self.update_line1.color = self.scrolling_label.color
            self.update_line2.color = self.scrolling_label.color
            self.required_line1.color = self.scrolling_label.color
            self.required_line2.color = self.scrolling_label.color
            self.centered_line1.color = self.scrolling_label.color
            self.centered_line2.color = self.scrolling_label.color
        except Exception as e:
            logger.error(e, "Error setting colors")

    async def run_async(self):
        """Run the display in an async loop with Theme Park Waits window title."""
        if IS_CIRCUITPYTHON:
            return
        import pygame
        if not pygame.get_init():
            pygame.init()
        screen = pygame.display.set_mode(
            (self.matrix.surface_width, self.matrix.surface_height))
        pygame.display.set_caption("Theme Park Waits - LED Simulator")
        clock = pygame.time.Clock()
        running = True
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    pygame.quit()
                    sys.exit(0)
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                        pygame.quit()
                        sys.exit(0)
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

    async def show_splash(self, duration=8, reveal_style=False):
        """Show the splash screen."""
        logger.debug(f"UnifiedDisplay.show_splash duration={duration}, reveal_style={reveal_style}")
        self._hide_all_groups()
        if reveal_style:
            await show_reveal_splash(self.main_group)
        else:
            self.splash_group.hidden = False
            await asyncio.sleep(duration)
            self.splash_group.hidden = True

    async def show_ride_name(self, ride_name):
        """Show a ride name and scroll it."""
        await asyncio.sleep(.5)
        self.wait_time_name.text = ride_name
        self.wait_time_name_group.hidden = False
        while self._scroll_x(self.wait_time_name):
            await asyncio.sleep(self.scroll_delay)
            self.update()
        await asyncio.sleep(1)
        self.wait_time.text = ""
        self.wait_time_name.text = ""
        self.wait_time_group.hidden = True
        self.wait_time_name_group.hidden = True
        self.closed_group.hidden = True

    async def show_ride_closed(self, dummy):
        """Show that a ride is closed."""
        self.closed_group.hidden = False

    async def show_ride_wait_time(self, ride_wait_time):
        """Show a ride wait time."""
        self.wait_time.text = ride_wait_time
        self._center_text(self.wait_time)
        self.wait_time_group.hidden = False

    async def show_scroll_message(self, message):
        """Show a scrolling message with full scroll animation."""
        logger.debug(f"Scrolling message: {message}")
        self._hide_all_groups()
        self.scrolling_label.text = message
        self.scrolling_group.hidden = False
        await asyncio.sleep(.5)
        while self._scroll_x(self.scrolling_label):
            await asyncio.sleep(self.scroll_delay)
            self.update()
        self.scrolling_group.hidden = True