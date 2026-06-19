"""Glyph caching for bitmap fonts."""

from ..displayio import Bitmap


class GlyphCache:
    """Cache for rendered font glyphs.
    
    Stores pre-rendered glyphs to improve text rendering performance.
    """
    
    def __init__(self, max_glyphs=256):
        """Initialize glyph cache.
        
        Args:
            max_glyphs: Maximum number of glyphs to cache
        """
        self.max_glyphs = max_glyphs
        self._cache = {}
        self._access_order = []
        
    def get(self, char_code):
        """Get a cached glyph.
        
        Args:
            char_code: Character code to get
            
        Returns:
            Cached glyph info dictionary or None if not cached
        """
        if char_code in self._cache:
            # Move to end of access order (most recently used)
            self._access_order.remove(char_code)
            self._access_order.append(char_code)
            return self._cache[char_code]['info']
        return None
        
    def put(self, char_code, glyph_bitmap, glyph_info):
        """Add a glyph to the cache.
        
        Args:
            char_code: Character code
            glyph_bitmap: Bitmap containing glyph pixels
            glyph_info: Dictionary with glyph metrics
        """
        # Check if we need to evict old glyphs
        if len(self._cache) >= self.max_glyphs and char_code not in self._cache:
            # Evict least recently used
            old_char = self._access_order.pop(0)
            del self._cache[old_char]
            
        # Add to cache
        self._cache[char_code] = {
            'bitmap': glyph_bitmap,
            'info': glyph_info
        }
        
        # Update access order
        if char_code in self._access_order:
            self._access_order.remove(char_code)
        self._access_order.append(char_code)
        
    def clear(self):
        """Clear all cached glyphs."""
        self._cache.clear()
        self._access_order.clear()
        
    def __len__(self):
        """Get number of cached glyphs."""
        return len(self._cache)