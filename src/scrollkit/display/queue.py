# Copyright (c) 2024-2026 Michael Winslow Czeiszperger
"""Display queue management for SLDK.

Implements a priority-based queue system for managing display items.
Supports manual processing, expiration handling, and fair scheduling.
"""

from __future__ import annotations

import heapq
import time
try:
    from typing import Any, Callable, List, Optional
except ImportError:  # CircuitPython has no 'typing' module
    pass
from .strategy import DisplayItem, Priority, get_strategy_registry
from ..exceptions import ContentError, ValidationError

try:
    # CircuitPython compatibility
    import asyncio
except ImportError:
    asyncio = None


class DisplayQueue:
    """Priority-based queue for display items.
    
    Manages display items with priority ordering, expiration handling,
    and manual processing control. Applications call process_next()
    to render the next item in the queue.
    """
    
    def __init__(self, max_items: int = 100, default_duration: float = 5.0):
        """Initialize the display queue.
        
        Args:
            max_items: Maximum number of items to keep in queue
            default_duration: Default duration for items without duration set
        """
        self.max_items: int = max_items
        self.default_duration: float = default_duration
        self._queue: List[DisplayItem] = []
        # Simple DisplayContent-based store for the high-level add/peek/pop/
        # expire API (separate from the DisplayItem/strategy heap above).
        self._content: List[Any] = []
        self._current_item: Optional[DisplayItem] = None
        self._item_start_time: Optional[float] = None
        self._on_item_expired: Optional[Callable[[DisplayItem], None]] = None
        
        # Statistics
        self.stats = {
            'items_processed': 0,
            'items_expired': 0,
            'items_dropped': 0,
            'queue_depth_max': 0
        }
    
    def add_item(self, item: DisplayItem) -> bool:
        """Add an item to the queue.
        
        Args:
            item: DisplayItem to add to queue
            
        Returns:
            True if item was added, False if queue is full
        """
        # Check if item is already expired
        if item.is_expired():
            self.stats['items_expired'] += 1
            return False
        
        # Validate item data with strategy
        registry = get_strategy_registry()
        strategy = registry.create_strategy(item.strategy_name)
        if strategy and not strategy.validate_data(item.data):
            return False
        
        # Check queue capacity
        if len(self._queue) >= self.max_items:
            # Remove lowest priority item if possible
            if not self._make_room_for_item(item):
                self.stats['items_dropped'] += 1
                return False
        
        # Add to priority queue
        heapq.heappush(self._queue, item)
        
        # Update statistics
        queue_depth = len(self._queue)
        if queue_depth > self.stats['queue_depth_max']:
            self.stats['queue_depth_max'] = queue_depth
        
        return True
    
    # ------------------------------------------------------------------
    # High-level DisplayContent API (priority + duration aware).
    # Operates on DisplayContent objects and is independent of the
    # DisplayItem/strategy heap used by DisplayManager.
    # ------------------------------------------------------------------

    def add(self, content) -> bool:
        """Add DisplayContent to the queue with priority-based eviction.

        Eviction policy (spec FR-007a) when the queue is full:
        - SYSTEM priority is always admitted (evicting the lowest-priority,
          oldest non-SYSTEM item to make room).
        - A higher-priority item displaces the lowest-priority present item.
        - An item lower-or-equal priority than everything present is rejected.
        - SYSTEM items are never evicted by add().

        Returns:
            True if the content was added, False if rejected.
        """
        pr = getattr(content, 'priority', Priority.NORMAL)

        if len(self._content) >= self.max_items:
            evictable = [c for c in self._content
                         if getattr(c, 'priority', Priority.NORMAL) != Priority.SYSTEM]
            if not evictable:
                # Queue is full of SYSTEM items; nothing may be evicted.
                return False
            # Lowest priority, then oldest (earliest inserted) among ties.
            victim = min(evictable,
                         key=lambda c: (getattr(c, 'priority', Priority.NORMAL),
                                        self._content.index(c)))
            if pr == Priority.SYSTEM or pr > getattr(victim, 'priority', Priority.NORMAL):
                self._content.remove(victim)
            else:
                return False

        self._content.append(content)
        return True

    def peek(self):
        """Return the highest-priority non-expired item without removing it."""
        self.expire()
        if not self._content:
            return None
        return max(self._content,
                   key=lambda c: getattr(c, 'priority', Priority.NORMAL))

    def pop(self):
        """Remove and return the highest-priority non-expired item.

        Among equal priorities the earliest-inserted item is returned (FIFO).
        """
        self.expire()
        if not self._content:
            return None
        best = max(self._content,
                   key=lambda c: getattr(c, 'priority', Priority.NORMAL))
        self._content.remove(best)
        return best

    def expire(self) -> int:
        """Remove completed (duration-elapsed) items. Returns count removed."""
        before = len(self._content)
        self._content = [c for c in self._content if not getattr(c, 'is_complete', False)]
        return before - len(self._content)

    def __len__(self) -> int:
        return len(self._content)

    def _make_room_for_item(self, new_item: DisplayItem) -> bool:
        """Try to make room for a new item by removing lower priority items.
        
        Args:
            new_item: Item that needs to be added
            
        Returns:
            True if room was made, False otherwise
        """
        if not self._queue:
            return True
        
        # Find the lowest priority item
        lowest_priority_item = min(self._queue, key=lambda x: (x.priority, -x.created_at))
        
        # Only remove if new item has higher priority
        if new_item.priority > lowest_priority_item.priority:
            self._queue.remove(lowest_priority_item)
            heapq.heapify(self._queue)  # Restore heap property
            return True
        
        return False
    
    async def process_next(self, display) -> bool:
        """Process the next item in the queue.
        
        This method should be called by the application when it's ready
        to render the next display item.
        
        Args:
            display: Display interface to render to
            
        Returns:
            True if an item was processed, False if queue is empty
        """
        # Clean up expired items
        self._remove_expired_items()
        
        # Check if current item is still valid
        if self._current_item and self._should_continue_current_item():
            return True
        
        # Get next item from queue
        next_item = self._get_next_item()
        if not next_item:
            # No items available
            self._current_item = None
            self._item_start_time = None
            return False
        
        # Start processing new item
        self._current_item = next_item
        self._item_start_time = time.time()
        
        try:
            # Get strategy and render
            registry = get_strategy_registry()
            strategy = registry.create_strategy(next_item.strategy_name)
            
            if not strategy:
                raise ValueError(f"Unknown strategy: {next_item.strategy_name}")
            
            await strategy.render(display, next_item.data)
            
            self.stats['items_processed'] += 1
            return True
            
        except (ContentError, ValidationError, ValueError, OSError) as e:
            # Log error and move to next item
            print(f"Error processing display item: {e}")
            self._current_item = None
            self._item_start_time = None
            return await self.process_next(display)  # Try next item

    def _should_continue_current_item(self) -> bool:
        """Check if the current item should continue displaying.
        
        Returns:
            True if current item should continue, False if it should end
        """
        if not self._current_item or not self._item_start_time:
            return False
        
        # Check if item has expired
        if self._current_item.is_expired():
            return False
        
        # Calculate how long item has been displaying
        elapsed_time = time.time() - self._item_start_time
        
        # Get duration (from item, strategy recommendation, or default)
        duration = self._current_item.duration
        if duration is None:
            # Try to get duration from strategy
            registry = get_strategy_registry()
            strategy = registry.create_strategy(self._current_item.strategy_name)
            if strategy:
                duration = strategy.get_render_duration(self._current_item.data)
        
        if duration is None:
            duration = self.default_duration
        
        return elapsed_time < duration
    
    def _get_next_item(self) -> Optional[DisplayItem]:
        """Get the next item from the queue.
        
        Returns:
            Next DisplayItem or None if queue is empty
        """
        while self._queue:
            item = heapq.heappop(self._queue)
            
            # Check if item is expired
            if item.is_expired():
                self.stats['items_expired'] += 1
                continue
            
            return item
        
        return None
    
    def _remove_expired_items(self) -> None:
        """Remove expired items from the queue."""
        original_size = len(self._queue)
        self._queue = [item for item in self._queue if not item.is_expired()]
        
        # Restore heap property if items were removed
        if len(self._queue) < original_size:
            heapq.heapify(self._queue)
            self.stats['items_expired'] += original_size - len(self._queue)
    
    def clear(self) -> None:
        """Clear all items from the queue."""
        self._queue.clear()
        self._current_item = None
        self._item_start_time = None
    
    def get_queue_depth(self) -> int:
        """Get the current number of items in the queue.
        
        Returns:
            Number of items in queue
        """
        return len(self._queue)
    
    def get_current_item(self) -> Optional[DisplayItem]:
        """Get the currently displaying item.
        
        Returns:
            Current DisplayItem or None if nothing is displaying
        """
        return self._current_item
    
    def get_items_by_priority(self, priority: int) -> List[DisplayItem]:
        """Get all items in queue with specific priority.
        
        Args:
            priority: Priority level to filter by
            
        Returns:
            List of DisplayItems with matching priority
        """
        return [item for item in self._queue if item.priority == priority]
    
    def remove_items_by_metadata(self, key: str, value: Any) -> int:
        """Remove items from queue based on metadata.
        
        Args:
            key: Metadata key to match
            value: Metadata value to match
            
        Returns:
            Number of items removed
        """
        original_size = len(self._queue)
        self._queue = [item for item in self._queue 
                      if item.get_metadata(key) != value]
        
        # Restore heap property if items were removed
        if len(self._queue) < original_size:
            heapq.heapify(self._queue)
        
        return original_size - len(self._queue)
    
    def set_item_expired_callback(self, callback: Callable[[DisplayItem], None]) -> None:
        """Set callback for when items expire.
        
        Args:
            callback: Function to call when items expire
        """
        self._on_item_expired = callback
    
    def get_statistics(self) -> dict:
        """Get queue statistics.
        
        Returns:
            Dictionary with queue statistics
        """
        # Build explicitly — CircuitPython doesn't support {**dict} literal unpacking.
        stats = dict(self.stats)
        stats['current_queue_depth'] = len(self._queue)
        stats['current_item'] = self._current_item.strategy_name if self._current_item else None
        return stats