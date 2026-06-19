"""Manages multiple LED matrix displays."""

import pygame
import sys


class DisplayManager:
    """Manages multiple LED matrix displays.
    
    This class handles the pygame window creation, event processing,
    and coordination of multiple LED matrix displays.
    """
    
    def __init__(self):
        """Initialize display manager."""
        self.displays = []
        self.display_positions = {}
        self.window = None
        self.window_width = 800
        self.window_height = 600
        self.background_color = (0, 0, 0)
        self.running = False
        self.clock = None
        self.target_fps = 60
        self.event_handlers = {}
        self.update_callback = None
        
    def add_display(self, display, position=(0, 0), name=None):
        """Add a display at specified position.
        
        Args:
            display: LEDMatrix instance
            position: (x, y) position in window
            name: Optional name for the display
        """
        self.displays.append(display)
        self.display_positions[display] = position
        
        if name:
            self.display_positions[name] = display
            
        # Recalculate window size if needed
        self._update_window_size()
        
    def create_window(self, title="LED Simulator", width=None, height=None, 
                     fullscreen=False, resizable=True):
        """Create pygame window for all displays.
        
        Args:
            title: Window title
            width: Window width (auto-calculated if None)
            height: Window height (auto-calculated if None)
            fullscreen: Whether to create fullscreen window
            resizable: Whether window is resizable
        """
        if not pygame.get_init():
            pygame.init()
            
        # Set window size
        if width:
            self.window_width = width
        if height:
            self.window_height = height
            
        # Create window
        flags = 0
        if fullscreen:
            flags |= pygame.FULLSCREEN
        if resizable:
            flags |= pygame.RESIZABLE
            
        self.window = pygame.display.set_mode(
            (self.window_width, self.window_height), flags
        )
        pygame.display.set_caption(title)
        
        # Create clock for FPS control
        self.clock = pygame.time.Clock()
        
    def _update_window_size(self):
        """Update window size based on display positions."""
        if not self.displays:
            return
            
        max_x = 0
        max_y = 0
        
        for display in self.displays:
            pos_x, pos_y = self.display_positions[display]
            max_x = max(max_x, pos_x + display.surface_width)
            max_y = max(max_y, pos_y + display.surface_height)
            
        # Add minimal padding for realistic appearance
        self.window_width = max_x + 4
        self.window_height = max_y + 4
        
    def update(self):
        """Update all displays and window."""
        if not self.window:
            return
            
        # Clear window
        self.window.fill(self.background_color)
        
        # Render and blit each display
        for display in self.displays:
            display.render()
            surface = display.get_surface()
            position = self.display_positions[display]
            self.window.blit(surface, position)
            
        # Update display
        pygame.display.flip()
        
        # Control frame rate
        if self.clock:
            self.clock.tick(self.target_fps)
            
    def handle_events(self):
        """Handle pygame events.
        
        Returns:
            False if quit event received, True otherwise
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
                
            # Check custom event handlers
            if event.type in self.event_handlers:
                self.event_handlers[event.type](event)
                
            # Handle keyboard events
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                elif event.key == pygame.K_s and event.mod & pygame.KMOD_CTRL:
                    # Ctrl+S to save screenshot
                    self.save_screenshot("screenshot.png")
                    
        return True
        
    def run(self, update_callback=None):
        """Run the display manager main loop.
        
        Args:
            update_callback: Optional function to call each frame
        """
        if not self.window:
            self.create_window()
            
        self.running = True
        self.update_callback = update_callback
        
        while self.running:
            # Handle events
            self.running = self.handle_events()
            
            # Call update callback if provided
            if self.update_callback:
                self.update_callback()
                
            # Update displays
            self.update()
            
        self.quit()
        
    def run_once(self):
        """Run a single update cycle without entering main loop."""
        if not self.window:
            self.create_window()
            
        self.handle_events()
        if self.update_callback:
            self.update_callback()
        self.update()
        
    def quit(self):
        """Quit pygame and clean up."""
        self.running = False
        pygame.quit()
        
    def save_screenshot(self, filename):
        """Save a screenshot of the entire window.
        
        Args:
            filename: Path to save the screenshot
        """
        if self.window:
            pygame.image.save(self.window, filename)
            print(f"Screenshot saved to {filename}")
            
    def set_event_handler(self, event_type, handler):
        """Set a custom event handler.
        
        Args:
            event_type: Pygame event type
            handler: Function to call for this event type
        """
        self.event_handlers[event_type] = handler
        
    def get_display_by_name(self, name):
        """Get a display by its name.
        
        Args:
            name: Display name
            
        Returns:
            Display instance or None
        """
        return self.display_positions.get(name)