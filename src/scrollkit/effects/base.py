"""Base effect system for SLDK display strategies.

Provides effects that can be applied to display content during rendering.
These effects work with the strategy system and can modify how content
is rendered to create visual enhancements.
"""

from __future__ import annotations

try:
    from abc import ABC, abstractmethod
except ImportError:  # CircuitPython has no 'abc' module
    class ABC:
        pass
    def abstractmethod(func):
        return func
try:
    from typing import Dict, Type, Callable, Any, Optional, List
except ImportError:  # CircuitPython has no 'typing' module
    pass

from ..exceptions import DisplayError

try:
    # CircuitPython compatibility
    import asyncio
except ImportError:
    asyncio = None


class Effect(ABC):
    """Abstract base class for display effects.
    
    Effects modify the rendering process to create visual enhancements
    like reveal animations, transitions, or other visual effects.
    """
    
    def __init__(self, duration: float = 1.0, **kwargs: Any) -> None:
        """Initialize the effect.
        
        Args:
            duration: Effect duration in seconds
            **kwargs: Additional effect parameters
        """
        self.duration: float = duration
        self.params: Dict[str, Any] = kwargs
    
    @abstractmethod
    async def apply(self, display: Any, render_func: Callable[..., Any]) -> None:
        """Apply the effect to the rendering process.
        
        Args:
            display: Display interface to render to
            render_func: Async function that performs the base rendering
        """
        pass
    
    def get_total_duration(self) -> float:
        """Get the total duration this effect adds to rendering.
        
        Returns:
            Duration in seconds
        """
        return self.duration


class EffectRegistry:
    """Registry for display effects using decorator pattern."""
    
    def __init__(self) -> None:
        self._effects: Dict[str, Type[Effect]] = {}
    
    def register(self, name: str, effect_class: Type[Effect]) -> None:
        """Register an effect class with a name.
        
        Args:
            name: Effect name identifier
            effect_class: Effect subclass
        """
        if not issubclass(effect_class, Effect):
            raise ValueError(f"Effect class must inherit from Effect")
        
        self._effects[name] = effect_class
    
    def get_effect(self, name: str) -> Type[Effect]:
        """Get an effect class by name.
        
        Args:
            name: Effect name identifier
            
        Returns:
            Effect class or None if not found
        """
        return self._effects.get(name)
    
    def create_effect(self, name: str, **kwargs: Any) -> Optional[Effect]:
        """Create an effect instance by name.
        
        Args:
            name: Effect name identifier
            **kwargs: Effect parameters
            
        Returns:
            Effect instance or None if not found
        """
        effect_class = self.get_effect(name)
        if effect_class:
            return effect_class(**kwargs)
        return None
    
    def list_effects(self) -> Dict[str, Type[Effect]]:
        """Get all registered effects.
        
        Returns:
            Dictionary of effect name to effect class
        """
        return self._effects.copy()


# Global effect registry
_global_effect_registry = EffectRegistry()


def register_effect(name: str) -> Callable[[Type[Effect]], Type[Effect]]:
    """Decorator to register a display effect.
    
    Args:
        name: Effect name identifier
        
    Example:
        @register_effect('custom_fade')
        class CustomFadeEffect(Effect):
            async def apply(self, display, render_func):
                # Custom fade logic
                await render_func()
    """
    def decorator(effect_class: Type[Effect]) -> Type[Effect]:
        _global_effect_registry.register(name, effect_class)
        return effect_class
    return decorator


def get_effect_registry() -> EffectRegistry:
    """Get the global effect registry.
    
    Returns:
        Global EffectRegistry instance
    """
    return _global_effect_registry


class CompositeEffect(Effect):
    """Effect that combines multiple effects in sequence or parallel."""
    
    def __init__(self, effects: List[Effect], mode: str = 'sequence', **kwargs: Any) -> None:
        """Initialize composite effect.
        
        Args:
            effects: List of Effect instances
            mode: 'sequence' or 'parallel'
            **kwargs: Additional parameters
        """
        # Calculate total duration
        if mode == 'sequence':
            total_duration: float = sum(effect.get_total_duration() for effect in effects)
        else:  # parallel
            total_duration = max(effect.get_total_duration() for effect in effects) if effects else 0
        
        super().__init__(duration=total_duration, **kwargs)
        self.effects: List[Effect] = effects
        self.mode: str = mode
    
    async def apply(self, display: Any, render_func: Callable[..., Any]) -> None:
        """Apply composite effect."""
        if self.mode == 'sequence':
            await self._apply_sequence(display, render_func)
        else:  # parallel
            await self._apply_parallel(display, render_func)
    
    async def _apply_sequence(self, display: Any, render_func: Callable[..., Any]) -> None:
        """Apply effects in sequence."""
        current_render_func = render_func
        
        # Chain effects together
        for effect in reversed(self.effects):
            effect_render_func = current_render_func
            
            async def create_chained_func(eff: Effect, base_func: Callable[..., Any]) -> Callable[..., Any]:
                async def chained() -> None:
                    await eff.apply(display, base_func)
                return chained
            
            current_render_func = await create_chained_func(effect, effect_render_func)
        
        # Execute the final chained function
        await current_render_func()
    
    async def _apply_parallel(self, display: Any, render_func: Callable[..., Any]) -> None:
        """Apply effects in parallel."""
        if not self.effects:
            await render_func()
            return
        
        # For parallel effects, we need to coordinate them
        # This is more complex and may need coordination
        # For now, just apply the first effect
        if self.effects:
            await self.effects[0].apply(display, render_func)
        else:
            await render_func()


# Utility function for content classes
def with_effect_mixin():
    """Mixin to add effect support to content classes.
    
    Returns:
        Class with effect support methods
    """
    class EffectMixin:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            if not hasattr(self, 'effects'):
                self.effects: List[Effect] = []
        
        def with_effect(self, effect: Effect) -> 'EffectMixin':
            """Add an effect to this content.
            
            Args:
                effect: Effect instance to add
                
            Returns:
                Self for method chaining
            """
            if not hasattr(self, 'effects'):
                self.effects = []
            self.effects.append(effect)
            return self
        
        def with_effects(self, effects: List[Effect]) -> 'EffectMixin':
            """Add multiple effects to this content.
            
            Args:
                effects: List of Effect instances
                
            Returns:
                Self for method chaining
            """
            if not hasattr(self, 'effects'):
                self.effects = []
            self.effects.extend(effects)
            return self
    
    return EffectMixin