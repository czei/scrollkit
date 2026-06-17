#!/usr/bin/env python3
"""Visual effects demo with actual pygame window you can see."""

import sys
import os
import asyncio
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

# Import pygame directly
import pygame

from sldk.effects import EffectsEngine
from sldk.effects.effects import SparkleEffect, EdgeGlowEffect, RainbowCycleEffect
from sldk.effects.particles import ParticleEngine, Sparkle, RainDrop, Snow, Ember


class VisualEffectsWindow:
    """Visual effects demo with pygame window."""
    
    def __init__(self, width=64, height=32, scale=15):
        """Initialize the visual demo.
        
        Args:
            width: LED matrix width
            height: LED matrix height  
            scale: Pixel scale factor for window
        """
        self.width = width
        self.height = height
        self.scale = scale
        self.window_width = width * scale
        self.window_height = height * scale
        
        # Initialize pygame
        pygame.init()
        self.screen = pygame.display.set_mode((self.window_width, self.window_height))
        pygame.display.set_caption("SLDK Visual Effects Demo")
        
        # Create pixel buffer (simulates LED matrix)
        self.pixel_buffer = [[0x000000 for _ in range(width)] for _ in range(height)]
        
        # Effects engines
        self.effects_engine = EffectsEngine(max_effects=2, target_fps=10)
        self.particle_engine = ParticleEngine(max_particles=8)
        
        # Demo state
        self.demo_stage = 0
        self.stage_start_time = time.time()
        self.stage_duration = 5.0  # 5 seconds per stage
        
        # Define demo stages
        self.stages = [
            ("Sparkle Effect", self.setup_sparkle),
            ("Edge Glow", self.setup_edge_glow), 
            ("Rainbow Cycle", self.setup_rainbow),
            ("Rain Particles", self.setup_rain),
            ("Snow Particles", self.setup_snow),
            ("Fire Embers", self.setup_fire),
            ("Combined Effects", self.setup_combined),
        ]
        
        print("Controls:")
        print("- Press SPACE to advance to next effect")
        print("- Press ESC or close window to exit")
        print("- Each effect runs for 5 seconds automatically")
    
    async def set_pixel(self, x, y, color):
        """Set a pixel in our buffer."""
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixel_buffer[y][x] = color
    
    async def clear(self):
        """Clear the pixel buffer."""
        for y in range(self.height):
            for x in range(self.width):
                self.pixel_buffer[y][x] = 0x000000
    
    def render_to_screen(self):
        """Render pixel buffer to pygame screen."""
        for y in range(self.height):
            for x in range(self.width):
                color = self.pixel_buffer[y][x]
                
                # Convert from 24-bit RGB to pygame color
                r = (color >> 16) & 0xFF
                g = (color >> 8) & 0xFF
                b = color & 0xFF
                pygame_color = (r, g, b)
                
                # Draw scaled pixel
                rect = pygame.Rect(
                    x * self.scale, 
                    y * self.scale, 
                    self.scale, 
                    self.scale
                )
                pygame.draw.rect(self.screen, pygame_color, rect)
        
        pygame.display.flip()
    
    def setup_sparkle(self):
        """Setup sparkle effect demo."""
        self.effects_engine.clear_effects()
        self.particle_engine.clear_particles()
        
        sparkle = SparkleEffect(intensity=5, duration=None)
        self.effects_engine.add_effect(sparkle)
        print("✨ Sparkle Effect: White sparkles on dark blue background")
    
    def setup_edge_glow(self):
        """Setup edge glow effect demo."""
        self.effects_engine.clear_effects()
        self.particle_engine.clear_particles()
        
        glow = EdgeGlowEffect(color=0x00FFFF, duration=None)
        self.effects_engine.add_effect(glow)
        print("💎 Edge Glow: Pulsing cyan glow around edges")
    
    def setup_rainbow(self):
        """Setup rainbow cycle effect demo."""
        self.effects_engine.clear_effects()
        self.particle_engine.clear_particles()
        
        rainbow = RainbowCycleEffect(speed=2.0, duration=None)
        self.effects_engine.add_effect(rainbow)
        print("🌈 Rainbow Cycle: Full display color cycling")
    
    def setup_rain(self):
        """Setup rain particles demo."""
        self.effects_engine.clear_effects()
        self.particle_engine.clear_particles()
        print("💧 Rain Particles: Blue raindrops falling")
    
    def setup_snow(self):
        """Setup snow particles demo."""
        self.effects_engine.clear_effects()
        self.particle_engine.clear_particles()
        print("❄️ Snow Particles: White snowflakes with gentle sway")
    
    def setup_fire(self):
        """Setup fire embers demo."""
        self.effects_engine.clear_effects()
        self.particle_engine.clear_particles()
        print("🔥 Fire Embers: Orange/red particles rising")
    
    def setup_combined(self):
        """Setup combined effects demo."""
        self.effects_engine.clear_effects()
        self.particle_engine.clear_particles()
        
        # Add both sparkle and edge glow
        sparkle = SparkleEffect(intensity=3, duration=None)
        glow = EdgeGlowEffect(color=0xFF00FF, duration=None)  # Purple glow
        self.effects_engine.add_effect(sparkle)
        self.effects_engine.add_effect(glow)
        print("✨💎 Combined Effects: Sparkles + purple edge glow")
    
    async def spawn_particles(self):
        """Spawn particles based on current demo stage."""
        stage_name = self.stages[self.demo_stage][0]
        
        if "Rain" in stage_name:
            # Spawn raindrops from top
            import random
            if random.random() < 0.3:  # 30% chance per frame
                x = random.randint(0, self.width - 1)
                raindrop = RainDrop(x, -2, speed=15.0, color=0x4080FF, lifetime=3.0)
                self.particle_engine.add_particle(raindrop)
        
        elif "Snow" in stage_name:
            # Spawn snowflakes from top
            import random
            if random.random() < 0.2:  # 20% chance per frame
                x = random.randint(0, self.width - 1)
                snowflake = Snow(x, -1, speed=6.0, sway=2.0, lifetime=4.0)
                self.particle_engine.add_particle(snowflake)
        
        elif "Fire" in stage_name:
            # Spawn embers from bottom
            import random
            if random.random() < 0.4:  # 40% chance per frame
                x = random.randint(5, self.width - 6)
                ember = Ember(x, self.height, speed=12.0, drift=3.0, lifetime=2.5)
                self.particle_engine.add_particle(ember)
        
        elif "Combined" in stage_name:
            # Occasional sparkle particles
            import random
            if random.random() < 0.1:  # 10% chance per frame
                x = random.randint(0, self.width - 1)
                y = random.randint(0, self.height - 1)
                sparkle_particle = Sparkle(x, y, color=0xFFFFFF, lifetime=1.5)
                self.particle_engine.add_particle(sparkle_particle)
    
    async def render_background(self):
        """Render appropriate background for current effect."""
        stage_name = self.stages[self.demo_stage][0]
        
        if "Sparkle" in stage_name:
            # Dark blue background
            for y in range(self.height):
                for x in range(self.width):
                    await self.set_pixel(x, y, 0x001133)
        
        elif "Edge Glow" in stage_name:
            # Dark center area
            for y in range(self.height):
                for x in range(self.width):
                    if 2 <= x < self.width - 2 and 2 <= y < self.height - 2:
                        await self.set_pixel(x, y, 0x002020)
                    else:
                        await self.set_pixel(x, y, 0x000000)
        
        elif "Rain" in stage_name:
            # Storm sky
            for y in range(self.height):
                for x in range(self.width):
                    await self.set_pixel(x, y, 0x001144)
        
        elif "Snow" in stage_name:
            # Gray winter sky
            for y in range(self.height):
                for x in range(self.width):
                    await self.set_pixel(x, y, 0x333344)
        
        elif "Fire" in stage_name:
            # Dark background for fire
            for y in range(self.height):
                for x in range(self.width):
                    await self.set_pixel(x, y, 0x110000)
        
        elif "Combined" in stage_name:
            # Dark purple background
            for y in range(self.height):
                for x in range(self.width):
                    await self.set_pixel(x, y, 0x220033)
    
    def advance_stage(self):
        """Advance to next demo stage."""
        self.demo_stage = (self.demo_stage + 1) % len(self.stages)
        self.stage_start_time = time.time()
        
        # Setup new stage
        stage_name, setup_func = self.stages[self.demo_stage]
        setup_func()
    
    async def run(self):
        """Run the visual effects demo."""
        print(f"\n🎨 SLDK Visual Effects Demo")
        print(f"Window: {self.window_width}x{self.window_height} pixels")
        print(f"LED Matrix: {self.width}x{self.height} pixels")
        print()
        
        # Setup first stage
        stage_name, setup_func = self.stages[self.demo_stage]
        setup_func()
        
        clock = pygame.time.Clock()
        running = True
        
        while running:
            current_time = time.time()
            
            # Handle events
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False
                    elif event.key == pygame.K_SPACE:
                        self.advance_stage()
            
            # Auto-advance stages
            if current_time - self.stage_start_time > self.stage_duration:
                self.advance_stage()
            
            # Clear display
            await self.clear()
            
            # Render background
            await self.render_background()
            
            # Spawn particles if needed
            await self.spawn_particles()
            
            # Update effects and particles
            await self.effects_engine.update(self)
            await self.particle_engine.update(self)
            
            # Render to screen
            self.render_to_screen()
            
            # Show current stage info
            stage_name = self.stages[self.demo_stage][0]
            time_left = self.stage_duration - (current_time - self.stage_start_time)
            particle_count = self.particle_engine.get_particle_count()
            effect_count = len(self.effects_engine.active_effects)
            
            pygame.display.set_caption(
                f"SLDK Effects Demo - {stage_name} "
                f"(Effects: {effect_count}, Particles: {particle_count}, "
                f"Time: {time_left:.1f}s)"
            )
            
            # Control frame rate
            clock.tick(10)  # 10 FPS
            await asyncio.sleep(0.001)  # Yield control
        
        pygame.quit()


async def main():
    """Run the visual effects demo."""
    print("🎨 SLDK Visual Effects Demo with Pygame Window")
    print("=" * 50)
    
    try:
        demo = VisualEffectsWindow(width=64, height=32, scale=12)
        await demo.run()
    except Exception as e:
        print(f"Demo error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())