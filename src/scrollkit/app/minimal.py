# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Minimal LED App - Simplified API for SLDK applications.

Provides convenience functions for quick LED matrix programming.
"""

import sys
import gc

# Import base app
from .base import SLDKApp

# Try to detect environment
def is_circuitpython():
    """Check if running on CircuitPython."""
    return hasattr(sys, 'implementation') and sys.implementation.name == 'circuitpython'

def get_memory_info():
    """Get memory information."""
    gc.collect()
    if hasattr(gc, 'mem_free'):
        # CircuitPython
        return type('MemInfo', (), {
            'free': gc.mem_free(),
            'used': gc.mem_alloc() if hasattr(gc, 'mem_alloc') else 0
        })
    else:
        # Standard Python - simulate high memory
        return type('MemInfo', (), {
            'free': 500 * 1024 * 1024,  # 500MB
            'used': 100 * 1024 * 1024   # 100MB
        })


class MinimalLEDApp:
    """Simplified LED application with convenience functions.
    
    This class provides a minimal API for LED matrix programming:
    - show_text(text, color) - Display static text
    - scroll_text(text, color, delay) - Scroll text across display
    - clear() - Clear the display
    
    Automatically detects environment and adjusts features.
    """
    
    # Color name to RGB mapping
    COLORS = {
        'red': (255, 0, 0),
        'green': (0, 255, 0),
        'blue': (0, 0, 255),
        'yellow': (255, 255, 0),
        'purple': (128, 0, 128),
        'cyan': (0, 255, 255),
        'white': (255, 255, 255),
        'orange': (255, 165, 0),
        'pink': (255, 192, 203),
        'magenta': (255, 0, 255),
        'lime': (0, 255, 0),
        'teal': (0, 128, 128),
        'navy': (0, 0, 128),
        'brown': (165, 42, 42),
        'gray': (128, 128, 128),
        'grey': (128, 128, 128),
        'black': (0, 0, 0),
    }
    
    def __init__(self):
        """Initialize minimal LED app with auto-detection."""
        # Detect environment
        self.is_circuitpython = is_circuitpython()
        mem_info = get_memory_info()
        
        # Choose appropriate app based on environment
        if self.is_circuitpython or mem_info.free < 100 * 1024:  # < 100KB
            # Use lightweight CircuitPython app
            self.app = CircuitPythonApp()
        else:
            # Use full-featured standard Python app
            self.app = StandardPythonApp()
        
        print(f"MinimalLEDApp initialized ({'CircuitPython' if self.is_circuitpython else 'Standard Python'})")
        print(f"Free memory: {mem_info.free // 1024}KB")
    
    def _parse_color(self, color):
        """Parse color input to RGB tuple."""
        if isinstance(color, str):
            # Special case for rainbow
            if color.lower() == 'rainbow':
                # Return special marker for rainbow effect
                return 'rainbow'
            # Look up color name
            return self.COLORS.get(color.lower(), (255, 255, 255))  # Default white
        elif isinstance(color, (tuple, list)) and len(color) == 3:
            # Already RGB tuple
            return tuple(color)
        else:
            # Default to white
            return (255, 255, 255)
    
    def show_text(self, text, color=(255, 255, 255)):
        """Display static text on the LED matrix.
        
        Args:
            text: Text to display (will be truncated to fit)
            color: RGB tuple (r, g, b) or color name string
        """
        color = self._parse_color(color)
        self.app.display_static_text(text, color)
    
    def scroll_text(self, text, color=(255, 255, 255), delay=0.05):
        """Scroll text across the LED matrix.
        
        Args:
            text: Text to scroll
            color: RGB tuple (r, g, b) or color name string
            delay: Delay between scroll steps (seconds)
        """
        color = self._parse_color(color)
        
        # Handle rainbow as special scrolling effect
        if color == 'rainbow':
            # Implement rainbow scroll
            self.app.rainbow_scroll_text(text, delay)
        else:
            self.app.scroll_text(text, color, delay)
    
    def clear(self):
        """Clear the LED display."""
        self.app.clear()


# Platform-specific implementations

class CircuitPythonApp:
    """Lightweight app for CircuitPython environment."""
    
    def __init__(self):
        """Initialize CircuitPython app."""
        try:
            # Try to import CircuitPython display modules
            import board
            import displayio
            from adafruit_matrixportal.matrix import Matrix
            
            # Initialize matrix
            self.matrix = Matrix()
            self.display = self.matrix.display
            
            # Create display group
            self.group = displayio.Group()
            self.display.root_group = self.group
            
            print("CircuitPython Matrix initialized")
            
        except ImportError:
            # Fallback to terminal display
            print("No CircuitPython hardware - using terminal display")
            self.matrix = None
            self.display = None
    
    def display_static_text(self, text, color):
        """Display static text."""
        if self.matrix:
            # Use CircuitPython display
            # This is simplified - real implementation would use bitmap fonts
            print(f"LED: {text} in color {color}")
        else:
            # Terminal display
            print(f"[{self._color_name(color)}] {text}")
    
    def scroll_text(self, text, color, delay):
        """Scroll text across display."""
        import time
        
        # Simple terminal scroll simulation
        width = 8  # Assume 8 character display
        padded = "  " + text + "  "
        
        for i in range(len(padded)):
            visible = padded[i:i+width]
            if len(visible) < width:
                visible += " " * (width - len(visible))
            print(f"\r[{self._color_name(color)}] {visible}", end='', flush=True)
            time.sleep(delay)
        print()  # New line after scroll
    
    def rainbow_scroll_text(self, text, delay):
        """Scroll with rainbow effect."""
        import time
        colors = [(255,0,0), (255,128,0), (255,255,0), (0,255,0), 
                  (0,255,255), (0,0,255), (128,0,255)]
        
        width = 8
        padded = "  " + text + "  "
        
        for i in range(len(padded)):
            color = colors[i % len(colors)]
            visible = padded[i:i+width]
            if len(visible) < width:
                visible += " " * (width - len(visible))
            print(f"\r[Rainbow] {visible}", end='', flush=True)
            time.sleep(delay)
        print()
    
    def clear(self):
        """Clear display."""
        if self.matrix:
            # Clear CircuitPython display
            print("LED: [cleared]")
        else:
            # Clear terminal line
            print("\r" + " " * 40 + "\r", end='', flush=True)
    
    def _color_name(self, color):
        """Get color name for terminal display."""
        if color == (255, 0, 0): return "RED"
        elif color == (0, 255, 0): return "GREEN"
        elif color == (0, 0, 255): return "BLUE"
        elif color == (255, 255, 0): return "YELLOW"
        elif color == (255, 255, 255): return "WHITE"
        else: return f"RGB{color}"


class StandardPythonApp:
    """Full-featured app for standard Python environment."""
    
    def __init__(self):
        """Initialize standard Python app."""
        try:
            # Try to use SLDK simulator
            from ..simulator import TerminalDisplay
            self.display = TerminalDisplay(width=64, height=8)
            print("SLDK Terminal Display initialized")
        except ImportError:
            # Fallback to simple print
            self.display = None
            print("Using simple terminal output")
    
    def display_static_text(self, text, color):
        """Display static text."""
        if self.display:
            # Use SLDK display
            self.display.clear()
            self.display.draw_text(0, 0, text, color)
            self.display.show()
        else:
            # Simple print
            print(f"[{self._color_name(color)}] {text}")
    
    def scroll_text(self, text, color, delay):
        """Scroll text across display."""
        import time
        
        if self.display:
            # Use SLDK scrolling
            width = self.display.width // 6  # Assume 6-pixel wide chars
            padded = "  " + text + "  "
            
            for i in range(len(padded)):
                self.display.clear()
                visible = padded[i:i+width]
                self.display.draw_text(0, 0, visible, color)
                self.display.show()
                time.sleep(delay)
        else:
            # Terminal scroll
            width = 10
            padded = "  " + text + "  "
            
            for i in range(len(padded)):
                visible = padded[i:i+width]
                if len(visible) < width:
                    visible += " " * (width - len(visible))
                print(f"\r[{self._color_name(color)}] {visible}", end='', flush=True)
                time.sleep(delay)
            print()
    
    def rainbow_scroll_text(self, text, delay):
        """Scroll with rainbow effect."""
        import time
        colors = [(255,0,0), (255,128,0), (255,255,0), (0,255,0), 
                  (0,255,255), (0,0,255), (128,0,255)]
        
        if self.display:
            width = self.display.width // 6
            padded = "  " + text + "  "
            
            for i in range(len(padded)):
                self.display.clear()
                visible = padded[i:i+width]
                
                # Draw each character in different color
                for j, char in enumerate(visible):
                    color = colors[(i + j) % len(colors)]
                    self.display.draw_text(j * 6, 0, char, color)
                
                self.display.show()
                time.sleep(delay)
        else:
            # Terminal rainbow
            width = 10
            padded = "  " + text + "  "
            
            for i in range(len(padded)):
                visible = padded[i:i+width]
                if len(visible) < width:
                    visible += " " * (width - len(visible))
                print(f"\r[RAINBOW] {visible}", end='', flush=True)
                time.sleep(delay)
            print()
    
    def clear(self):
        """Clear display."""
        if self.display:
            self.display.clear()
            self.display.show()
        else:
            print("\r" + " " * 50 + "\r", end='', flush=True)
    
    def _color_name(self, color):
        """Get color name for terminal display."""
        if color == (255, 0, 0): return "RED"
        elif color == (0, 255, 0): return "GREEN"
        elif color == (0, 0, 255): return "BLUE"
        elif color == (255, 255, 0): return "YELLOW"
        elif color == (255, 255, 255): return "WHITE"
        elif color == (128, 0, 128): return "PURPLE"
        elif color == (0, 255, 255): return "CYAN"
        elif color == (255, 165, 0): return "ORANGE"
        else: return f"RGB{color}"