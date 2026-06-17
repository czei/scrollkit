#!/usr/bin/env python3
"""
SLDK Tutorial 02: Colors Minimal
Learn how to add colors to your LED display!
"""

from sldk.app import MinimalLEDApp

# Create app instance (you can reuse it)
app = MinimalLEDApp()

# Show text in different colors
app.show_text("Red", color=(255, 0, 0))
app.show_text("Green", color=(0, 255, 0))
app.show_text("Blue", color=(0, 0, 255))

# Use convenience color names
app.show_text("Yellow", color="yellow")
app.show_text("Purple", color="purple")
app.show_text("Cyan", color="cyan")

# Custom colors with RGB values
app.show_text("Orange", color=(255, 128, 0))
app.show_text("Pink", color=(255, 192, 203))