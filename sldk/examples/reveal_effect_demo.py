#!/usr/bin/env python3
"""Simple demo of the RevealEffect for SLDK.

This demonstrates text reveal effects using proper text rendering.

NOTE: This is a simplified demo showing manual reveal implementation.
For the full SLDK effects framework usage, see reveal_effect_sldk_demo.py
"""

import os
import sys
import time

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def simple_reveal_demo():
    """Simple reveal effect demo using proper text rendering."""
    print("SLDK Reveal Effect Demo")
    print("=" * 40)
    print("Demonstrating text reveal effects with proper text rendering")
    
    # Import device and display components
    from sldk.simulator.devices import MatrixPortalS3
    from sldk.simulator.displayio import Group
    from sldk.simulator.adafruit_display_text import Label
    from sldk.simulator.terminalio import FONT
    
    # Create device
    device = MatrixPortalS3()
    device.initialize()
    
    # Create main display group
    main_group = Group()
    
    # Demo state
    demo_stage = 0
    stage_start = 0
    stage_names = ["Right Reveal", "Character Reveal", "Center Reveal"]
    
    # Create labels for each stage (initially empty)
    label1 = Label(font=FONT, text="", color=0x00FF00, scale=1)  # Green
    label1.x = 1  # Adjusted for longer text
    label1.y = 16
    
    label2 = Label(font=FONT, text="", color=0xFF0000, scale=1)  # Red
    label2.x = 2
    label2.y = 16
    
    label3 = Label(font=FONT, text="", color=0x0000FF, scale=1)  # Blue
    label3.x = 16  # Will be centered dynamically
    label3.y = 16
    
    # Add all labels to group (we'll control visibility via text content)
    main_group.append(label1)
    main_group.append(label2)
    main_group.append(label3)
    
    # Show the group on display
    device.display.show(main_group)
    
    def update():
        """Update function called each frame."""
        nonlocal demo_stage, stage_start
        
        current_time = time.time()
        if stage_start == 0:
            stage_start = current_time
        
        elapsed = current_time - stage_start
        
        if demo_stage == 0:
            # Stage 1: Right reveal of "WE LOVE ADAFRUIT"
            text = "WE LOVE ADAFRUIT"
            reveal_duration = 3.0
            
            # Clear other labels
            label2.text = ""
            label3.text = ""
            
            if elapsed < reveal_duration:
                # Revealing from left to right
                progress = min(elapsed / reveal_duration, 1.0)
                reveal_chars = int(len(text) * progress)
                label1.text = text[:reveal_chars]
            else:
                # Fully revealed
                label1.text = text
                        
        elif demo_stage == 1:
            # Stage 2: Character-by-character reveal of "SLDK DEMO"
            text = "SLDK DEMO"
            reveal_duration = 3.0
            
            # Clear other labels
            label1.text = ""
            label3.text = ""
            
            if elapsed < reveal_duration:
                # Revealing character by character
                progress = min(elapsed / reveal_duration, 1.0)
                reveal_chars = int(len(text) * progress)
                label2.text = text[:reveal_chars]
            else:
                # Fully revealed
                label2.text = text
                                
        elif demo_stage == 2:
            # Stage 3: Center reveal of "REVEAL"
            text = "REVEAL"
            reveal_duration = 3.0
            
            # Clear other labels
            label1.text = ""
            label2.text = ""
            
            if elapsed < reveal_duration:
                # Revealing from center outwards
                progress = min(elapsed / reveal_duration, 1.0)
                text_len = len(text)
                center = text_len // 2
                
                # Calculate how many characters to show from center
                chars_to_show = int(text_len * progress)
                half_chars = chars_to_show // 2
                
                if chars_to_show > 0:
                    # Build the revealed text from center outwards
                    if chars_to_show == 1:
                        # Start with center character
                        label3.text = text[center]
                    else:
                        # Expand from center
                        start_idx = max(0, center - half_chars)
                        end_idx = min(text_len, center + half_chars + 1)
                        label3.text = text[start_idx:end_idx]
                    
                    # Center the label
                    label3.x = 32 - (len(label3.text) * 3)
                else:
                    label3.text = ""
            else:
                # Fully revealed
                label3.text = text
                label3.x = 32 - (len(text) * 3)
        
        # Force display refresh
        device.display.show(main_group)
        
        # Advance stages
        stage_duration = 5
        if elapsed >= stage_duration:
            demo_stage = (demo_stage + 1) % 3  # 3 total stages
            stage_start = current_time
            
            # Update window title with current effect name
            import pygame
            if pygame.display.get_init():
                new_title = f"SLDK Reveal Effect Demo - {stage_names[demo_stage]}"
                pygame.display.set_caption(new_title)
            
            print(f"Reveal Demo Stage {demo_stage + 1}: {stage_names[demo_stage]}")
        
        return True
    
    # Use device.run() 
    device.run(update_callback=update, title="SLDK Reveal Effect Demo")


def main():
    """Main entry point."""
    simple_reveal_demo()


if __name__ == "__main__":
    main()