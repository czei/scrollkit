#!/usr/bin/env python3
"""Test LED display with window that stays open."""

import sys
import os
import time
import asyncio

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from sldk.display.simulator import SimulatorDisplay

async def test_led_display():
    """Test LED display with visible content."""
    print("Creating LED display...")
    display = SimulatorDisplay(width=64, height=32)
    await display.initialize()
    
    print("Setting up initial pattern...")
    # Create a simple test pattern
    for x in range(64):
        await display.set_pixel(x, 10, 0xFF0000)  # Red line
        await display.set_pixel(x, 15, 0x00FF00)  # Green line
        await display.set_pixel(x, 20, 0x0000FF)  # Blue line
    
    print("Starting display loop...")
    print("Press Ctrl+C to exit, or close the window")
    
    try:
        frame = 0
        while True:
            # Animate a moving dot
            dot_x = (frame // 2) % 64
            
            # Clear previous dot
            if dot_x > 0:
                await display.set_pixel(dot_x - 1, 5, 0x000000)
            
            # Draw new dot
            await display.set_pixel(dot_x, 5, 0xFFFF00)  # Yellow dot
            
            # Update display
            result = await display.show()
            if not result:  # Window was closed
                print("Window closed by user")
                break
                
            await asyncio.sleep(0.05)  # 20 FPS
            frame += 1
            
            if frame % 200 == 0:  # Every 10 seconds
                print(f"Frame {frame} - display still running")
                
    except KeyboardInterrupt:
        print("Stopped by user (Ctrl+C)")
    
    print("Test complete")

if __name__ == "__main__":
    asyncio.run(test_led_display())