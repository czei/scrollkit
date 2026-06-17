#!/usr/bin/env python3
"""Unit tests for particle systems."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from sldk.effects.particles import ParticleEngine, Sparkle, RainDrop, Snow, Ember


class TestParticleEngine:
    """Test cases for ParticleEngine class."""
    
    def test_particle_engine_initialization(self):
        """Test creating particle engine."""
        engine = ParticleEngine(max_particles=10)
        
        assert engine.max_particles == 10
        assert len(engine.particles) == 0
        assert engine.get_particle_count() == 0
    
    def test_particle_engine_defaults(self):
        """Test particle engine with default values."""
        engine = ParticleEngine()
        
        assert engine.max_particles == 8  # Default for ESP32
        assert len(engine.particles) == 0
    
    def test_add_single_particle(self):
        """Test adding single particle."""
        engine = ParticleEngine(max_particles=5)
        particle = Sparkle(x=10, y=15, color=0xFFFFFF, lifetime=2.0)
        
        engine.add_particle(particle)
        
        assert engine.get_particle_count() == 1
        assert particle in engine.particles
    
    def test_add_multiple_particles(self):
        """Test adding multiple particles."""
        engine = ParticleEngine(max_particles=5)
        
        sparkle = Sparkle(x=5, y=5, color=0xFFFFFF, lifetime=1.0)
        raindrop = RainDrop(x=10, y=0, speed=20.0, color=0x0080FF, lifetime=3.0)
        snow = Snow(x=15, y=0, speed=8.0, sway=2.0, lifetime=4.0)
        
        engine.add_particle(sparkle)
        engine.add_particle(raindrop)
        engine.add_particle(snow)
        
        assert engine.get_particle_count() == 3
        assert sparkle in engine.particles
        assert raindrop in engine.particles
        assert snow in engine.particles
    
    def test_exceed_max_particles(self):
        """Test adding more particles than max_particles limit."""
        engine = ParticleEngine(max_particles=2)
        
        p1 = Sparkle(x=0, y=0, lifetime=1.0)
        p2 = Sparkle(x=5, y=5, lifetime=1.0)
        p3 = Sparkle(x=10, y=10, lifetime=1.0)
        
        engine.add_particle(p1)
        engine.add_particle(p2)
        engine.add_particle(p3)  # Should either replace oldest or be ignored
        
        assert engine.get_particle_count() <= 2
    
    def test_clear_particles(self):
        """Test clearing all particles."""
        engine = ParticleEngine(max_particles=5)
        
        # Add particles
        engine.add_particle(Sparkle(x=0, y=0, lifetime=1.0))
        engine.add_particle(RainDrop(x=10, y=5, speed=15.0, lifetime=2.0))
        
        assert engine.get_particle_count() == 2
        
        # Clear particles
        engine.clear_particles()
        
        assert engine.get_particle_count() == 0
        assert len(engine.particles) == 0
    
    @pytest.mark.asyncio
    async def test_update_particles(self, mock_display):
        """Test updating all particles."""
        engine = ParticleEngine(max_particles=3)
        
        # Add mock particles with proper methods
        p1 = MagicMock()
        p1.is_dead.return_value = False
        p1.update = MagicMock()  # Not async
        p1.render = AsyncMock()
        p1.spawn_time = 0.0
        
        p2 = MagicMock()
        p2.is_dead.return_value = False
        p2.update = MagicMock()  # Not async
        p2.render = AsyncMock()
        p2.spawn_time = 0.0
        
        engine.add_particle(p1)
        engine.add_particle(p2)
        
        # Update particles
        await engine.update(mock_display)
        
        # Both particles should be updated with elapsed time
        p1.update.assert_called_once()
        p2.update.assert_called_once()
        
        # Both should be rendered
        p1.render.assert_called_once_with(mock_display)
        p2.render.assert_called_once_with(mock_display)
    
    @pytest.mark.asyncio
    async def test_remove_dead_particles(self, mock_display):
        """Test automatic removal of dead particles."""
        engine = ParticleEngine(max_particles=3)
        
        # Create mock particles - one dead, one alive
        dead_particle = MagicMock()
        dead_particle.is_dead.return_value = True
        dead_particle.update = MagicMock()
        dead_particle.render = AsyncMock()
        dead_particle.spawn_time = 0.0
        
        alive_particle = MagicMock()
        alive_particle.is_dead.return_value = False
        alive_particle.update = MagicMock()
        alive_particle.render = AsyncMock()
        alive_particle.spawn_time = 0.0
        
        engine.add_particle(dead_particle)
        engine.add_particle(alive_particle)
        
        assert engine.get_particle_count() == 2
        
        # Update should remove dead particle
        await engine.update(mock_display)
        
        assert engine.get_particle_count() == 1
        assert alive_particle in engine.particles
        assert dead_particle not in engine.particles


class TestSparkleParticle:
    """Test cases for Sparkle particle class."""
    
    def test_sparkle_creation(self):
        """Test creating sparkle particle."""
        sparkle = Sparkle(x=20, y=10, color=0xFF00FF, lifetime=1.5)
        
        assert sparkle.x == 20
        assert sparkle.y == 10
        assert sparkle.color == 0xFF00FF
        assert sparkle.lifetime == 1.5
        assert hasattr(sparkle, 'spawn_time')
    
    def test_sparkle_defaults(self):
        """Test sparkle with default values."""
        sparkle = Sparkle(x=0, y=0)
        
        assert sparkle.x == 0
        assert sparkle.y == 0
        assert sparkle.color == 0xFFFFFF  # Default white
        assert sparkle.lifetime == 1.0  # Default lifetime
    
    def test_sparkle_lifetime(self):
        """Test sparkle lifetime and expiration."""
        sparkle = Sparkle(x=0, y=0, lifetime=2.0)
        
        # Just spawned - should not be dead
        assert not sparkle.is_dead(0.0)
        
        # Within lifetime
        assert not sparkle.is_dead(1.5)
        
        # Past lifetime - should be dead
        assert sparkle.is_dead(2.5)
    
    @pytest.mark.asyncio
    async def test_sparkle_update(self, mock_display):
        """Test updating sparkle particle."""
        sparkle = Sparkle(x=15, y=25, color=0x00FFFF, lifetime=2.0)
        
        # Mock display dimensions
        mock_display.width = 64
        mock_display.height = 32
        
        # Set spawn time to have a known reference
        sparkle.spawn_time = 0.0
        
        # Mock time for render
        with patch('sldk.effects.particles.get_time') as mock_get_time:
            mock_get_time.return_value = 0.5  # Half second elapsed
            
            await sparkle.render(mock_display)
            
            # Should render sparkle at position
            mock_display.set_pixel.assert_called()
            # Check if called with correct position
            call_args = mock_display.set_pixel.call_args
            if call_args:
                x, y, color = call_args[0]
                assert x == 15
                assert y == 25


class TestRainDropParticle:
    """Test cases for RainDrop particle class."""
    
    def test_raindrop_creation(self):
        """Test creating raindrop particle."""
        drop = RainDrop(x=30, y=5, speed=25.0, color=0x4080FF, lifetime=3.0)
        
        assert drop.x == 30
        assert drop.y == 5  # Current y position
        assert drop.start_y == 5  # Starting y position
        assert drop.speed == 25.0
        assert drop.color == 0x4080FF
        assert drop.lifetime == 3.0
    
    def test_raindrop_defaults(self):
        """Test raindrop with default values."""
        drop = RainDrop(x=0, y=0)
        
        assert drop.x == 0
        assert drop.start_y == 0
        assert drop.speed == 10.0  # Default speed
        assert drop.color == 0x0080FF  # Default blue
        assert drop.lifetime == 3.0  # Default lifetime
    
    def test_raindrop_movement(self):
        """Test raindrop falling movement."""
        drop = RainDrop(x=10, y=0, speed=30.0, lifetime=5.0)
        
        # Update with different elapsed times
        initial_y = drop.y
        
        drop.update(0.5)  # 0.5 seconds elapsed
        first_y = drop.y
        
        drop.update(1.0)  # 1.0 seconds elapsed
        second_y = drop.y
        
        # Y position should increase (falling down)
        assert first_y > initial_y
        assert second_y > first_y
    
    def test_raindrop_off_screen_death(self):
        """Test raindrop dies when falling off screen."""
        drop = RainDrop(x=10, y=0, speed=50.0, lifetime=10.0)
        
        # Position raindrop below screen (assuming 32-pixel height)
        drop.y = 35  # Below 32-pixel height
        
        # Check if dead - is_dead checks if y >= 32
        assert drop.is_dead(0.1)  # Any elapsed time


class TestSnowParticle:
    """Test cases for Snow particle class."""
    
    def test_snow_creation(self):
        """Test creating snow particle."""
        snow = Snow(x=25, y=2, speed=10.0, sway=3.0, lifetime=4.0)
        
        assert snow.x == 25
        assert snow.start_y == 2
        assert snow.speed == 10.0
        assert snow.sway == 3.0
        assert snow.lifetime == 4.0
    
    def test_snow_defaults(self):
        """Test snow with default values."""
        snow = Snow(x=0, y=0)
        
        assert snow.x == 0
        assert snow.start_y == 0
        assert snow.speed == 3.0  # Default speed
        assert snow.sway == 1.0  # Default sway
        # Snow doesn't have a color attribute - it's always white
        assert snow.lifetime == 5.0  # Default lifetime
    
    def test_snow_movement_with_sway(self):
        """Test snow movement with horizontal sway."""
        snow = Snow(x=20, y=0, speed=15.0, sway=4.0, lifetime=5.0)
        
        initial_x = snow.x
        initial_y = snow.y
        
        # Update with elapsed time
        snow.update(0.5)
        first_x, first_y = snow.x, snow.y
        
        snow.update(1.0)
        second_x, second_y = snow.x, snow.y
        
        # Y should increase (falling)
        assert first_y > initial_y
        assert second_y > first_y
        
        # X should change due to sway (might increase or decrease)
        assert first_x != initial_x or second_x != first_x
    
    def test_snow_sway_pattern(self):
        """Test snow sway creates gentle side-to-side motion."""
        snow = Snow(x=15, y=0, speed=8.0, sway=2.0, lifetime=10.0)
        
        x_positions = []
        
        # Simulate multiple updates with different elapsed times
        for i in range(10):
            elapsed = i * 0.2  # 0.2 second intervals
            snow.update(elapsed)
            x_positions.append(snow.x)
        
        # Should see variation in X positions due to sway
        assert len(set(x_positions)) > 1  # X should change


class TestEmberParticle:
    """Test cases for Ember particle class."""
    
    def test_ember_creation(self):
        """Test creating ember particle."""
        ember = Ember(x=40, y=30, speed=18.0, drift=2.5, lifetime=2.5)
        
        assert ember.x == 40
        assert ember.start_y == 30
        assert ember.speed == 18.0
        assert ember.drift == 2.5
        assert ember.lifetime == 2.5
    
    def test_ember_defaults(self):
        """Test ember with default values."""
        ember = Ember(x=0, y=32)  # Start at bottom
        
        assert ember.x == 0
        assert ember.start_y == 32
        assert ember.speed == 5.0  # Default speed
        assert ember.drift == 2.0  # Default drift
        assert ember.lifetime == 2.0  # Default lifetime
    
    def test_ember_color_variation(self):
        """Test ember has appropriate fire colors."""
        ember = Ember(x=10, y=20, lifetime=3.0)
        
        # Ember has a colors list attribute
        assert hasattr(ember, 'colors')
        assert len(ember.colors) > 0
        
        # Check that colors are fire-like (red, orange, yellow)
        for color in ember.colors:
            # Extract RGB components
            r = (color >> 16) & 0xFF
            g = (color >> 8) & 0xFF
            b = color & 0xFF
            
            # Fire colors should have significant red component
            assert r >= 0xFF  # Full red
            
            # Blue should be zero for fire colors
            assert b == 0
    
    def test_ember_upward_movement(self):
        """Test ember moves upward like rising fire."""
        ember = Ember(x=15, y=25, speed=20.0, lifetime=5.0)
        
        initial_y = ember.y
        
        ember.update(0.5)
        first_y = ember.y
        
        ember.update(1.0)
        second_y = ember.y
        
        # Y should decrease (moving up)
        assert first_y < initial_y
        assert second_y < first_y
    
    def test_ember_off_screen_death(self):
        """Test ember dies when rising off screen."""
        ember = Ember(x=10, y=25, speed=50.0, lifetime=10.0)
        
        # Simulate ember above screen
        ember.y = -5  # Above screen
        
        assert ember.is_dead(0.1)  # Any elapsed time


class TestParticleIntegration:
    """Integration tests for particle systems."""
    
    @pytest.mark.asyncio
    async def test_mixed_particle_types(self, mock_display):
        """Test engine with different particle types."""
        engine = ParticleEngine(max_particles=6)
        
        # Mock display dimensions
        mock_display.width = 64
        mock_display.height = 32
        
        # Add different particle types
        sparkle = Sparkle(x=5, y=5, lifetime=2.0)
        rain = RainDrop(x=15, y=0, speed=25.0, lifetime=3.0)
        snow = Snow(x=25, y=0, speed=8.0, sway=2.0, lifetime=4.0)
        ember = Ember(x=35, y=30, speed=18.0, lifetime=2.5)
        
        engine.add_particle(sparkle)
        engine.add_particle(rain)
        engine.add_particle(snow)
        engine.add_particle(ember)
        
        assert engine.get_particle_count() == 4
        
        # Update all particles
        await engine.update(mock_display)
        
        # Particles should be updated (may or may not render depending on their state)
        assert engine.get_particle_count() == 4
    
    @pytest.mark.asyncio
    async def test_particle_lifecycle(self, mock_display):
        """Test complete particle lifecycle."""
        engine = ParticleEngine(max_particles=3)
        
        # Mock display dimensions
        mock_display.width = 64
        mock_display.height = 32
        
        with patch('sldk.effects.particles.get_time') as mock_get_time:
            mock_get_time.return_value = 300.0
            
            # Add short-lived particle
            short_particle = Sparkle(x=10, y=10, lifetime=1.0)
            engine.add_particle(short_particle)
            
            assert engine.get_particle_count() == 1
            
            # Update before expiration
            mock_get_time.return_value = 300.5
            await engine.update(mock_display)
            assert engine.get_particle_count() == 1
            
            # Update after expiration
            mock_get_time.return_value = 302.0
            await engine.update(mock_display)
            assert engine.get_particle_count() == 0
    
    def test_particle_memory_efficiency(self):
        """Test particle system respects memory constraints."""
        # Very small engine for memory testing
        engine = ParticleEngine(max_particles=2)
        
        # Try to add many particles
        for i in range(10):
            particle = Sparkle(x=i, y=i, lifetime=1.0)
            engine.add_particle(particle)
        
        # Should not exceed max_particles
        assert engine.get_particle_count() <= 2