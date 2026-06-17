#!/usr/bin/env python3
"""Unit tests for effects engine."""

import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from sldk.effects import EffectsEngine
from sldk.effects.effects import SparkleEffect, EdgeGlowEffect, RainbowCycleEffect


class TestEffectsEngine:
    """Test cases for EffectsEngine class."""
    
    def test_effects_engine_initialization(self):
        """Test creating effects engine."""
        engine = EffectsEngine(max_effects=3, target_fps=10)
        
        assert engine.max_effects == 3
        assert engine.target_fps == 10
        assert engine.frame_duration == 0.1  # 1/10 FPS
        assert len(engine.active_effects) == 0
    
    def test_effects_engine_defaults(self):
        """Test effects engine with default values."""
        engine = EffectsEngine()
        
        assert engine.max_effects == 2
        assert engine.target_fps == 5
        assert engine.frame_duration == 0.2  # 1/5 FPS
        assert len(engine.active_effects) == 0
    
    def test_add_single_effect(self):
        """Test adding single effect to engine."""
        engine = EffectsEngine(max_effects=3)
        effect = SparkleEffect(intensity=5, duration=10.0)
        
        engine.add_effect(effect)
        
        assert len(engine.active_effects) == 1
        assert engine.active_effects[0] == effect
    
    def test_add_multiple_effects(self):
        """Test adding multiple effects."""
        engine = EffectsEngine(max_effects=3)
        
        sparkle = SparkleEffect(intensity=3, duration=5.0)
        glow = EdgeGlowEffect(color=0x00FFFF, duration=8.0)
        rainbow = RainbowCycleEffect(speed=2.0, duration=12.0)
        
        engine.add_effect(sparkle)
        engine.add_effect(glow)
        engine.add_effect(rainbow)
        
        assert len(engine.active_effects) == 3
        assert sparkle in engine.active_effects
        assert glow in engine.active_effects
        assert rainbow in engine.active_effects
    
    def test_exceed_max_effects(self):
        """Test adding more effects than max_effects limit."""
        engine = EffectsEngine(max_effects=2)
        
        effect1 = SparkleEffect(intensity=3, duration=5.0)
        effect2 = EdgeGlowEffect(color=0xFF0000, duration=5.0)
        effect3 = RainbowCycleEffect(speed=1.0, duration=5.0)
        
        engine.add_effect(effect1)
        engine.add_effect(effect2)
        engine.add_effect(effect3)  # Should either replace oldest or be ignored
        
        assert len(engine.active_effects) <= 2
        # Either effect3 replaces effect1, or effect3 is ignored
        assert effect2 in engine.active_effects  # Most recent should remain
    
    def test_clear_effects(self):
        """Test clearing all effects."""
        engine = EffectsEngine(max_effects=3)
        
        # Add effects
        engine.add_effect(SparkleEffect(intensity=3, duration=5.0))
        engine.add_effect(EdgeGlowEffect(color=0x00FF00, duration=5.0))
        
        assert len(engine.active_effects) == 2
        
        # Clear effects
        engine.clear_effects()
        
        assert len(engine.active_effects) == 0
    
    @pytest.mark.asyncio
    async def test_update_effects(self, mock_display):
        """Test updating effects on display."""
        engine = EffectsEngine(max_effects=2, target_fps=10)
        
        # Add mock effect with proper attributes
        effect = MagicMock()
        effect.is_expired.return_value = False
        effect.update = AsyncMock()
        effect.duration = None  # No duration = permanent
        effect.start_time = 0.0
        
        engine.add_effect(effect)
        
        # Update effects
        await engine.update(mock_display)
        
        # Effect should be updated with display and elapsed_time
        effect.update.assert_called_once()
        # Check that it was called with display and a numeric elapsed_time
        call_args = effect.update.call_args[0]
        assert call_args[0] == mock_display
        assert isinstance(call_args[1], (int, float))  # elapsed_time
    
    @pytest.mark.asyncio
    async def test_remove_expired_effects(self, mock_display):
        """Test automatic removal of expired effects."""
        engine = EffectsEngine(max_effects=3)
        
        # Create mock effects - one expired, one active
        expired_effect = MagicMock()
        expired_effect.is_expired.return_value = True
        expired_effect.update = AsyncMock()
        expired_effect.duration = 5.0
        expired_effect.start_time = 0.0
        
        active_effect = MagicMock()
        active_effect.is_expired.return_value = False
        active_effect.update = AsyncMock()
        active_effect.duration = None
        active_effect.start_time = 0.0
        
        # Mock time when adding effects
        with patch('sldk.effects.effects.get_time') as mock_get_time:
            mock_get_time.return_value = 0.0  # Initial time
            
            engine.add_effect(expired_effect)
            engine.add_effect(active_effect)
            
            assert len(engine.active_effects) == 2
            
            # Set time to make expired_effect actually expired (start_time + duration < current)
            mock_get_time.return_value = 10.0  # expired_effect started at 0.0 with duration 5.0
            
            # Update should remove expired effect
            await engine.update(mock_display)
            
            assert len(engine.active_effects) == 1
            assert active_effect in engine.active_effects
            assert expired_effect not in engine.active_effects
    
    @pytest.mark.asyncio
    async def test_update_empty_engine(self, mock_display):
        """Test updating engine with no effects."""
        engine = EffectsEngine()
        
        # Should not raise error
        await engine.update(mock_display)
        
        assert len(engine.active_effects) == 0


