# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Display manager for SLDK.

Provides the core orchestrator that coordinates display queue processing,
strategy execution, and display management.
"""

from __future__ import annotations

import time
try:
    from typing import Any, Dict, Optional
except ImportError:  # CircuitPython has no 'typing' module
    pass
from .strategy import Priority, get_strategy_registry
from .queue import DisplayQueue, DisplayItem
from .interface import DisplayInterface
from ..exceptions import ContentError, DisplayError

try:
    # CircuitPython compatibility
    import asyncio
except ImportError:
    asyncio = None


class DisplayManager:
    """Core orchestrator for the display system.
    
    Coordinates display queue processing, strategy execution, and provides
    a unified interface for applications to manage display content.
    """
    
    def __init__(self, display: DisplayInterface, queue: Optional[DisplayQueue] = None):
        """Initialize the display manager.
        
        Args:
            display: Display interface to render to
            queue: Display queue to use (creates default if None)
        """
        self.display: DisplayInterface = display
        self.queue: DisplayQueue = queue or DisplayQueue()
        self._is_running: bool = False
        self._last_process_time: float = 0
        self._process_interval: float = 0.1  # Process queue every 100ms by default
        
        # Statistics
        self.stats: Dict[str, Any] = {
            'render_time_total': 0.0,
            'render_time_avg': 0.0,
            'renders_completed': 0,
            'errors_encountered': 0,
            'uptime_start': time.time()
        }
    
    async def start(self) -> None:
        """Start the display manager.
        
        Initializes the display and prepares for processing.
        """
        if not self._is_running:
            await self.display.initialize()
            self._is_running = True
            self.stats['uptime_start'] = time.time()
    
    async def stop(self) -> None:
        """Stop the display manager."""
        self._is_running = False
        await self.display.clear()
    
    async def process_queue(self) -> bool:
        """Process the display queue.
        
        This is the main method that applications should call regularly
        to process display items. It handles timing and queue management.
        
        Returns:
            True if processing should continue, False if stopped
        """
        if not self._is_running:
            return False
        
        current_time = time.time()
        
        # Check if it's time to process next item
        if current_time - self._last_process_time < self._process_interval:
            return True
        
        self._last_process_time = current_time
        
        try:
            # Process next item in queue
            render_start = time.time()
            processed = await self.queue.process_next(self.display)
            
            if processed:
                # Update render statistics
                render_time = time.time() - render_start
                self.stats['render_time_total'] += render_time
                self.stats['renders_completed'] += 1
                self.stats['render_time_avg'] = (
                    self.stats['render_time_total'] / self.stats['renders_completed']
                )
            
            # Update display
            await self.display.show()
            
            return True
            
        except (ContentError, DisplayError, OSError) as e:
            self.stats['errors_encountered'] += 1
            print(f"Error in display manager: {e}")
            return True  # Continue processing despite errors
    
    def add_item(self, strategy_name: str, data: Dict[str, Any], 
                 priority: int = Priority.NORMAL, 
                 duration: Optional[float] = None) -> bool:
        """Add an item to the display queue.
        
        Args:
            strategy_name: Name of the strategy to use
            data: Data dictionary for the strategy
            priority: Priority level
            duration: Display duration in seconds
            
        Returns:
            True if item was added successfully
        """
        item = DisplayItem(strategy_name, data, priority, duration)
        return self.queue.add_item(item)
    
    def add_display_item(self, item: DisplayItem) -> bool:
        """Add a pre-constructed DisplayItem to the queue.
        
        Args:
            item: DisplayItem to add
            
        Returns:
            True if item was added successfully
        """
        return self.queue.add_item(item)
    
    def clear_queue(self) -> None:
        """Clear all items from the display queue."""
        self.queue.clear()
    
    def set_process_interval(self, interval: float) -> None:
        """Set the queue processing interval.
        
        Args:
            interval: Time between queue processing in seconds
        """
        self._process_interval = max(0.01, interval)  # Minimum 10ms
    
    def get_queue_depth(self) -> int:
        """Get the current queue depth.
        
        Returns:
            Number of items in queue
        """
        return self.queue.get_queue_depth()
    
    def get_current_item(self) -> Optional[DisplayItem]:
        """Get the currently displaying item.
        
        Returns:
            Current DisplayItem or None
        """
        return self.queue.get_current_item()
    
    def get_registered_strategies(self) -> Dict[str, type]:
        """Get all registered display strategies.
        
        Returns:
            Dictionary of strategy names to strategy classes
        """
        registry = get_strategy_registry()
        return registry.list_strategies()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive statistics.
        
        Returns:
            Dictionary with display manager and queue statistics
        """
        uptime = time.time() - self.stats['uptime_start']
        
        # Build explicitly — CircuitPython doesn't support {**dict} literal unpacking.
        dm_stats = dict(self.stats)
        dm_stats['uptime_seconds'] = uptime
        dm_stats['is_running'] = self._is_running
        dm_stats['process_interval'] = self._process_interval
        return {
            'display_manager': dm_stats,
            'queue': self.queue.get_statistics(),
            'display': {
                'width': getattr(self.display, 'width', 'unknown'),
                'height': getattr(self.display, 'height', 'unknown'),
                'type': self.display.__class__.__name__
            }
        }
    
    # Convenience methods for common display patterns
    
    def show_text(self, text: str, duration: float = 5.0, 
                  priority: int = Priority.NORMAL, **kwargs) -> bool:
        """Show static text.
        
        Args:
            text: Text to display
            duration: Display duration
            priority: Priority level
            **kwargs: Additional parameters for the strategy
            
        Returns:
            True if item was added successfully
        """
        data = {'text': text}
        data.update(kwargs)
        return self.add_item('static_text', data, priority, duration)
    
    def show_scrolling_text(self, text: str, duration: Optional[float] = None,
                           priority: int = Priority.NORMAL, **kwargs) -> bool:
        """Show scrolling text.
        
        Args:
            text: Text to scroll
            duration: Display duration (auto-calculated if None)
            priority: Priority level
            **kwargs: Additional parameters for the strategy
            
        Returns:
            True if item was added successfully
        """
        data = {'text': text}
        data.update(kwargs)
        return self.add_item('scrolling_text', data, priority, duration)
    
    def show_alert(self, message: str, priority: int = Priority.HIGH,
                   duration: float = 3.0, **kwargs) -> bool:
        """Show an alert message.
        
        Args:
            message: Alert message
            priority: Priority level (default HIGH)
            duration: Display duration
            **kwargs: Additional parameters
            
        Returns:
            True if item was added successfully
        """
        data = {'text': message, 'color': kwargs.get('color', 0xFF0000)}  # Red default
        data.update(kwargs)
        return self.add_item('static_text', data, priority, duration)
    
    async def show_sequence(self, items: list) -> None:
        """Show a sequence of items.
        
        Args:
            items: List of (strategy_name, data, duration) tuples
        """
        for strategy_name, data, duration in items:
            self.add_item(strategy_name, data, Priority.NORMAL, duration)
            
            # Wait for this item to complete before adding next
            while self.get_current_item():
                await self.process_queue()
                if asyncio:
                    await asyncio.sleep(0.1)
                else:
                    time.sleep(0.1)