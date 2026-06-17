#!/usr/bin/env python3
"""Simple static text test."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sldk.simulator.devices import MatrixPortalS3
from sldk.simulator.displayio import Group
from sldk.simulator.adafruit_display_text import Label
from sldk.simulator.terminalio import FONT
from sldk.simulator.core import CYAN, MAGENTA, YELLOW


def main():
    """Simple static text test."""
    print("Creating MatrixPortal S3...")
    device = MatrixPortalS3()
    device.initialize()
    
    # Create display group
    main_group = Group()
    
    # Create a simple static label first
    print("Creating static Label...")
    static_label = Label(
        font=FONT,
        text="HELLO",
        color=CYAN,
        x=0,
        y=8
    )
    print(f"Static label created: {static_label}")
    print(f"Static label text: '{static_label.text}'")
    print(f"Static label color: {static_label.color}")
    print(f"Static label position: ({static_label.x}, {static_label.y})")
    
    # Add to group
    main_group.append(static_label)
    print("Added static label to main group")
    
    # Show on display
    print("Showing on display...")
    device.show(main_group)
    print("Display shown")
    
    print("\nRunning simulation...")
    device.run(title="Simple Static Test")
    

if __name__ == "__main__":
    main()