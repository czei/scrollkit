"""CircuitPython displayio.Group equivalent."""


class Group:
    """Group organizes display elements into a tree structure.
    
    Groups can contain other groups, creating a display hierarchy.
    Elements in a group can be positioned, scaled, and hidden.
    Compatible with CircuitPython's displayio.Group API.
    """
    
    def __init__(self, *, scale=1, x=0, y=0):
        """Initialize Group.
        
        Args:
            scale: Integer scale factor (default 1) 
            x: X position of group (default 0)
            y: Y position of group (default 0)
        """
        self.scale = scale
        self.x = x
        self.y = y
        self.hidden = False
        self._items = []
        
    def append(self, item):
        """Add an item to the group.
        
        Args:
            item: Display object (Group, TileGrid, etc.) to add
        """
        if item in self._items:
            raise ValueError("Item already in group")
        self._items.append(item)
        
    def insert(self, index, item):
        """Insert an item at a specific position.
        
        Args:
            index: Position to insert at
            item: Display object to insert
        """
        if item in self._items:
            raise ValueError("Item already in group")
        self._items.insert(index, item)
        
    def remove(self, item):
        """Remove an item from the group.
        
        Args:
            item: Display object to remove
        """
        self._items.remove(item)
        
    def pop(self, index=-1):
        """Remove and return an item.
        
        Args:
            index: Index of item to remove (default -1 for last item)
            
        Returns:
            Removed display object
        """
        return self._items.pop(index)
        
    def index(self, item):
        """Find the index of an item.
        
        Args:
            item: Display object to find
            
        Returns:
            Index of item in group
        """
        return self._items.index(item)
        
    def __len__(self):
        """Get number of items in group."""
        return len(self._items)
        
    def __getitem__(self, index):
        """Get item at index.
        
        Args:
            index: Index of item to get
            
        Returns:
            Display object at index
        """
        return self._items[index]
        
    def __setitem__(self, index, item):
        """Replace item at index.
        
        Args:
            index: Index to replace at
            item: New display object
        """
        # Remove old item if it exists elsewhere in group
        if item in self._items:
            self._items.remove(item)
        self._items[index] = item
        
    def __iter__(self):
        """Iterate over items in group."""
        return iter(self._items)
        
    def sort(self, key=None):
        """Sort items in group.
        
        Args:
            key: Optional key function for sorting
        """
        self._items.sort(key=key)
        
    @property
    def auto_write(self):
        """Get auto_write setting (always True for compatibility)."""
        return True
        
    @auto_write.setter
    def auto_write(self, value):
        """Set auto_write (no-op for compatibility)."""
        pass  # No-op for API compatibility