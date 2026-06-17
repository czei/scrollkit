#!/usr/bin/env python3
"""
SLDK Tutorial 05: Progressive Demo
This file contains examples of increasing complexity.
Uncomment sections as you learn to explore more features!
"""

from sldk.app import MinimalLEDApp
import time

# Create our app
app = MinimalLEDApp()

# ============================================================================
# LEVEL 1: Absolute Beginner (Uncommented by default)
# ============================================================================
print("=== LEVEL 1: Hello World ===")
app.show_text("Hello!", color="green")
time.sleep(2)


# ============================================================================
# LEVEL 2: Basic Colors and Text
# Uncomment this section when ready!
# ============================================================================
"""
print("\n=== LEVEL 2: Colors and Text ===")

# Try different colors
basic_colors = ["red", "green", "blue", "yellow", "purple", "cyan", "white"]
for color in basic_colors:
    app.show_text(color.upper()[:4], color=color)  # Show first 4 letters
    time.sleep(0.5)

# Show numbers
for i in range(10):
    app.show_text(str(i), color="cyan")
    time.sleep(0.3)
"""


# ============================================================================
# LEVEL 3: Simple Animations
# Uncomment when comfortable with Level 2
# ============================================================================
"""
print("\n=== LEVEL 3: Simple Animations ===")

# Scrolling message
app.scroll_text("Welcome to SLDK!", color="purple", delay=0.05)

# Pulsing effect (bright to dim)
for _ in range(3):
    for brightness in range(255, 0, -25):
        app.show_text("PULSE", color=(brightness, 0, 0))
        time.sleep(0.05)
    for brightness in range(0, 255, 25):
        app.show_text("PULSE", color=(brightness, 0, 0))
        time.sleep(0.05)

# Moving dot animation
for x in range(64):
    app.clear()
    # This would set a single pixel in full app
    # For now, show position as number
    app.show_text(str(x % 10), color="green")
    time.sleep(0.05)
"""


# ============================================================================
# LEVEL 4: Interactive Patterns
# Uncomment when comfortable with animations
# ============================================================================
"""
print("\n=== LEVEL 4: Interactive Patterns ===")

# Temperature display simulator
import random

for _ in range(10):
    temp = random.randint(60, 90)
    if temp < 70:
        color = "blue"
    elif temp < 80:
        color = "green"
    else:
        color = "red"
    
    app.show_text(f"{temp}F", color=color)
    time.sleep(1)

# Simple menu system
menu_items = ["Play", "Stop", "Next", "Prev"]
selected = 0

for _ in range(8):  # Simulate menu navigation
    item = menu_items[selected]
    app.show_text(item, color="yellow")
    time.sleep(0.5)
    selected = (selected + 1) % len(menu_items)
"""


# ============================================================================
# LEVEL 5: Advanced Concepts
# Uncomment when ready for advanced features
# ============================================================================
"""
print("\n=== LEVEL 5: Advanced Concepts ===")

# Custom color gradients
def gradient_color(position, max_pos):
    # Create gradient from red to blue
    ratio = position / max_pos
    r = int(255 * (1 - ratio))
    b = int(255 * ratio)
    return (r, 0, b)

# Show gradient effect
for i in range(20):
    color = gradient_color(i, 19)
    app.show_text("GRAD", color=color)
    time.sleep(0.1)

# Matrix-style falling text
chars = "01"
for _ in range(30):
    char = chars[random.randint(0, 1)]
    green_shade = random.randint(100, 255)
    app.show_text(char, color=(0, green_shade, 0))
    time.sleep(0.1)

# Create a simple graph/meter
levels = [2, 4, 6, 8, 6, 4, 2, 1, 3, 5, 7, 8, 7, 5, 3]
for level in levels:
    # Show level as a number (in full app, this would be a bar graph)
    app.show_text("|" * min(level, 4), color="cyan")  # Limit to 4 chars
    time.sleep(0.2)

# Time-based color changes
start_time = time.time()
duration = 5  # Run for 5 seconds

while time.time() - start_time < duration:
    # Color changes based on time
    elapsed = time.time() - start_time
    hue = int((elapsed * 72) % 360)  # 72 degrees per second
    
    # Simple HSV to RGB
    if hue < 120:
        color = (255 - hue * 2, hue * 2, 0)
    elif hue < 240:
        color = (0, 255 - (hue - 120) * 2, (hue - 120) * 2)
    else:
        color = ((hue - 240) * 2, 0, 255 - (hue - 240) * 2)
    
    app.show_text("TIME", color=color)
    time.sleep(0.05)
"""


# ============================================================================
# LEVEL 6: Your Own Experiments!
# Add your own code here!
# ============================================================================
"""
print("\n=== LEVEL 6: Your Experiments ===")

# Your code here!
# Some ideas:
# - Create a bouncing ball animation
# - Make a simple game display
# - Show sensor data (temperature, distance, etc.)
# - Create custom fonts or symbols
# - Build a notification system
# - Make music visualizations

# Example: Your name in favorite color
# app.scroll_text("YOUR NAME HERE", color="your_favorite_color", delay=0.03)
"""

# ============================================================================
# Closing message
# ============================================================================
print("\n=== Demo Complete! ===")
app.scroll_text("Experiment and have fun with SLDK!", color="rainbow", delay=0.03)
app.show_text("END", color="green")
time.sleep(2)