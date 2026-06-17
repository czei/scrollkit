#!/usr/bin/env python3
"""Working reveal effect demo using SLDK's RevealEffect class.

This demonstrates the actual RevealEffect implementation with async/await.
"""

import asyncio
import os
import sys

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from sldk.simulator.devices import MatrixPortalS3
from sldk.simulator.displayio import Group
from sldk.simulator.adafruit_display_text import Label
from sldk.simulator.terminalio import FONT
from sldk.effects import RevealEffect
from sldk.display.manager import DisplayManager


async def reveal_demo():
    """Demonstrate RevealEffect with actual implementation."""
    print("SLDK RevealEffect Demo - Working Implementation")
    print("=" * 50)
    
    # Create device
    device = MatrixPortalS3()
    device.initialize()
    
    # Create display manager
    manager = DisplayManager(device.display)
    await manager.start()
    
    # Create main group
    main_group = Group()
    
    # Create labels for text
    label = Label(font=FONT, text="ADAFRUIT", color=0x00FF00, scale=1)
    label.x = 1
    label.y = 16
    main_group.append(label)
    
    device.display.show(main_group)
    
    # Create reveal effect
    reveal = RevealEffect(
        duration=3.0,
        direction='right',
        pause_at_end=2.0
    )
    
    print("Starting reveal effect...")
    print(f"Direction: {reveal.direction}")
    print(f"Duration: {reveal.reveal_duration}s")
    print(f"Pause at end: {reveal.pause_at_end}s")
    print()
    
    # Define the render function
    async def render_func():
        """Function that renders the content."""
        device.display.show(main_group)
        if hasattr(device.display, 'refresh'):
            device.display.refresh()
    
    # Apply the reveal effect
    try:
        await reveal.apply(device.display, render_func)
        print("Reveal effect completed!")
    except Exception as e:
        print(f"Error during reveal effect: {e}")
        import traceback
        traceback.print_exc()
    
    # Keep display active for a bit
    await asyncio.sleep(2)
    
    # Cleanup
    await manager.stop()
    print("Demo complete!")


def main():
    """Main entry point."""
    print("This demo shows the actual RevealEffect class in action.")
    print("The effect will reveal 'WE LOVE ADAFRUIT' from left to right.")
    print()
    
    try:
        asyncio.run(reveal_demo())
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")


if __name__ == "__main__":
    main()
