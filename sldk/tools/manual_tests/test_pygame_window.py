#!/usr/bin/env python3
"""Test pygame window creation directly."""

import pygame
import time
import os

# Force pygame to show window
os.environ['SDL_VIDEO_WINDOW_POS'] = '100,100'

def test_simple_window():
    """Test basic pygame window."""
    print("Initializing pygame...")
    pygame.init()
    
    print("Creating window...")
    screen = pygame.display.set_mode((640, 320))
    pygame.display.set_caption("Test Window - Should Be Visible")
    
    print("Drawing to window...")
    # Fill with red background
    screen.fill((255, 0, 0))
    
    # Draw some shapes
    pygame.draw.circle(screen, (0, 255, 0), (100, 100), 50)
    pygame.draw.rect(screen, (0, 0, 255), (200, 50, 100, 100))
    
    print("Updating display...")
    pygame.display.flip()
    
    print("Window should be visible now. Waiting 5 seconds...")
    
    # Event loop to keep window responsive
    start_time = time.time()
    while time.time() - start_time < 5:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                print("Window closed by user")
                pygame.quit()
                return
        
        time.sleep(0.1)
    
    print("Test complete")
    pygame.quit()

if __name__ == "__main__":
    test_simple_window()