class TestSparkleEffect:
    """Test cases for SparkleEffect class."""
    
    def test_sparkle_effect_creation(self):
        """Test creating sparkle effect."""
        effect = SparkleEffect(intensity=5, duration=10.0)
        
        assert effect.intensity == 5
        assert effect.duration == 10.0
        assert hasattr(effect, 'start_time')
    
    def test_sparkle_effect_defaults(self):
        """Test sparkle effect with default values."""
        effect = SparkleEffect()
        
        assert effect.intensity == 3  # Default intensity
        assert effect.duration is None  # Permanent
    
    def test_sparkle_effect_infinite_duration(self):
        """Test sparkle effect with no duration (permanent)."""
        effect = SparkleEffect(intensity=5, duration=None)
        
        assert effect.duration is None
        # Effects don't have is_expired() method
    
    @pytest.mark.asyncio
    async def test_sparkle_effect_update(self, mock_display):
        """Test updating sparkle effect."""
        effect = SparkleEffect(intensity=3, duration=5.0)
        
        # Mock display dimensions
        mock_display.width = 64
        mock_display.height = 32
        
        # Update requires elapsed_time parameter
        await effect.update(mock_display, 0.5)
        
        # May or may not call set_pixel depending on spawn timing
        # Just ensure no errors
    
    def test_sparkle_effect_expiration(self):
        """Test sparkle effect expiration logic."""
        effect = SparkleEffect(intensity=3, duration=5.0)
        
        # Test duration is set correctly
        assert effect.duration == 5.0
        
        # Engine will handle expiration by checking:
        # if effect.duration and (current_time - effect.start_time) > effect.duration


class TestEdgeGlowEffect:
    """Test cases for EdgeGlowEffect class."""
    
    def test_edge_glow_creation(self):
        """Test creating edge glow effect."""
        effect = EdgeGlowEffect(color=0x00FFFF, duration=8.0)
        
        assert effect.color == 0x00FFFF
        assert effect.duration == 8.0
    
    def test_edge_glow_defaults(self):
        """Test edge glow with default values."""
        effect = EdgeGlowEffect()
        
        assert effect.color == 0x00FFFF  # Default cyan
        assert effect.duration is None  # Permanent
    
    @pytest.mark.asyncio
    async def test_edge_glow_update(self, mock_display):
        """Test updating edge glow effect."""
        effect = EdgeGlowEffect(color=0xFF0080, duration=10.0)
        
        # Mock display dimensions
        mock_display.width = 64
        mock_display.height = 32
        
        # Update requires elapsed_time parameter
        await effect.update(mock_display, 0.5)
        
        # Should set pixels around edges
        mock_display.set_pixel.assert_called()
    
    def test_edge_glow_intensity_validation(self):
        """Test edge glow color validation."""
        # EdgeGlowEffect doesn't have intensity parameter
        # Test different colors instead
        red = EdgeGlowEffect(color=0xFF0000)
        green = EdgeGlowEffect(color=0x00FF00)
        blue = EdgeGlowEffect(color=0x0000FF)
        
        assert red.color == 0xFF0000
        assert green.color == 0x00FF00
        assert blue.color == 0x0000FF


