#!/usr/bin/env python3
"""Debug scrolling text display."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sldk.simulator.devices import MatrixPortalS3
from sldk.simulator.displayio import Group
from sldk.simulator.adafruit_display_text import ScrollingLabel
from sldk.simulator.terminalio import FONT
from sldk.simulator.core import CYAN, MAGENTA, YELLOW


def main():
    """Debug scrolling text display."""
    print("Creating MatrixPortal S3...")
    device = MatrixPortalS3()
    print(f"Device created: {device}")
    
    print("Initializing device...")
    device.initialize()
    print("Device initialized")
    
    # Create display group
    main_group = Group()
    print(f"Main group created: {main_group}")
    
    # Create a simple scrolling label
    print("Creating ScrollingLabel...")
    scroll_label = ScrollingLabel(
        font=FONT,
        text="Hello World! This is a scrolling message...",
        max_characters=10,
        color=CYAN,
        x=0,
        y=8,
        animate_time=0.3
    )
    print(f"ScrollingLabel created: {scroll_label}")
    print(f"ScrollingLabel text: '{scroll_label.text}'")
    print(f"ScrollingLabel full_text: '{scroll_label.full_text}'")
    print(f"ScrollingLabel max_characters: {scroll_label.max_characters}")
    print(f"ScrollingLabel color: {scroll_label.color}")
    
    # Add to group
    main_group.append(scroll_label)
    print("Added ScrollingLabel to main group")
    
    # Start scrolling
    print("Starting scrolling...")
    scroll_label.start_scrolling()
    print(f"Is scrolling: {scroll_label.is_scrolling}")
    
    # Show on display
    print("Showing on display...")
    device.show(main_group)
    print("Display shown")
    
    # Test a few manual updates
    print("\nTesting manual updates:")
    for i in range(5):
        print(f"Update {i+1}:")
        result = scroll_label.update(force=True)
        print(f"  Update result: {result}")
        print(f"  Current text: '{scroll_label.text}'")
        print(f"  Current index: {scroll_label.current_index}")
    
    print("\nRunning simulation...")
    
    def update():
        """Update function called each frame."""
        updated = scroll_label.update()
        if updated:
            print(f"Frame update - Current text: '{scroll_label.text}' (index: {scroll_label.current_index})")
    
    device.run(update_callback=update, title="Debug Scrolling")
    

if __name__ == "__main__":
    main()