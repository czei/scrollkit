#!/usr/bin/env python3
"""Educational bridge between manual reveal implementation and SLDK framework.

This demo shows:
1. How the manual reveal implementation works (what you see)
2. How the SLDK effects framework API looks (what you should use)
3. The relationship between the two approaches

For the full async implementation, see reveal_effect_async_demo.py
"""

import os
import sys
import time

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


def reveal_effect_sldk_demo():
    """Educational demo showing manual vs framework approaches."""
    print("SLDK Reveal Effect - Educational Demo")
    print("=" * 40)
    print("This demo shows the manual implementation alongside")
    print("the SLDK framework API that should be used instead.")
    print()
    
    # Import SLDK components
    from sldk.simulator.devices import MatrixPortalS3
    from sldk.simulator.displayio import Group
    from sldk.simulator.adafruit_display_text import Label
    from sldk.simulator.terminalio import FONT
    # Note: In the full SLDK framework, you would also import:
    # from sldk.content_classes import create_splash, create_text
    # from sldk.effects import RevealEffect, RevealCenterEffect
    
    # Create device
    device = MatrixPortalS3()
    device.initialize()
    
    # Create main display group
    main_group = Group()
    
    # Demo state
    demo_stage = 0
    stage_start = 0
    stage_names = ["SLDK Splash Reveal", "Text with Effects", "Center Reveal"]
    
    # Labels for displaying content
    label1 = Label(font=FONT, text="", color=0x00FF00, scale=1)
    label1.x = 1
    label1.y = 16
    
    label2 = Label(font=FONT, text="", color=0xFF0000, scale=1)
    label2.x = 2
    label2.y = 16
    
    label3 = Label(font=FONT, text="", color=0x0000FF, scale=1)
    label3.x = 16
    label3.y = 16
    
    main_group.append(label1)
    main_group.append(label2)
    main_group.append(label3)
    
    device.display.show(main_group)
    
    print("===== UNDERSTANDING THE APPROACHES =====")
    print()
    print("MANUAL APPROACH (what this demo does):")
    print("  - Manually control label.text to reveal characters")
    print("  - Use time-based progress calculation")
    print("  - Directly manipulate display elements")
    print()
    print("FRAMEWORK APPROACH (what you should use):")
    print("  - Use async/await with DisplayManager")
    print("  - Effects handle timing and rendering")
    print("  - Declarative API with fluent interface")
    print()
    print("Starting manual demo in 3 seconds...")
    time.sleep(3)
    
    def update():
        """Update function called each frame."""
        nonlocal demo_stage, stage_start
        
        current_time = time.time()
        if stage_start == 0:
            stage_start = current_time
        
        elapsed = current_time - stage_start
        
        if demo_stage == 0:
            # MANUAL IMPLEMENTATION: Right reveal
            # What you see: Characters appearing one by one from left to right
            # 
            # FRAMEWORK EQUIVALENT:
            # splash = create_splash("WE LOVE ADAFRUIT").with_effect(
            #     RevealEffect(duration=3.0, direction='right')
            # )
            
            text = "WE LOVE ADAFRUIT"
            reveal_duration = 3.0
            
            label2.text = ""
            label3.text = ""
            
            if elapsed < reveal_duration:
                # Simulating RevealEffect's right direction reveal
                progress = min(elapsed / reveal_duration, 1.0)
                reveal_chars = int(len(text) * progress)
                label1.text = text[:reveal_chars]
                label1.color = 0x00FF00  # Green like a splash screen
            else:
                label1.text = text
                
        elif demo_stage == 1:
            # Stage 2: Demonstrate create_text with effects
            # In the full framework:
            # text_content = create_text("SLDK EFFECTS").with_effect(
            #     RevealEffect(duration=3.0, direction='down')
            # )
            
            text = "SLDK EFFECTS"
            reveal_duration = 3.0
            
            label1.text = ""
            label3.text = ""
            
            if elapsed < reveal_duration:
                # Simulating character-by-character reveal (like down reveal)
                progress = min(elapsed / reveal_duration, 1.0)
                reveal_chars = int(len(text) * progress)
                label2.text = text[:reveal_chars]
                label2.color = 0xFF0000  # Red for emphasis
            else:
                label2.text = text
                
        elif demo_stage == 2:
            # Stage 3: Demonstrate RevealCenterEffect
            # In the full framework:
            # center_reveal = create_text("REVEAL DEMO").with_effect(
            #     RevealCenterEffect(duration=3.0, mode='expand')
            # )
            
            text = "REVEAL DEMO"
            reveal_duration = 3.0
            
            label1.text = ""
            label2.text = ""
            
            if elapsed < reveal_duration:
                # Simulating center reveal effect
                progress = min(elapsed / reveal_duration, 1.0)
                text_len = len(text)
                center = text_len // 2
                
                chars_to_show = int(text_len * progress)
                half_chars = chars_to_show // 2
                
                if chars_to_show > 0:
                    if chars_to_show == 1:
                        label3.text = text[center]
                    else:
                        start_idx = max(0, center - half_chars)
                        end_idx = min(text_len, center + half_chars + 1)
                        label3.text = text[start_idx:end_idx]
                    
                    # Center the label
                    label3.x = 32 - (len(label3.text) * 3)
                    label3.color = 0x0000FF  # Blue
                else:
                    label3.text = ""
            else:
                label3.text = text
                label3.x = 32 - (len(text) * 3)
        
        # Force display refresh
        device.display.show(main_group)
        
        # Advance stages
        stage_duration = 5
        if elapsed >= stage_duration:
            demo_stage = (demo_stage + 1) % 3
            stage_start = current_time
            
            # Update window title
            import pygame
            if pygame.display.get_init():
                new_title = f"SLDK Framework Demo - {stage_names[demo_stage]}"
                pygame.display.set_caption(new_title)
            
            print(f"Stage {demo_stage + 1}: {stage_names[demo_stage]}")
            
            # Show the SLDK API pattern for this stage
            if demo_stage == 0:
                print("  API: create_splash('WE LOVE ADAFRUIT').with_effect(RevealEffect(direction='right'))")
            elif demo_stage == 1:
                print("  API: create_text('SLDK EFFECTS').with_effect(RevealEffect(direction='down'))")
            elif demo_stage == 2:
                print("  API: create_text('REVEAL DEMO').with_effect(RevealCenterEffect(mode='expand'))")
        
        return True
    
    # Run the demo
    device.run(update_callback=update, title="SLDK Reveal Effect Framework Demo")


def main():
    """Main entry point."""
    print("\n" + "=" * 60)
    print("SLDK REVEAL EFFECT - EDUCATIONAL DEMO")
    print("=" * 60)
    print()
    print("This demo teaches you about SLDK's reveal effects by showing:")
    print("1. Manual implementation (what you'll see running)")
    print("2. Framework API (what you should use in real apps)")
    print()
    print("For a working async implementation, see:")
    print("  reveal_effect_async_demo.py")
    print()
    print("Key differences:")
    print("- Manual: Synchronous, character manipulation")
    print("- Framework: Async, declarative effects API")
    print()
    
    reveal_effect_sldk_demo()


if __name__ == "__main__":
    main()