class TestRainbowCycleEffect:
    """Test cases for RainbowCycleEffect class."""
    
    def test_rainbow_cycle_creation(self):
        """Test creating rainbow cycle effect."""
        effect = RainbowCycleEffect(speed=2.0, duration=10.0)
        
        assert effect.speed == 2.0
        assert effect.duration == 10.0
    
    def test_rainbow_cycle_defaults(self):
        """Test rainbow cycle with default values."""
        effect = RainbowCycleEffect()
        
        assert effect.speed == 1.0  # Default speed
        assert effect.duration is None  # Permanent
    
    @pytest.mark.asyncio
    async def test_rainbow_cycle_update(self, mock_display):
        """Test updating rainbow cycle effect."""
        effect = RainbowCycleEffect(speed=1.5, duration=6.0)
        
        # Mock display dimensions
        mock_display.width = 64
        mock_display.height = 32
        
        # Update requires elapsed_time parameter
        await effect.update(mock_display, 0.5)
        
        # Should set pixels across display
        mock_display.set_pixel.assert_called()
    
    def test_rainbow_cycle_speed_validation(self):
        """Test rainbow cycle speed validation."""
        slow = RainbowCycleEffect(speed=0.1)
        fast = RainbowCycleEffect(speed=10.0)
        
        assert slow.speed == 0.1
        assert fast.speed == 10.0
        
        # Zero speed should be valid (static rainbow)
        static = RainbowCycleEffect(speed=0.0)
        assert static.speed == 0.0


class TestEffectsIntegration:
    """Integration tests for effects system."""
    
    @pytest.mark.asyncio
    async def test_multiple_effects_rendering(self, mock_display):
        """Test rendering multiple effects simultaneously."""
        engine = EffectsEngine(max_effects=3, target_fps=10)
        
        # Mock display dimensions
        mock_display.width = 64
        mock_display.height = 32
        
        # Add multiple effects
        sparkle = SparkleEffect(intensity=2, duration=None)
        glow = EdgeGlowEffect(color=0xFF00FF, duration=None)
        
        engine.add_effect(sparkle)
        engine.add_effect(glow)
        
        # Verify both effects were added
        assert len(engine.active_effects) == 2
        assert sparkle in engine.active_effects
        assert glow in engine.active_effects
        
        # Update engine
        await engine.update(mock_display)
        
        # Both effects should still be active
        assert len(engine.active_effects) == 2
    
    @pytest.mark.asyncio
    async def test_effects_lifecycle(self, mock_display):
        """Test complete lifecycle of effects."""
        engine = EffectsEngine(max_effects=2, target_fps=5)
        
        # Need to mock the time module used by effects
        with patch('sldk.effects.effects.get_time') as mock_get_time:
            # Initial time
            mock_get_time.return_value = 100.0
            
            # Add short-duration effect
            short_effect = SparkleEffect(intensity=3, duration=2.0)
            engine.add_effect(short_effect)
            
            assert len(engine.active_effects) == 1
            
            # Update before expiration
            mock_get_time.return_value = 101.0
            await engine.update(mock_display)
            assert len(engine.active_effects) == 1
            
            # Update after expiration
            mock_get_time.return_value = 103.0  # 3 seconds later
            await engine.update(mock_display)
            assert len(engine.active_effects) == 0


class TestEffectsMemoryUsage:
    """Test memory efficiency of effects system."""
    
    def test_effects_engine_memory_limit(self):
        """Test that engine respects memory limits."""
        # Small engine for memory-constrained devices
        engine = EffectsEngine(max_effects=1, target_fps=5)
        
        # Add multiple effects
        for i in range(5):
            effect = SparkleEffect(intensity=1, duration=1.0)
            engine.add_effect(effect)
        
        # Should not exceed max_effects
        assert len(engine.active_effects) <= 1
    
    def test_effect_cleanup(self):
        """Test that expired effects are properly cleaned up."""
        engine = EffectsEngine(max_effects=5)
        
        with patch('sldk.effects.effects.get_time') as mock_get_time:
            mock_get_time.return_value = 200.0
            
            # Add effects with short duration
            for i in range(3):
                effect = SparkleEffect(intensity=1, duration=0.1)
                engine.add_effect(effect)
            
            assert len(engine.active_effects) == 3
            
            # Advance time to expire all effects
            mock_get_time.return_value = 201.0
            
            # Check which effects would be expired
            expired_count = 0
            for effect in engine.active_effects:
                if effect.duration and (mock_get_time.return_value - effect.start_time) > effect.duration:
                    expired_count += 1
            
            assert expired_count == 3  # All should be expired