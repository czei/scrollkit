"""Display strategy system for SLDK.

Provides the foundation for extensible display strategies following the 
Strategy pattern. Applications can register custom strategies to handle
different types of display content.
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
    from typing import Any, Dict, Optional, Type
except ImportError:  # CircuitPython has no 'typing' module
    pass
import time

from ..exceptions import ContentError, ValidationError

try:
    # CircuitPython compatibility
    import asyncio
except ImportError:
    asyncio = None


class Priority:
    """Priority levels for display items."""
    IDLE: int = 0
    LOW: int = 1
    NORMAL: int = 2
    HIGH: int = 3
    URGENT: int = 4
    SYSTEM: int = 5


class DisplayStrategy(ABC):
    """Abstract base class for all display strategies.
    
    Display strategies define how specific types of content should be
    rendered on the display. Each strategy handles one type of content
    (e.g., text, graphs, animations) and implements the rendering logic.
    """
    
    @abstractmethod
    async def render(self, display, data: Dict[str, Any]) -> None:
        """Render the content to the display.
        
        Args:
            display: Display interface to render to
            data: Dictionary containing the data to render
        """
        pass
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate that the data is suitable for this strategy.
        
        Args:
            data: Dictionary containing the data to validate
            
        Returns:
            True if data is valid, False otherwise
        """
        return True
    
    def get_render_duration(self, data: Dict[str, Any]) -> Optional[float]:
        """Get the recommended rendering duration for this content.
        
        Args:
            data: Dictionary containing the data
            
        Returns:
            Duration in seconds, or None for default duration
        """
        return None


class StrategyRegistry:
    """Registry for display strategies using decorator pattern."""
    
    def __init__(self):
        self._strategies: Dict[str, Type[DisplayStrategy]] = {}
    
    def register(self, name: str, strategy_class: Type[DisplayStrategy]) -> None:
        """Register a strategy class with a name.
        
        Args:
            name: Strategy name identifier
            strategy_class: DisplayStrategy subclass
        """
        if not issubclass(strategy_class, DisplayStrategy):
            raise ValueError(f"Strategy class must inherit from DisplayStrategy")
        
        self._strategies[name] = strategy_class
    
    def get_strategy(self, name: str) -> Optional[Type[DisplayStrategy]]:
        """Get a strategy class by name.
        
        Args:
            name: Strategy name identifier
            
        Returns:
            Strategy class or None if not found
        """
        return self._strategies.get(name)
    
    def list_strategies(self) -> Dict[str, Type[DisplayStrategy]]:
        """Get all registered strategies.
        
        Returns:
            Dictionary of strategy name to strategy class
        """
        return self._strategies.copy()
    
    def create_strategy(self, name: str) -> Optional[DisplayStrategy]:
        """Create an instance of a strategy by name.
        
        Args:
            name: Strategy name identifier
            
        Returns:
            Strategy instance or None if not found
        """
        strategy_class = self.get_strategy(name)
        if strategy_class:
            return strategy_class()
        return None


# Global strategy registry
_global_registry = StrategyRegistry()


def register_strategy(name: str):
    """Decorator to register a display strategy.
    
    Args:
        name: Strategy name identifier
        
    Example:
        @register_strategy('custom_text')
        class CustomTextStrategy(DisplayStrategy):
            async def render(self, display, data):
                await display.draw_text(data['text'])
    """
    def decorator(strategy_class: Type[DisplayStrategy]):
        _global_registry.register(name, strategy_class)
        return strategy_class
    return decorator


def get_strategy_registry() -> StrategyRegistry:
    """Get the global strategy registry.
    
    Returns:
        Global StrategyRegistry instance
    """
    return _global_registry


