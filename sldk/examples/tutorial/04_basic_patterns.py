#!/usr/bin/env python3
"""
SLDK Tutorial 04: Basic Patterns
Common LED display patterns you'll want to use.
"""

from sldk.app import MinimalLEDApp
import time

app = MinimalLEDApp()

# Pattern 1: Scrolling Text
print("Pattern 1: Scrolling Text")
app.scroll_text("This is a long message that will scroll across the display!", 
                color="green", delay=0.05)

# Pattern 2: Color Cycling
print("\nPattern 2: Color Cycling")
colors = [
    (255, 0, 0),    # Red
    (255, 128, 0),  # Orange  
    (255, 255, 0),  # Yellow
    (0, 255, 0),    # Green
    (0, 0, 255),    # Blue
    (128, 0, 255),  # Purple
]

for i in range(3):  # Cycle 3 times
    for color in colors:
        app.show_text("COLOR", color=color)
        time.sleep(0.3)

# Pattern 3: Flashing/Blinking
print("\nPattern 3: Flashing")
for i in range(5):
    app.show_text("ALERT!", color="red")
    time.sleep(0.5)
    app.clear()
    time.sleep(0.5)

# Pattern 4: Countdown
print("\nPattern 4: Countdown")
for i in range(10, 0, -1):
    app.show_text(str(i), color="cyan")
    time.sleep(1)
app.show_text("GO!", color="green")
time.sleep(2)

# Pattern 5: Progress Bar (using fill)
print("\nPattern 5: Progress Bar")
for i in range(0, 101, 10):
    app.clear()
    app.show_text(f"{i}%", color="yellow")
    time.sleep(0.5)

# Pattern 6: Rainbow Text
print("\nPattern 6: Rainbow Effect")
text = "RAINBOW"
for i in range(20):
    # Cycle through spectrum
    hue = (i * 18) % 360  # 0-360 degrees
    # Simple HSV to RGB conversion (simplified)
    if hue < 120:
        r = 255 - (hue * 255 // 120)
        g = hue * 255 // 120
        b = 0
    elif hue < 240:
        r = 0
        g = 255 - ((hue - 120) * 255 // 120)
        b = (hue - 120) * 255 // 120
    else:
        r = (hue - 240) * 255 // 120
        g = 0
        b = 255 - ((hue - 240) * 255 // 120)
    
    app.show_text(text, color=(r, g, b))
    time.sleep(0.1)

# Done!
app.scroll_text("Tutorial Complete! Happy LED Programming!", color="purple", delay=0.03)