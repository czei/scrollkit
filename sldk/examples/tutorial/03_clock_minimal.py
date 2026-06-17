#!/usr/bin/env python3
"""
SLDK Tutorial 03: Clock Minimal
Create a simple digital clock that updates every second.
"""

from sldk.app import MinimalLEDApp
import time

app = MinimalLEDApp()

# Simple clock - runs for 60 seconds
for i in range(60):
    # Get current time
    current_time = time.strftime("%H:%M:%S")
    
    # Display it
    app.show_text(current_time, color="cyan")
    
    # Wait one second
    time.sleep(1)

# Final message
app.show_text("Time's up!", color="yellow")