class DisplayItem:
    """Container for display content with metadata.
    
    DisplayItems combine data with rendering strategy, priority, timing,
    and effects information. They represent a single item in the display queue.
    """
    
    def __init__(self, 
                 strategy_name: str, 
                 data: Dict[str, Any], 
                 priority: int = Priority.NORMAL,
                 duration: Optional[float] = None,
                 expires_at: Optional[float] = None):
        """Initialize a display item.
        
        Args:
            strategy_name: Name of the strategy to use for rendering
            data: Data dictionary for the strategy
            priority: Priority level (see Priority class)
            duration: How long to display (seconds), None for default
            expires_at: Unix timestamp when item expires, None for no expiration
        """
        self.strategy_name = strategy_name
        self.data = data
        self.priority = priority
        self.duration = duration
        self.expires_at = expires_at
        self.effects = []
        self.created_at = time.time()
        self.metadata = {}
    
    def add_effect(self, effect) -> 'DisplayItem':
        """Add an effect to this display item.
        
        Args:
            effect: Effect instance to apply during rendering
            
        Returns:
            Self for method chaining
        """
        self.effects.append(effect)
        return self
    
    def with_effect(self, effect) -> 'DisplayItem':
        """Add an effect to this display item (alias for add_effect).
        
        This method provides the fluent interface pattern requested:
        DisplayItem(...).with_effect(RevealEffect())
        
        Args:
            effect: Effect instance to apply during rendering
            
        Returns:
            Self for method chaining
        """
        return self.add_effect(effect)
    
    def is_expired(self) -> bool:
        """Check if this item has expired.
        
        Returns:
            True if item is expired, False otherwise
        """
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at
    
    def set_metadata(self, key: str, value: Any) -> 'DisplayItem':
        """Set metadata for this item.
        
        Args:
            key: Metadata key
            value: Metadata value
            
        Returns:
            Self for method chaining
        """
        self.metadata[key] = value
        return self
    
    def get_metadata(self, key: str, default: Any = None) -> Any:
        """Get metadata for this item.
        
        Args:
            key: Metadata key
            default: Default value if key not found
            
        Returns:
            Metadata value or default
        """
        return self.metadata.get(key, default)
    
    def __lt__(self, other: 'DisplayItem') -> bool:
        """Compare items for priority queue ordering.
        
        Higher priority items sort first, then by creation time.
        """
        if self.priority != other.priority:
            return self.priority > other.priority  # Higher priority first
        return self.created_at < other.created_at  # Earlier items first


# Built-in strategies that should be part of SLDK core
@register_strategy('static_text')
class StaticTextStrategy(DisplayStrategy):
    """Strategy for displaying static text."""
    
    async def render(self, display, data: Dict[str, Any]) -> None:
        """Render static text to display."""
        text = data.get('text', '')
        x = data.get('x', 0)
        y = data.get('y', 10)
        color = data.get('color', 0xFFFFFF)
        font = data.get('font', None)
        
        await display.draw_text(text, x=x, y=y, color=color, font=font)
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate static text data."""
        return 'text' in data


@register_strategy('scrolling_text')
class ScrollingTextStrategy(DisplayStrategy):
    """Strategy for displaying scrolling text."""
    
    async def render(self, display, data: Dict[str, Any]) -> None:
        """Render scrolling text to display."""
        text = data.get('text', '')
        y = data.get('y', 10)
        color = data.get('color', 0xFFFFFF)
        speed = data.get('speed', 0.05)
        
        # Use display's scroll_text method if available
        if hasattr(display, 'scroll_text'):
            await display.scroll_text(text, y=y, color=color, speed=speed)
        else:
            # Fallback to static text
            await display.draw_text(text, x=0, y=y, color=color)
    
    def validate_data(self, data: Dict[str, Any]) -> bool:
        """Validate scrolling text data."""
        return 'text' in data
    
    def get_render_duration(self, data: Dict[str, Any]) -> Optional[float]:
        """Calculate duration based on text length and scroll speed."""
        text = data.get('text', '')
        speed = data.get('speed', 0.05)
        # Rough estimate: 6 pixels per character, scroll speed in seconds per pixel
        estimated_duration = len(text) * 6 * speed + 2.0  # Extra 2 seconds
        return estimated_duration